"""
Link extraction in the weekly DAGs (linking_tasks.py, etl_factory.py).

The DAG-structure tests import the three DAG files against recording stand-ins
for Airflow's operators and task groups (no Airflow install). The month tests
need a real Postgres, as in test_link_loader.py: they run only when
CLE_TEST_PG_DSN points at a server where the test may create and drop a
scratch database.
"""

import importlib
import json
import sys
import types
from datetime import date
from types import SimpleNamespace

import etl_factory
import linking_tasks
import pytest
from tests.linking_db import DSN, add_case, execute, needs_db, scratch_db  # noqa: F401

LINK_ENV = (
    "LINK_EXTRACTION_ENABLED",
    "LINK_RS_TEXT",
    "LINK_ECHR_TEXT",
    "LINK_CJEU_TEXT",
    "LINK_CELLAR_REFERRALS",
    "LINK_AG_OPINIONS",
    "LINK_CELLAR_RELATIONS",
    "LINK_CELLAR_UUID_CACHE",
    "LINK_CELLAR_UUID_CELEX_CACHE",
    "CASE_IDENTIFIER_ENABLED",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in LINK_ENV + ("SEGMENTATION_API_URL",):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------


def test_dataset_names_match_the_extractor_modules():
    from data_extraction.linking import (
        ag_opinions,
        cellar_referrals,
        cellar_relations,
        cjeu_text,
        echr_text,
        rs_text,
    )

    ex = linking_tasks.EXTRACTORS
    assert ex["rs_text"].datasets == (
        rs_text.DATASET_ECLI,
        rs_text.DATASET_CJEU,
        rs_text.DATASET_ECHR,
    )
    assert ex["echr_text"].datasets == echr_text.DATASETS
    assert ex["cjeu_text"].datasets == (cjeu_text.DATASET,)
    assert ex["cellar_referrals"].datasets == (cellar_referrals.SOURCE_DATASET,)
    assert ex["ag_opinions"].datasets == (ag_opinions.SOURCE_DATASET,)
    assert ex["cellar_relations"].datasets == (cellar_relations.SOURCE_DATASET,)


def test_promoter_paths_per_source():
    sources = linking_tasks.SOURCES
    assert linking_tasks.artifact_paths(sources["rechtspraak"], "2026-09-01") == [
        "processed/2026-09-01/links/rs_text_ecli.jsonl",
        "processed/2026-09-01/links/rs_text_cjeu_casenum.jsonl",
        "processed/2026-09-01/links/rs_text_echr_appno.jsonl",
    ]
    assert linking_tasks.artifact_paths(sources["echr"], "2026-09-01") == [
        "processed/2026-09-01/links/echr_text_cjeu.jsonl",
        "processed/2026-09-01/links/echr_text_rs.jsonl",
    ]
    assert linking_tasks.artifact_paths(sources["cellar"], "2026-09-01") == [
        "processed/2026-09-01/links/cjeu_text_echr.jsonl",
        "processed/2026-09-01/links/cellar_national_judgement.jsonl",
        "processed/2026-09-01/links/cjeu_ag_link.jsonl",
        "processed/2026-09-01/links/cellar_relation_resolved.jsonl",
    ]
    assert (
        linking_tasks.counts_path(sources["cellar"], "2026-09-01")
        == "processed/2026-09-01/links/_counts.CELLAR.json"
    )
    # the promoter keys its sources by dag_id and prefix
    assert {s.dag_id: s.prefix for s in sources.values()} == {
        "rechtspraak_etl": "RS",
        "cellar_etl": "CELLAR",
        "echr_etl": "ECHR",
    }


def test_flags_default_off_and_extractors_default_on(monkeypatch, tmp_path):
    assert not linking_tasks.enabled()
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "true")
    assert linking_tasks.enabled()

    plan = linking_tasks.extractor_plan(linking_tasks.SOURCES["cellar"])
    reasons = {e.name: reason for e, reason in plan}
    assert reasons == {
        "cjeu_text": None,
        "cellar_referrals": None,
        "ag_opinions": None,
        "cellar_relations": "LINK_CELLAR_UUID_CACHE is not set",
    }

    monkeypatch.setenv("LINK_CELLAR_UUID_CACHE", str(tmp_path / "missing.json"))
    monkeypatch.setenv("LINK_AG_OPINIONS", "false")
    reasons = {e.name: r for e, r in linking_tasks.extractor_plan(linking_tasks.SOURCES["cellar"])}
    assert reasons["ag_opinions"] == "LINK_AG_OPINIONS is off"
    assert "does not exist" in reasons["cellar_relations"]

    cache = tmp_path / "uuid.json"
    cache.write_text("{}")
    monkeypatch.setenv("LINK_CELLAR_UUID_CACHE", str(cache))
    reasons = {e.name: r for e, r in linking_tasks.extractor_plan(linking_tasks.SOURCES["cellar"])}
    assert reasons["cellar_relations"] is None


