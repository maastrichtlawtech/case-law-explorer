"""
Outcome and status extraction, loading and the timeline query against a
scratch database built from db/schema.sql (only with CLE_TEST_PG_DSN, see
tests/linking_db.py), and the DAG wiring of OUTCOME_EXTRACTION_ENABLED.

Data: the ECLIs and application number of M.E. v. Sweden (71398/12) are real;
HUDOC item ids and field
values, Cellar type_procedure values outside issue #83 and every Dutch text
are ILLUSTRATIVE, written for the test (the research files hold none).
"""

import json
from datetime import date
from pathlib import Path

import pytest

import linking_tasks
from data_extraction.case_context import case_status, cjeu_outcomes, echr_outcomes, rs_dictum
from data_extraction.case_context.artifact import read_jsonl
from data_loading import outcome_loader
from tests.linking_db import DSN, add_case, execute, needs_db, scratch_db  # noqa: F401
from tests.test_linking_tasks import DAGS, _load_dag

OUTCOME_ENV = ("OUTCOME_EXTRACTION_ENABLED", "RS_DICTUM_ENABLED", "LINK_EXTRACTION_ENABLED")
TIMELINE_SQL = Path(__file__).resolve().parents[3] / "db" / "queries" / "case_timeline.sql"

ME_CHAMBER = "ECLI:CE:ECHR:2014:0626JUD007139812"
ME_GC = "ECLI:CE:ECHR:2015:0408JUD007139812"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in OUTCOME_ENV + ("SEGMENTATION_API_URL",):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# DAG wiring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dag_id, prefix", DAGS)
def test_dag_unchanged_with_outcomes_off(monkeypatch, dag_id, prefix):
    graph = _load_dag(monkeypatch, dag_id)
    run_window = f"{dag_id}_tasks.run_window"
    assert set(graph.tasks) == {run_window, "register_promotion"}
    assert graph.edges == {(run_window, "register_promotion")}


@pytest.mark.parametrize("dag_id, prefix", DAGS)
def test_outcomes_run_after_the_load_and_before_promotion(monkeypatch, dag_id, prefix):
    monkeypatch.setenv("OUTCOME_EXTRACTION_ENABLED", "1")
    graph = _load_dag(monkeypatch, dag_id)
    run_window = f"{dag_id}_tasks.run_window"
    outcomes = f"{dag_id}_tasks.extract_outcomes"
    assert set(graph.tasks) == {run_window, outcomes, "register_promotion"}
    assert graph.edges == {(run_window, outcomes), (outcomes, "register_promotion")}
    assert graph.tasks[outcomes].kwargs["python_callable"] is linking_tasks.run_window_outcomes
    assert graph.tasks[outcomes].kwargs["op_kwargs"] == {"var_prefix": prefix}


@pytest.mark.parametrize("dag_id, prefix", DAGS)
def test_outcomes_follow_links_when_both_are_on(monkeypatch, dag_id, prefix):
    monkeypatch.setenv("OUTCOME_EXTRACTION_ENABLED", "1")
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "1")
    graph = _load_dag(monkeypatch, dag_id)
    run_window = f"{dag_id}_tasks.run_window"
    links = f"{dag_id}_tasks.extract_links"
    outcomes = f"{dag_id}_tasks.extract_outcomes"
    assert graph.edges == {
        (run_window, links),
        (links, outcomes),
        (outcomes, "register_promotion"),
    }


def test_window_callable_is_a_no_op_with_outcomes_off():
    assert linking_tasks.run_window_outcomes("RS") is None


def test_outcome_artifact_paths():
    assert linking_tasks.outcome_artifact_paths(linking_tasks.SOURCES["echr"], "2026-11-01") == [
        "processed/2026-11-01/outcomes/echr_conclusion.jsonl",
        "processed/2026-11-01/outcomes/echr_status.jsonl",
    ]
    datasets = {
        e.dataset for extractors in linking_tasks.CONTEXT_EXTRACTORS.values() for e in extractors
    }
    from data_extraction.case_context.artifact import DATASETS

    assert datasets == set(DATASETS)


# ---------------------------------------------------------------------------
# fixtures in the scratch database
# ---------------------------------------------------------------------------