def test_window_callable_is_a_no_op_with_the_master_off(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("must not run")

    monkeypatch.setattr(linking_tasks, "run_month", boom)
    assert linking_tasks.run_window_links("CELLAR", dag_run=None) is None


def test_month_chunks_name_the_same_folders_as_run_window():
    assert list(etl_factory.iter_month_chunks(date(2026, 5, 15), date(2026, 7, 3))) == [
        (date(2026, 5, 15), date(2026, 5, 31)),
        (date(2026, 6, 1), date(2026, 6, 30)),
        (date(2026, 7, 1), date(2026, 7, 3)),
    ]


# ---------------------------------------------------------------------------
# DAG structure
# ---------------------------------------------------------------------------


class _Graph:
    def __init__(self):
        self.tasks = {}
        self.edges = set()
        self.groups = []

    def connect(self, upstream, downstream):
        for a in upstream.leaves():
            for b in downstream.roots():
                self.edges.add((a, b))


class _FakeTask:
    graph = None

    def __init__(self, task_id, dag=None, **kwargs):
        graph = _FakeTask.graph
        group = graph.groups[-1] if graph.groups else None
        self.task_id = f"{group.group_id}.{task_id}" if group else task_id
        self.kwargs = kwargs
        graph.tasks[self.task_id] = self
        if group:
            group.task_ids.append(self.task_id)

    def leaves(self):
        return [self.task_id]

    roots = leaves

    def __rshift__(self, other):
        _FakeTask.graph.connect(self, other)
        return other


class _FakeGroup:
    def __init__(self, group_id, tooltip=None, dag=None):
        self.group_id = group_id
        self.task_ids = []

    def __enter__(self):
        _FakeTask.graph.groups.append(self)
        return self

    def __exit__(self, *exc):
        _FakeTask.graph.groups.pop()
        return False

    def _inner(self):
        return {
            (a, b) for a, b in _FakeTask.graph.edges if a in self.task_ids and b in self.task_ids
        }

    def leaves(self):  # Airflow: tasks of the group with nothing downstream in it
        inner = self._inner()
        return [t for t in self.task_ids if not any(a == t for a, _ in inner)]

    def roots(self):
        inner = self._inner()
        return [t for t in self.task_ids if not any(b == t for _, b in inner)]

    def __rshift__(self, other):
        _FakeTask.graph.connect(self, other)
        return other


class _FakeDag:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stub(monkeypatch, name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, module)


def _load_dag(monkeypatch, module_name):
    graph = _Graph()
    monkeypatch.setattr(_FakeTask, "graph", graph)
    monkeypatch.setattr(sys.modules["airflow.operators.python"], "PythonOperator", _FakeTask)
    monkeypatch.setattr(etl_factory, "PythonOperator", _FakeTask)
    monkeypatch.setattr(etl_factory, "TaskGroup", _FakeGroup)
    monkeypatch.setattr(sys.modules["airflow"], "DAG", _FakeDag, raising=False)
    _stub(monkeypatch, "airflow.operators.trigger_dagrun", TriggerDagRunOperator=_FakeTask)
    _stub(monkeypatch, "dotenv", find_dotenv=lambda: "", load_dotenv=lambda *a, **k: None)
    _stub(monkeypatch, "data_transformation.data_transformer")
    _stub(monkeypatch, "data_loading.data_loader")
    noop = lambda *a, **k: None  # noqa: E731
    _stub(
        monkeypatch,
        "data_extraction.caselaw.cellar.cellar_extraction",
        cellar_extract=noop,
    )
    _stub(monkeypatch, "data_extraction.caselaw.echr.echr_extraction", echr_extract=noop)
    _stub(
        monkeypatch,
        "data_extraction.caselaw.rechtspraak.rechtspraak_extraction",
        rechtspraak_extract=noop,
        rechtspraak_extract_modified=noop,
    )
    sys.modules.pop(module_name, None)
    try:
        importlib.import_module(module_name)
    finally:
        sys.modules.pop(module_name, None)
    return graph


DAGS = [
    ("rechtspraak_etl", "RS"),
    ("cellar_etl", "CELLAR"),
    ("echr_etl", "ECHR"),
]


@pytest.mark.parametrize("dag_id, prefix", DAGS)
def test_dag_unchanged_with_the_master_off(monkeypatch, dag_id, prefix):
    graph = _load_dag(monkeypatch, dag_id)

    run_window = f"{dag_id}_tasks.run_window"
    assert set(graph.tasks) == {run_window, "register_promotion"}
    assert graph.edges == {(run_window, "register_promotion")}
    assert graph.tasks[run_window].kwargs["python_callable"] is etl_factory.run_monthly_window
    assert graph.tasks[run_window].kwargs["op_kwargs"]["var_prefix"] == prefix
    assert graph.tasks["register_promotion"].kwargs["op_kwargs"] == {
        "dag_id": dag_id,
        "var_prefix": prefix,
    }


@pytest.mark.parametrize("dag_id, prefix", DAGS)
def test_links_run_after_the_load_and_before_promotion(monkeypatch, dag_id, prefix):
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "1")
    graph = _load_dag(monkeypatch, dag_id)

    run_window = f"{dag_id}_tasks.run_window"
    links = f"{dag_id}_tasks.extract_links"
    assert set(graph.tasks) == {run_window, links, "register_promotion"}
    assert graph.edges == {(run_window, links), (links, "register_promotion")}
    assert graph.tasks[links].kwargs["python_callable"] is linking_tasks.run_window_links
    assert graph.tasks[links].kwargs["op_kwargs"] == {"var_prefix": prefix}