def add_echr(
    conn,
    ecli,
    item_id,
    doctype,
    branch,
    decided,
    conclusion=None,
    violation=None,
    appno=None,
    docname=None,
):
    case_id = add_case(conn, ecli=ecli, decided=decided, sources=("ECHR",))
    execute(conn, "UPDATE cle_v2.cases SET item_id = %s WHERE id = %s", (item_id, case_id))
    execute(
        conn,
        """INSERT INTO cle_v2.echr_document (item_id, case_id, language, doctype, doctype_branch,
               docname, judgement_date, conclusion, violation)
           VALUES (%s, %s, 'en', %s, %s, %s, %s, %s, %s)""",
        (item_id, case_id, doctype, branch, docname, decided, conclusion, violation),
    )
    if appno:
        execute(
            conn,
            "INSERT INTO cle_v2.echr_document_appno (item_id, appno, source) "
            "VALUES (%s, %s, 'appno')",
            (item_id, appno),
        )
    return case_id


def add_cjeu(conn, ecli, celex, decided, proc_type):
    case_id = add_case(conn, ecli=ecli, celex=celex, decided=decided)
    execute(
        conn,
        "INSERT INTO cle_v2.cjeu_document (case_id, celex_id, ecli, proc_type) "
        "VALUES (%s, %s, %s, %s)",
        (case_id, celex, ecli, proc_type),
    )
    return case_id


def add_rs(conn, ecli, decided, text=None, document_type="Uitspraak"):
    case_id = add_case(conn, ecli=ecli, decided=decided, sources=("RS",))
    execute(
        conn,
        "INSERT INTO cle_v2.rs_document (case_id, date_decision, document_type) "
        "VALUES (%s, %s, %s)",
        (case_id, decided, document_type),
    )
    if text is not None:
        execute(
            conn,
            """INSERT INTO cle_v2.case_text (case_id, language, fulltext, source)
               VALUES (%s, 'nl', %s, 'RECHTSPRAAK')""",
            (case_id, text),
        )
    return case_id


def add_link(conn, source_id, target_id, relation, dataset):
    execute(
        conn,
        """INSERT INTO cle_v2.case_citation (source_case_id, target_case_id, relation_type,
               source_dataset) VALUES (%s, %s, %s, %s)""",
        (source_id, target_id, relation, dataset),
    )


def _records(path):
    return list(read_jsonl(path))


# ---------------------------------------------------------------------------
# ECtHR
# ---------------------------------------------------------------------------


@needs_db
def test_echr_outcomes_and_statuses_load_insert_only(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    chamber = add_echr(
        conn,
        ME_CHAMBER,
        "001-000001",
        "HEJUD",
        "CHAMBER",
        date(2014, 6, 26),
        conclusion="Violation of Article 3 - Prohibition of torture (Article 3 - Expulsion)",
        violation="3",
        appno="71398/12",
    )
    gc = add_echr(
        conn,
        ME_GC,
        "001-000002",
        "HEJUD",
        "GRANDCHAMBER",
        date(2015, 4, 8),
        conclusion="Struck out of the list",
        appno="71398/12",
    )

    out = tmp_path / "echr_conclusion.jsonl"
    written, stats = echr_outcomes.extract(conn, id_range=(None, None), out_path=out)
    records = _records(out)
    assert written == 2
    assert {(r.case.ecli, r.scope, r.article, r.outcome) for r in records} == {
        (ME_CHAMBER, "article", "3", "violation"),
        (ME_GC, "overall", None, "struck_out"),
    }

    status_out = tmp_path / "echr_status.jsonl"
    written, _ = case_status.extract_echr(conn, case_ids=[gc], out_path=status_out)
    statuses = {(r.case.ecli, r.status, r.status_date) for r in _records(status_out)}
    assert statuses == {
        (ME_GC, "struck_out", date(2015, 4, 8)),
        (ME_GC, "final", date(2015, 4, 8)),
        (ME_CHAMBER, "referred_to_grand_chamber", None),
    }

    first = outcome_loader.load_artifact(conn, out)
    assert first == {"echr_conclusion": {"inserted": 2}}
    assert outcome_loader.load_artifact(conn, out) == {"echr_conclusion": {"existing": 2}}
    assert outcome_loader.load_artifact(conn, status_out) == {"echr_status": {"inserted": 3}}
    rows = execute(
        conn,
        """SELECT s.case_id, s.status, s.related_case_id, s.confidence
             FROM cle_v2.case_status s ORDER BY s.case_id, s.status""",
    )
    assert rows == [
        (chamber, "referred_to_grand_chamber", gc, pytest.approx(0.85)),
        (gc, "final", None, pytest.approx(0.95)),
        (gc, "struck_out", None, pytest.approx(0.95)),
    ]
    raw = execute(
        conn, "SELECT raw_value, confidence FROM cle_v2.case_outcome WHERE case_id = %s", (chamber,)
    )
    assert raw == [
        (
            "conclusion: Violation of Article 3 - Prohibition of torture (Article 3 - Expulsion) "
            "| violation: 3",
            pytest.approx(0.97),
        )
    ]
    # one DELETE per dataset removes it
    execute(conn, "DELETE FROM cle_v2.case_status WHERE source_dataset = 'echr_status'")
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_status")[0][0] == 0


@needs_db
def test_loader_counts_missing_cases_and_related(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    add_echr(conn, ME_CHAMBER, "001-000001", "HEJUD", "CHAMBER", date(2014, 6, 26))
    path = tmp_path / "x.jsonl"
    lines = [
        {
            "kind": "status",
            "case": {"ecli": ME_CHAMBER},
            "status": "referred_to_grand_chamber",
            "status_date": None,
            "related": {"ecli": ME_GC},
            "source_dataset": "echr_status",
            "extractor_version": "t",
        },
        {
            "kind": "outcome",
            "case": {"ecli": "ECLI:CE:ECHR:1999:0101JUD000000199"},
            "scope": "overall",
            "article": None,
            "outcome": "inadmissible",
            "source_dataset": "echr_conclusion",
            "extractor_version": "t",
        },
        {
            "kind": "outcome",
            "case": {"item_id": "001-000001"},
            "scope": "article",
            "article": "3",
            "outcome": "violation",
            "source_dataset": "echr_conclusion",
            "extractor_version": "t",
        },
        {
            "kind": "outcome",
            "case": {"ecli": ME_CHAMBER},
            "scope": "article",
            "article": "3",
            "outcome": "violation",
            "source_dataset": "echr_conclusion",
            "extractor_version": "t",
        },
    ]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert outcome_loader.load_artifact(conn, path) == {
        "echr_status": {"related_missing": 1},
        "echr_conclusion": {"case_missing": 1, "inserted": 1, "existing": 1},
    }


@needs_db
def test_loader_without_the_0013_confidence_column(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    execute(conn, "DROP VIEW cle_v2.case_procedural_link")
    execute(conn, "ALTER TABLE cle_v2.case_outcome DROP COLUMN confidence")
    add_cjeu(
        conn,
        "ECLI:EU:T:2018:5",
        "62016TJ0005",
        date(2018, 1, 5),
        "Action for annulment - unfounded",
    )
    out = tmp_path / "cjeu_proc_type.jsonl"
    cjeu_outcomes.extract(conn, out_path=out)
    assert outcome_loader.load_artifact(conn, out) == {"cjeu_proc_type": {"inserted": 1}}


# ---------------------------------------------------------------------------
# CJEU
# ---------------------------------------------------------------------------


@needs_db
def test_cjeu_outcomes_and_overturned_on_appeal(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    general_court = add_cjeu(
        conn,
        "ECLI:EU:T:2018:5",
        "62016TJ0005",
        date(2018, 1, 5),
        "Action for annulment - successful",
    )
    opinion = add_cjeu(
        conn, "ECLI:EU:C:2019:900", "62018CC0010", date(2019, 9, 1), "Appeal - successful"
    )
    appeal = add_cjeu(
        conn, "ECLI:EU:C:2020:10", "62018CJ0010", date(2020, 1, 10), "Appeal - successful"
    )
    add_cjeu(
        conn,
        "ECLI:EU:C:2020:11",
        "62019CJ0011",
        date(2020, 1, 11),
        "Reference for a preliminary ruling",
    )
    add_link(conn, appeal, general_court, "appeal_of", "cellar_relation_resolved")

    out = tmp_path / "cjeu_proc_type.jsonl"
    written, stats = cjeu_outcomes.extract(conn, out_path=out)
    assert written == 2  # the opinion and the unsuffixed ruling get none
    assert stats["not_a_decision"] == 1 and stats["no_suffix"] == 1
    assert outcome_loader.load_artifact(conn, out) == {"cjeu_proc_type": {"inserted": 2}}
    rows = execute(
        conn, "SELECT case_id, outcome, raw_value FROM cle_v2.case_outcome ORDER BY case_id"
    )
    assert rows == [
        (general_court, "successful", "Action for annulment - successful"),
        (appeal, "successful", "Appeal - successful"),
    ]
    # cjeu_document is untouched: procedure_result stays NULL, proc_type raw
    assert execute(
        conn, "SELECT count(*) FROM cle_v2.cjeu_document WHERE procedure_result IS NOT NULL"
    ) == [(0,)]

    status_out = tmp_path / "cjeu_appeal_status.jsonl"
    case_status.extract_cjeu(conn, case_ids=[appeal, opinion], out_path=status_out)
    assert outcome_loader.load_artifact(conn, status_out) == {"cjeu_appeal_status": {"inserted": 1}}
    assert execute(
        conn, "SELECT case_id, status, status_date, related_case_id FROM cle_v2.case_status"
    ) == [(general_court, "overturned", date(2020, 1, 10), appeal)]


# ---------------------------------------------------------------------------
# Rechtspraak (behind RS_DICTUM_ENABLED)
# ---------------------------------------------------------------------------

HOF_TEXT = """Beslissing
Het hof:
bekrachtigt het vonnis waarvan beroep.
Dit arrest is gewezen door ..."""  # ILLUSTRATIVE

HR_TEXT = """4 Beslissing
De Hoge Raad:
- vernietigt het arrest van het gerechtshof;
- verwijst het geding naar een ander gerechtshof.
Dit arrest is gewezen door ..."""  # ILLUSTRATIVE


@needs_db
def test_rs_dictum_and_overturned(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    hof = add_rs(conn, "ECLI:NL:GHAMS:2020:1", date(2020, 3, 1), HOF_TEXT)
    hr = add_rs(conn, "ECLI:NL:HR:2021:1", date(2021, 6, 1), HR_TEXT)
    add_rs(conn, "ECLI:NL:PHR:2021:1", date(2021, 2, 1), HR_TEXT, document_type="Conclusie")
    # stored from the earlier decision, as the legacy formal relations often are
    add_link(conn, hof, hr, "cassatie", "rs_formal_relation")

    out = tmp_path / "rs_dictum.jsonl"
    rs_dictum.extract(conn, out_path=out)
    assert {(r.case.ecli, r.outcome) for r in _records(out)} == {
        ("ECLI:NL:GHAMS:2020:1", "dismissed"),
        ("ECLI:NL:HR:2021:1", "quashed"),
    }
    status_out = tmp_path / "rs_appeal_status.jsonl"
    case_status.extract_rs(conn, case_ids=[hr], out_path=status_out)
    assert outcome_loader.load_artifact(conn, status_out) == {"rs_appeal_status": {"inserted": 1}}
    assert execute(conn, "SELECT case_id, status, related_case_id FROM cle_v2.case_status") == [
        (hof, "overturned", hr)
    ]


@needs_db
def test_rs_appeal_status_ignores_conclusies(scratch_db, tmp_path):  # noqa: F811
    """A conclusie linked by a formal relation is neither the appeal nor the
    decision under appeal (ILLUSTRATIVE ECLIs and texts as above)."""
    conn = scratch_db
    hof = add_rs(conn, "ECLI:NL:GHAMS:2020:1", date(2020, 3, 1), HOF_TEXT)
    phr = add_rs(conn, "ECLI:NL:PHR:2021:1", date(2021, 2, 1), HR_TEXT, document_type="Conclusie")
    hr = add_rs(conn, "ECLI:NL:HR:2021:1", date(2021, 6, 1), HR_TEXT)
    add_link(conn, hof, phr, "cassatie", "rs_formal_relation")  # conclusie as the appeal
    add_link(conn, phr, hr, "cassatie", "rs_formal_relation")  # conclusie as the earlier one

    status_out = tmp_path / "rs_appeal_status.jsonl"
    case_status.extract_rs(conn, case_ids=[phr, hr], out_path=status_out)
    assert _records(status_out) == []


@needs_db
def test_referral_relates_to_the_earliest_grand_chamber_merits_judgment(
    scratch_db, tmp_path  # noqa: F811
):
    """ILLUSTRATIVE ECLIs: a Chamber judgment, the Grand Chamber merits
    judgment and a later Grand Chamber just-satisfaction judgment."""
    conn = scratch_db
    chamber = add_echr(
        conn,
        "ECLI:CE:ECHR:2010:0101JUD000000110",
        "001-000011",
        "HEJUD",
        "CHAMBER",
        date(2010, 1, 1),
        appno="1/10",
    )
    merits = add_echr(
        conn,
        "ECLI:CE:ECHR:2012:0101JUD000000110",
        "001-000012",
        "HEJUD",
        "GRANDCHAMBER",
        date(2012, 1, 1),
        appno="1/10",
        docname="CASE OF A v. B",
    )
    satisfaction = add_echr(
        conn,
        "ECLI:CE:ECHR:2014:0101JUD000000110",
        "001-000013",
        "HEJUD",
        "GRANDCHAMBER",
        date(2014, 1, 1),
        appno="1/10",
        docname="CASE OF A v. B (JUST SATISFACTION)",
    )
    status_out = tmp_path / "echr_status.jsonl"
    case_status.extract_echr(conn, case_ids=[satisfaction, merits], out_path=status_out)
    case_status.extract_echr(conn, case_ids=[satisfaction], out_path=tmp_path / "only.jsonl")
    referred = [r for r in _records(status_out) if r.status == "referred_to_grand_chamber"]
    assert [(r.case.ecli, r.related.ecli) for r in referred] == [
        ("ECLI:CE:ECHR:2010:0101JUD000000110", "ECLI:CE:ECHR:2012:0101JUD000000110")
    ]
    only = [r for r in _records(tmp_path / "only.jsonl") if r.status == "referred_to_grand_chamber"]
    assert only == []
    assert chamber


@needs_db
def test_rs_extractors_are_skipped_without_their_flag(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    add_rs(conn, "ECLI:NL:HR:2021:1", date(2021, 6, 1), HR_TEXT)
    statuses, datasets = linking_tasks.extract_outcomes(
        conn, linking_tasks.SOURCES["rechtspraak"], tmp_path, id_range=(None, None)
    )
    assert statuses["rs_dictum"]["status"] == "skipped"
    assert datasets == {"rs_dictum": {"records": 0}, "rs_appeal_status": {"records": 0}}
    assert (tmp_path / "rs_dictum.jsonl").read_text() == ""
    assert (tmp_path / "rs_appeal_status.jsonl").read_text() == ""


# ---------------------------------------------------------------------------
# weekly month and backfill CLI
# ---------------------------------------------------------------------------


@needs_db
def test_echr_month_writes_every_file_and_loads(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    conn = scratch_db
    monkeypatch.setenv("OUTCOME_EXTRACTION_ENABLED", "1")
    add_echr(
        conn,
        ME_GC,
        "001-000002",
        "HEJUD",
        "GRANDCHAMBER",
        date(2015, 4, 8),
        conclusion="Struck out of the list",
        appno="71398/12",
    )
    month = tmp_path / "processed" / "2015-04-01"
    month.mkdir(parents=True)
    (month / "ECHR_metadata_clean.csv").write_text("document_id\n001-000002\n")
    counts = linking_tasks.run_month_outcomes(
        conn, linking_tasks.SOURCES["echr"], str(tmp_path), "2015-04-01"
    )
    assert counts["case_ids"] == 1
    assert counts["datasets"]["echr_conclusion"] == {"records": 1, "load": {"inserted": 1}}
    assert counts["datasets"]["echr_status"] == {"records": 2, "load": {"inserted": 2}}
    for path in linking_tasks.outcome_artifact_paths(linking_tasks.SOURCES["echr"], "2015-04-01"):
        assert (tmp_path / path).exists()
    assert (month / "outcomes" / "_counts.ECHR.json").exists()


@needs_db
def test_outcome_backfill_cli(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    conn = scratch_db
    first = add_cjeu(
        conn,
        "ECLI:EU:T:2018:5",
        "62016TJ0005",
        date(2018, 1, 5),
        "Action for annulment - unfounded",
    )
    add_cjeu(
        conn,
        "ECLI:EU:T:2018:6",
        "62016TJ0006",
        date(2018, 1, 6),
        "Action for annulment - inadmissible",
    )
    monkeypatch.setenv("OUTCOME_TEST_DSN", DSN.rpartition("/")[0] + "/" + conn.info.dbname)
    out = tmp_path / "out"
    argv = [
        "outcomes",
        "--dsn-env",
        "OUTCOME_TEST_DSN",
        "--source",
        "cellar",
        "--from-id",
        str(first),
        "--to-id",
        str(first),
        "--out",
        str(out),
    ]
    assert linking_tasks.main(argv) == 0
    assert len(_records(out / "cjeu_proc_type.jsonl")) == 1
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_outcome") == [(0,)]  # read only
    assert linking_tasks.main(argv + ["--load"]) == 0
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_outcome") == [(1,)]
    counts = json.loads((out / "_counts.CELLAR.json").read_text())
    assert counts["datasets"]["cjeu_proc_type"]["load"] == {"inserted": 1}


# ---------------------------------------------------------------------------
# timeline (R5.3)
# ---------------------------------------------------------------------------


@needs_db
def test_case_timeline(scratch_db):  # noqa: F811
    conn = scratch_db
    rechtbank = add_rs(conn, "ECLI:NL:RBDHA:2015:1", date(2015, 1, 1))
    referral = add_rs(conn, "ECLI:NL:RVS:2017:1098", date(2017, 4, 19))
    opinion = add_case(
        conn, ecli="ECLI:EU:C:2018:639", celex="62017CC0221", decided=date(2018, 7, 12)
    )
    ruling = add_case(
        conn, ecli="ECLI:EU:C:2019:189", celex="62017CJ0221", decided=date(2019, 3, 12)
    )
    follow_up = add_rs(conn, "ECLI:NL:RVS:2020:423", date(2020, 2, 12))
    unrelated = add_rs(conn, "ECLI:NL:RVS:2020:1", date(2020, 1, 1))
    # first instance -> appeal stored from the later decision (date-ordered)
    add_link(conn, referral, rechtbank, "hogerberoep", "rs_formal_relation")
    add_link(conn, referral, ruling, "preliminary_reference", "cellar_national_judgement")
    add_link(conn, opinion, ruling, "opinion_of", "cjeu_ag_link")
    add_link(conn, follow_up, ruling, "national_follow_up", "cellar_national_judgement")
    add_link(conn, follow_up, ruling, "cites", "rs_text_ecli")  # a citation, not a step
    add_link(conn, unrelated, follow_up, "replaced_by", "rs_formal_relation")  # identity
    sql = TIMELINE_SQL.read_text()
    rows = execute(conn, sql, {"case_id": ruling, "max_depth": 6})
    steps = [(r[1], r[5], r[8]) for r in rows]
    assert steps == [
        ("ECLI:NL:RBDHA:2015:1", "ECLI:NL:RVS:2017:1098", "appeal"),
        ("ECLI:NL:RVS:2017:1098", "ECLI:EU:C:2019:189", "referral"),
        ("ECLI:EU:C:2018:639", "ECLI:EU:C:2019:189", "opinion"),
        ("ECLI:EU:C:2019:189", "ECLI:NL:RVS:2020:423", "follow_up"),
    ]
    # from the first instance the same chain is found; depth limits the walk
    assert len(execute(conn, sql, {"case_id": rechtbank, "max_depth": 6})) == 4
    assert [r[8] for r in execute(conn, sql, {"case_id": rechtbank, "max_depth": 1})] == ["appeal"]
    assert execute(conn, sql, {"case_id": unrelated, "max_depth": 6}) == []