def test_segmentation_trigger_also_waits_for_links(monkeypatch):
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "1")
    monkeypatch.setenv("SEGMENTATION_API_URL", "http://segmentation")
    graph = _load_dag(monkeypatch, "rechtspraak_etl")

    assert graph.edges == {
        ("rechtspraak_etl_tasks.run_window", "rechtspraak_etl_tasks.extract_links"),
        ("rechtspraak_etl_tasks.extract_links", "trigger_case_segmentation"),
        ("trigger_case_segmentation", "register_promotion"),
    }


def test_group_without_links_ignores_the_flag(monkeypatch):
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "1")
    graph = _Graph()
    monkeypatch.setattr(_FakeTask, "graph", graph)
    monkeypatch.setattr(etl_factory, "PythonOperator", _FakeTask)
    monkeypatch.setattr(etl_factory, "TaskGroup", _FakeGroup)
    etl_factory.build_monthly_task_group(None, "x", "RS", lambda **k: None)
    assert set(graph.tasks) == {"x_tasks.run_window"}


# ---------------------------------------------------------------------------
# a month against a scratch database
# ---------------------------------------------------------------------------


def _processed(tmp_path, month, name, column, keys):
    folder = tmp_path / "processed" / month
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"{column},title"] + [f"{k},x" for k in keys]
    (folder / name).write_text("\n".join(lines) + "\n")
    return folder


def _cellar_month(conn, tmp_path, month="2013-07-01"):
    opinion = add_case(conn, "ECLI:EU:C:2013:474", "62012CC0199", date(2013, 7, 11))
    execute(conn, "INSERT INTO cle_v2.cjeu_ag_opinion (case_id) VALUES (%s)", (opinion,))
    judgment = add_case(conn, "ECLI:EU:C:2013:720", "62012CJ0199", date(2013, 11, 7))
    folder = _processed(
        tmp_path,
        month,
        "cellar_csv_data_clean.csv",
        "celex",
        ["62012CC0199", "62099CJ0001"],  # the second is not in the database
    )
    return opinion, judgment, folder / "links"


@needs_db
def test_cellar_month_writes_every_file_and_loads(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    conn = scratch_db
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "1")
    opinion, _judgment, links = _cellar_month(conn, tmp_path)

    counts = linking_tasks.run_month(
        conn, linking_tasks.SOURCES["cellar"], str(tmp_path), "2013-07-01"
    )

    expected = linking_tasks.artifact_paths(linking_tasks.SOURCES["cellar"], "2013-07-01")
    for path in expected:
        assert (tmp_path / path).is_file()
    assert sorted(p.name for p in links.iterdir()) == sorted(
        [p.rsplit("/", 1)[1] for p in expected] + ["_counts.CELLAR.json"]
    )
    sizes = {p.name: p.stat().st_size for p in links.iterdir()}
    assert sizes["cjeu_text_echr.jsonl"] == 0
    assert sizes["cellar_national_judgement.jsonl"] == 0
    assert sizes["cellar_relation_resolved.jsonl"] == 0
    assert sizes["cjeu_ag_link.jsonl"] > 0

    assert counts["case_keys"] == 2 and counts["case_ids"] == 1
    assert counts["extractors"]["cellar_relations"] == {
        "status": "skipped",
        "reason": "LINK_CELLAR_UUID_CACHE is not set",
    }
    assert counts["extractors"]["ag_opinions"] == {"status": "ran"}
    assert counts["datasets"]["cjeu_ag_link"] == {"records": 1, "load": {"inserted": 1}}
    assert counts["datasets"]["cjeu_text_echr"] == {"records": 0, "load": {}}
    assert counts["case_identifier_enabled"] is False
    assert json.loads((links / "_counts.CELLAR.json").read_text()) == counts
    assert execute(
        conn, "SELECT source_case_id, relation_type, source_dataset FROM cle_v2.case_citation"
    ) == [(opinion, "opinion_of", "cjeu_ag_link")]

    # a retry rewrites the same files and inserts nothing new
    before = (links / "cjeu_ag_link.jsonl").read_bytes()
    again = linking_tasks.run_month(
        conn, linking_tasks.SOURCES["cellar"], str(tmp_path), "2013-07-01"
    )
    assert (links / "cjeu_ag_link.jsonl").read_bytes() == before
    assert again["datasets"]["cjeu_ag_link"]["load"] == {"existing": 1}
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_citation") == [(1,)]


@needs_db
def test_cellar_relations_runs_with_a_cache_and_flags_switch_off(
    scratch_db, tmp_path, monkeypatch  # noqa: F811
):
    conn = scratch_db
    cache = tmp_path / "uuid_dossier.json"
    cache.write_text("{}")
    monkeypatch.setenv("LINK_CELLAR_UUID_CACHE", str(cache))
    monkeypatch.setenv("LINK_AG_OPINIONS", "no")
    _opinion, _judgment, links = _cellar_month(conn, tmp_path)

    counts = linking_tasks.run_month(
        conn, linking_tasks.SOURCES["cellar"], str(tmp_path), "2013-07-01"
    )

    assert counts["extractors"]["cellar_relations"] == {"status": "ran"}
    assert counts["extractors"]["ag_opinions"]["status"] == "skipped"
    assert (links / "cjeu_ag_link.jsonl").stat().st_size == 0
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_citation") == [(0,)]


@needs_db
def test_rs_month_splits_datasets(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    add_case(conn, "ECLI:EU:C:2019:189", "62017CJ0221", date(2019, 3, 12))
    rs = add_case(conn, "ECLI:NL:HR:2022:637", None, date(2022, 4, 22), sources=("RS",))
    execute(
        conn,
        """INSERT INTO cle_v2.case_text (case_id, language, source, summary)
           VALUES (%s, 'nl', 'RECHTSPRAAK', 'Art. 81 RO. Tjebbes, EU:C:2019:189.')""",
        (rs,),
    )
    _processed(tmp_path, "2022-04-01", "RS_cases_clean.csv", "ECLI", ["ECLI:NL:HR:2022:637"])

    counts = linking_tasks.run_month(
        conn, linking_tasks.SOURCES["rechtspraak"], str(tmp_path), "2022-04-01"
    )

    assert {d: v["records"] for d, v in counts["datasets"].items()} == {
        "rs_text_ecli": 1,
        "rs_text_cjeu_casenum": 0,
        "rs_text_echr_appno": 0,
    }
    assert counts["datasets"]["rs_text_ecli"]["load"] == {"inserted": 1, "mentions_inserted": 1}
    links = tmp_path / "processed" / "2022-04-01" / "links"
    assert (links / "rs_text_cjeu_casenum.jsonl").read_text() == ""
    assert (links / "_counts.RS.json").is_file()


@needs_db
def test_echr_keys_map_through_document_variants(scratch_db):  # noqa: F811
    conn = scratch_db
    case = execute(
        conn,
        """INSERT INTO cle_v2.cases (ecli, item_id, sources)
           VALUES ('ECLI:CE:ECHR:2004:0101JUD001234500', '001-1', '{ECHR}') RETURNING id""",
    )[0][0]
    execute(
        conn,
        """INSERT INTO cle_v2.echr_document (item_id, case_id, language, doctype)
           VALUES ('001-1', %s, 'en', 'HEJUD'), ('001-2', %s, 'fr', 'HFJUD')""",
        (case, case),
    )
    source = linking_tasks.SOURCES["echr"]
    assert linking_tasks.case_ids_for_keys(conn, source, ["001-2"]) == [case]
    assert linking_tasks.case_ids_for_keys(conn, source, ["001-1", "001-2", "001-9"]) == [case]


@needs_db
def test_late_binding_is_called_when_present(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    from data_loading import link_loader

    conn = scratch_db
    calls = []

    def resolve_late(conn, case_ids=None):
        calls.append(case_ids)
        return {"resolved": 0}

    monkeypatch.setattr(link_loader, "resolve_late", resolve_late, raising=False)
    opinion, _judgment, _links = _cellar_month(conn, tmp_path)

    counts = linking_tasks.run_month(
        conn, linking_tasks.SOURCES["cellar"], str(tmp_path), "2013-07-01"
    )

    assert calls == [[opinion]]
    assert counts["late_binding"] == {"resolved": 0}


def test_late_binding_absent_is_skipped(monkeypatch):
    from data_loading import link_loader

    monkeypatch.delattr(link_loader, "resolve_late", raising=False)
    assert linking_tasks.late_bind(object(), [1, 2]) is None


def test_marked_month_is_skipped(tmp_path):
    folder = tmp_path / "processed" / "2026-11-01"
    folder.mkdir(parents=True)
    (folder / "no_source_data.ECHR.marker").write_text("x")
    assert (
        linking_tasks.run_month(
            object(), linking_tasks.SOURCES["echr"], str(tmp_path), "2026-11-01"
        )
        is None
    )
    assert not (folder / "links").exists()


def test_missing_processed_csv_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        linking_tasks.run_month(
            object(), linking_tasks.SOURCES["echr"], str(tmp_path), "2026-11-01"
        )


@needs_db
def test_window_task_covers_every_month_chunk(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    conn = scratch_db
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "1")
    _cellar_month(conn, tmp_path, month="2013-07-01")
    marked = tmp_path / "processed" / "2013-08-01"
    marked.mkdir(parents=True)
    (marked / "no_source_data.CELLAR.marker").write_text("x")

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def _get_conn(self):
            return conn

    from data_loading.clients import postgres

    monkeypatch.setattr(postgres, "PostgresCLEClient", Client)
    monkeypatch.setattr(etl_factory, "get_data_path", lambda: str(tmp_path))
    dag_run = SimpleNamespace(
        run_id="manual__1",
        run_type="manual",
        conf={"window_start": "2013-07-01", "window_end": "2013-08-10"},
    )

    summary = linking_tasks.run_window_links("CELLAR", dag_run=dag_run)

    assert summary == {
        "2013-07-01": {
            "cjeu_text_echr": 0,
            "cellar_national_judgement": 0,
            "cjeu_ag_link": 1,
            "cellar_relation_resolved": 0,
        },
        "2013-08-01": None,
    }


@needs_db
def test_backfill_cli(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    conn = scratch_db
    opinion, judgment, _links = _cellar_month(conn, tmp_path)
    monkeypatch.setenv("LINK_TEST_DSN", DSN.rpartition("/")[0] + "/" + conn.info.dbname)
    out = tmp_path / "backfill"

    argv = ["backfill", "--dsn-env", "LINK_TEST_DSN", "--source", "cellar"]
    argv += ["--from-id", str(min(opinion, judgment)), "--to-id", str(max(opinion, judgment))]
    assert linking_tasks.main(argv + ["--out", str(out)]) == 0
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_citation") == [(0,)]
    assert sorted(p.name for p in out.iterdir()) == [
        "_counts.CELLAR.json",
        "cellar_national_judgement.jsonl",
        "cellar_relation_resolved.jsonl",
        "cjeu_ag_link.jsonl",
        "cjeu_text_echr.jsonl",
    ]

    assert linking_tasks.main(argv + ["--out", str(out), "--load"]) == 0
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_citation") == [(1,)]
    counts = json.loads((out / "_counts.CELLAR.json").read_text())
    assert counts["datasets"]["cjeu_ag_link"] == {"records": 1, "load": {"inserted": 1}}


# ---------------------------------------------------------------------------
# streaming split, Cellar caches (no database)
# ---------------------------------------------------------------------------


def _rs_record(i, dataset):
    from data_extraction.linking.artifact import LinkRecord

    value = {
        "source": {"ecli": f"ECLI:NL:HR:2022:{i}"},
        "relation_type": "cites",
        "source_dataset": dataset,
        "extractor_version": "rs_text/test",
    }
    if dataset == "rs_text_ecli":
        value.update(target={"ecli": f"ECLI:EU:C:2019:{i}"}, match_method="ecli")
    else:
        value.update(target_ref_raw=f"C-{i}/17", target_ref_scheme="cjeu_case_number")
    return LinkRecord.from_dict(value)


def test_extract_links_splits_the_stream_in_the_extractors_order(tmp_path, monkeypatch):
    from data_extraction.linking.artifact import ArtifactWriter

    datasets = ("rs_text_ecli", "rs_text_cjeu_casenum")
    batches = [[_rs_record(b * 10 + i, datasets[i % 2]) for i in range(6)] for b in range(3)]

    def fake_run(conn, extractor, out_path, case_ids=None, id_range=None):
        with ArtifactWriter(out_path) as writer:
            for batch in batches:
                writer.write(batch)
        fake_run.raw = open(out_path, encoding="utf-8").read().splitlines()

    monkeypatch.setattr(linking_tasks, "_run_extractor", fake_run)
    out = tmp_path / "links"
    statuses, counts = linking_tasks.extract_links(
        None, linking_tasks.SOURCES["rechtspraak"], str(out), case_ids=[1]
    )
    assert statuses == {"rs_text": {"status": "ran"}}
    assert counts == {
        "rs_text_ecli": {"records": 9},
        "rs_text_cjeu_casenum": {"records": 9},
        "rs_text_echr_appno": {"records": 0},
    }
    for dataset in datasets:
        expected = [line for line in fake_run.raw if f'"source_dataset": "{dataset}"' in line]
        assert (out / f"{dataset}.jsonl").read_text().splitlines() == expected
    assert sorted(p.name for p in out.iterdir()) == sorted(f"{d}.jsonl" for d in counts)


def test_extract_links_refuses_a_foreign_dataset_and_keeps_old_files(tmp_path, monkeypatch):
    from data_extraction.linking.artifact import write_jsonl

    out = tmp_path / "links"
    out.mkdir()
    (out / "rs_text_ecli.jsonl").write_text("previous run\n")

    def fake_run(conn, extractor, out_path, case_ids=None, id_range=None):
        write_jsonl([_rs_record(1, "rs_text_ecli")], out_path)
        with open(out_path, "a", encoding="utf-8") as handle:
            line = json.dumps(_rs_record(2, "rs_text_ecli").to_dict())
            handle.write(line.replace("rs_text_ecli", "echr_text_rs", 1) + "\n")

    monkeypatch.setattr(linking_tasks, "_run_extractor", fake_run)
    with pytest.raises(ValueError, match="rs_text: .*echr_text_rs"):
        linking_tasks.extract_links(
            None, linking_tasks.SOURCES["rechtspraak"], str(out), case_ids=[1]
        )
    assert (out / "rs_text_ecli.jsonl").read_text() == "previous run\n"
    assert sorted(p.name for p in out.iterdir()) == ["rs_text_ecli.jsonl"]


@pytest.mark.parametrize("celex_cache", ["unset", "missing", "present"])
def test_cellar_relations_gets_the_optional_uuid_celex_cache(
    tmp_path, monkeypatch, caplog, celex_cache
):
    from data_extraction.linking import cellar_relations

    dossier = tmp_path / "uuid_dossier.json"
    dossier_uri = "http://x/resource/cellar/aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
    dossier.write_text(json.dumps({dossier_uri: ["C-1/20 P"]}))
    monkeypatch.setenv("LINK_CELLAR_UUID_CACHE", str(dossier))
    celex = tmp_path / "uuid_celex.json"
    if celex_cache == "present":
        work_uri = "cellar:cccccccc-1111-2222-3333-dddddddddddd"
        celex.write_text(json.dumps({work_uri: ["62020CJ0646"]}))
    if celex_cache != "unset":
        monkeypatch.setenv("LINK_CELLAR_UUID_CELEX_CACHE", str(celex))
    seen = {}
    fake = SimpleNamespace(
        load_uuid_map=cellar_relations.load_uuid_map,
        extract=lambda conn, **kwargs: seen.update(kwargs),
    )
    monkeypatch.setattr(linking_tasks.importlib, "import_module", lambda name: fake)
    linking_tasks._run_extractor(
        None, linking_tasks.EXTRACTORS["cellar_relations"], "out.jsonl", case_ids=[1]
    )
    assert len(seen["uuid_dossier"]) == 1
    if celex_cache == "present":
        assert list(seen["uuid_celex"].values()) == [["62020CJ0646"]]
    else:
        assert seen["uuid_celex"] == {}
    assert ("does not exist" in caplog.text) == (celex_cache == "missing")
