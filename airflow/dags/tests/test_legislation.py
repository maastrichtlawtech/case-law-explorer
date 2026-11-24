"""
EU, Council of Europe and UN acts in legislation (R3.1), ECHR articles as
provisions (R3.7), resolved rs_lido_sqlite law references (R3.5).

The research files hold no real legislation references, ECHR article codes or
RS law references, so every case, CELEX reference and article code below is an
illustrative value in the documented formats, not data taken from a decision.
The DB tests run only when CLE_TEST_PG_DSN is set (tests/linking_db.py).
"""

import json
from collections import Counter

import pytest

import linking_tasks
from data_extraction.legislation import acts, catalog, echr_articles
from data_extraction.legislation.celex import parse_celex
from data_extraction.legislation.law_reference import LawReferenceRecord
from data_extraction.linking.artifact import ArtifactError
from data_loading import legislation_loader
from tests.linking_db import DSN, add_case, execute, needs_db, scratch_db  # noqa: F401
from tests.test_linking_tasks import _FakeGroup, _FakeTask, _Graph, _load_dag, _processed

LEGISLATION_ENV = ("LEGISLATION_EXTERNAL_ENABLED", "LINK_EXTRACTION_ENABLED")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in LEGISLATION_ENV + ("SEGMENTATION_API_URL", "CASE_IDENTIFIER_ENABLED"):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# CELEX
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, act, sector, document_type, year, subdivision",
    [
        ("32016R0679", "32016R0679", "3", "regulation", 2016, None),
        (" celex:32011L0095 ", "32011L0095", "3", "directive", 2011, None),
        ("32016R0679R(02)", "32016R0679", "3", "regulation", 2016, "R(02)"),
        ("32003D0048(01)", "32003D0048(01)", "3", "decision", 2003, None),
        ("21994A1223(01)", "21994A1223(01)", "2", "international_agreement", 1994, None),
        ("12008E267", "12008E", "1", "treaty", 2008, "267"),
        ("11957E085", "11957E", "1", "treaty", 1957, "085"),
        ("12016M/PRO/01", "12016M", "1", "treaty", 2016, "PRO/01"),
        ("12016P/TXT", "12016P", "1", "treaty", 2016, None),
        ("31977L0388", "31977L0388", "3", "directive", 1977, None),
        ("32004Z0001", "32004Z0001", "3", "celex_3Z", 2004, None),
    ],
)
def test_parse_celex(value, act, sector, document_type, year, subdivision):
    parsed = parse_celex(value)
    assert (parsed.act, parsed.sector, parsed.document_type, parsed.year, parsed.subdivision) == (
        act,
        sector,
        document_type,
        year,
        subdivision,
    )


@pytest.mark.parametrize(
    "value", ["62019CJ0001", "52020PC0001", "02016R0679-20160504", "C-221/17", "", None, "3201R"]
)
def test_parse_celex_refuses_everything_else(value):
    assert parse_celex(value) is None


def test_act_for_counts_what_it_skips():
    stats = Counter()
    assert catalog.act_for("62012CJ0199", stats) is None
    assert catalog.act_for("52020PC0001", stats) is None
    assert catalog.act_for("not a celex", stats) is None
    record = catalog.act_for("12008E267", stats)
    assert record.key == ("celex", "12008E") and record.enacted_year == 2008
    assert stats == Counter(
        skipped_sector_6=1, skipped_sector_5=1, unparsed=1, sector_1=1, with_subdivision=1
    )


# ---------------------------------------------------------------------------
# curated fixture
# ---------------------------------------------------------------------------


def test_fixture_is_valid_and_complete():
    records = acts.curated_acts()
    assert len(records) == 63
    by_key = acts.curated_by_key()
    for key in [
        ("celex", "12016E"),
        ("celex", "12016M"),
        ("celex", "11957E"),
        ("celex", "11965F"),
        ("celex", "12016P"),
        ("celex", "12012J"),
        ("coe_treaty", "005"),
        ("coe_treaty", "009"),
        ("un_treaty", "V-2"),
        ("un_treaty", "IV-11"),
    ]:
        assert key in by_key
    aliases = {a: r.key for r in records for a in r.aliases}
    for alias, key in {
        "VWEU": ("celex", "12016E"),
        "TFEU": ("celex", "12016E"),
        "AEUV": ("celex", "12016E"),
        "TFUE": ("celex", "12016E"),
        "VEU": ("celex", "12016M"),
        "TEU": ("celex", "12016M"),
        "EVRM": ("coe_treaty", "005"),
        "ECHR": ("coe_treaty", "005"),
        "EHRM-verdrag": ("coe_treaty", "005"),
        "CEDH": ("coe_treaty", "005"),
        "Handvest": ("celex", "12016P"),
        "Charter": ("celex", "12016P"),
        "Vluchtelingenverdrag": ("un_treaty", "V-2"),
        "IVRK": ("un_treaty", "IV-11"),
    }.items():
        assert aliases[alias] == key, alias
    # every alias names one act
    assert len(aliases) == sum(len(r.aliases) for r in records)
    with open(acts.FIXTURE, encoding="utf-8") as handle:
        assert "references" in json.load(handle)["_source"]


def test_echr_protocol_numbers():
    protocols = acts.echr_protocols()
    assert protocols[0].identifier == "005"
    assert {n: protocols[n].identifier for n in (1, 4, 6, 7, 12, 13)} == {
        1: "009",
        4: "046",
        6: "114",
        7: "117",
        12: "177",
        13: "187",
    }


def test_act_record_round_trip_and_validation():
    record = acts.ActRecord.from_dict(
        {
            "scheme": "celex",
            "identifier": "32016R0679",
            "jurisdiction": "EU",
            "document_type": "regulation",
            "enacted_year": 2016,
            "source_dataset": "legislation_cellar",
            "extractor_version": "test",
        }
    )
    assert acts.ActRecord.from_dict(record.to_dict()) == record
    for bad in (
        {"scheme": "bwb"},
        {"jurisdiction": "NL"},
        {"enacted_date": "2016-04-27", "enacted_year": 2015},
        {"source_dataset": "x"},
        {"surprise": 1},
    ):
        with pytest.raises(ArtifactError):
            acts.ActRecord.from_dict({**record.to_dict(), **bad})


# ---------------------------------------------------------------------------
# ECHR article codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code, expected",
    [
        ("6", [(0, "6", None, "6")]),
        ("6-1", [(0, "6", "1", "6-1")]),
        ("6-3-c", [(0, "6", "3(c)", "6-3-C")]),
        ("P1-1", [(1, "1", None, "P1-1")]),
        ("p1-1-1", [(1, "1", "1", "P1-1-1")]),
        (" P12-1 ", [(12, "1", None, "P12-1")]),
        ("14+8", [(0, "14", None, "14"), (0, "8", None, "8")]),
        ("14+P1-1", [(0, "14", None, "14"), (1, "1", None, "P1-1")]),
        ("35-3-a", [(0, "35", "3(a)", "35-3-A")]),
        ("06-01", [(0, "6", "1", "06-01")]),
    ],
)
def test_parse_article_code(code, expected):
    refs, bad = echr_articles.parse_article_code(code)
    assert bad == []
    assert [(r.protocol, r.article, r.paragraph, r.part) for r in refs] == expected


@pytest.mark.parametrize("code", ["P1", "Art. 6", "6-1-c-2", "", "41bis"])
def test_parse_article_code_refuses(code):
    refs, bad = echr_articles.parse_article_code(code)
    assert refs == [] and bad


def test_records_merge_per_case_and_count_problems():
    protocols = acts.echr_protocols()
    rows = [
        (1, "ECLI:CE:ECHR:2004:0101JUD001234500", "001-1", "violation", "6-1"),
        (1, "ECLI:CE:ECHR:2004:0101JUD001234500", "001-1", "violation", "14+8"),
        (1, "ECLI:CE:ECHR:2004:0101JUD001234500", "001-1", "applied", "8"),
        # the French version of the same case repeats the codes
        (1, "ECLI:CE:ECHR:2004:0101JUD001234500", "001-1", "violation", "8"),
        (1, "ECLI:CE:ECHR:2004:0101JUD001234500", "001-1", "violation", "P99-1"),
        (1, "ECLI:CE:ECHR:2004:0101JUD001234500", "001-1", "violation", "Art. 3"),
        (2, None, "001-9", "nonviolation", "P1-1"),
        (3, None, None, "applied", "3"),
    ]
    stats = Counter()
    records = echr_articles.records_for_rows(rows, protocols, stats)
    keys = sorted(
        (r.source.ecli or r.source.item_id, r.identifier, r.article, r.paragraph, r.role)
        for r in records
    )
    assert keys == [
        ("001-9", "009", "1", None, "nonviolation"),
        ("ECLI:CE:ECHR:2004:0101JUD001234500", "005", "14", None, "violation"),
        ("ECLI:CE:ECHR:2004:0101JUD001234500", "005", "6", "1", "violation"),
        ("ECLI:CE:ECHR:2004:0101JUD001234500", "005", "8", None, "applied"),
        ("ECLI:CE:ECHR:2004:0101JUD001234500", "005", "8", None, "violation"),
    ]
    eight = [r for r in records if r.article == "8" and r.role == "violation"][0]
    assert (eight.raw_reference, eight.raw_subdivision) == ("14+8", "8")
    assert stats["merged"] == 1
    assert stats["unknown_protocol"] == 1
    assert stats["unparsed"] == 1
    assert stats["no_natural_key"] == 1


def test_law_reference_record_validation():
    value = {
        "source": {"item_id": "001-1"},
        "act": {"scheme": "coe_treaty", "identifier": "005"},
        "article": "6",
        "paragraph": "1",
        "role": "violation",
        "source_dataset": "echr_article",
        "extractor_version": "test",
    }
    record = LawReferenceRecord.from_dict(value)
    assert LawReferenceRecord.from_dict(record.to_dict()) == record
    for bad in (
        {"source_dataset": "rs_text_ecli"},
        {"article": None},
        {"act": {"scheme": "bwb", "identifier": "BWBR0001"}},
        {"extra": 1},
    ):
        with pytest.raises(ArtifactError):
            LawReferenceRecord.from_dict({**value, **bad})


# ---------------------------------------------------------------------------
# DAG wiring
# ---------------------------------------------------------------------------

DAGS = [("rechtspraak_etl", "RS"), ("cellar_etl", "CELLAR"), ("echr_etl", "ECHR")]


@pytest.mark.parametrize("dag_id, prefix", DAGS)
def test_dag_unchanged_with_the_flag_off(monkeypatch, dag_id, prefix):
    graph = _load_dag(monkeypatch, dag_id)
    run_window = f"{dag_id}_tasks.run_window"
    assert set(graph.tasks) == {run_window, "register_promotion"}
    assert graph.edges == {(run_window, "register_promotion")}


@pytest.mark.parametrize("dag_id, prefix", DAGS)
def test_legislation_task_runs_before_promotion(monkeypatch, dag_id, prefix):
    monkeypatch.setenv("LEGISLATION_EXTERNAL_ENABLED", "1")
    graph = _load_dag(monkeypatch, dag_id)
    run_window = f"{dag_id}_tasks.run_window"
    task = f"{dag_id}_tasks.extract_legislation"
    if prefix == "RS":  # no legislation files for Rechtspraak
        assert set(graph.tasks) == {run_window, "register_promotion"}
        return
    assert graph.edges == {(run_window, task), (task, "register_promotion")}
    assert graph.tasks[task].kwargs["python_callable"] is linking_tasks.run_window_legislation
    assert graph.tasks[task].kwargs["op_kwargs"] == {"var_prefix": prefix}


def test_legislation_follows_links_when_both_are_on(monkeypatch):
    monkeypatch.setenv("LEGISLATION_EXTERNAL_ENABLED", "1")
    monkeypatch.setenv("LINK_EXTRACTION_ENABLED", "1")
    graph = _load_dag(monkeypatch, "echr_etl")
    assert graph.edges == {
        ("echr_etl_tasks.run_window", "echr_etl_tasks.extract_links"),
        ("echr_etl_tasks.extract_links", "echr_etl_tasks.extract_legislation"),
        ("echr_etl_tasks.extract_legislation", "register_promotion"),
    }


def test_group_without_links_ignores_the_legislation_flag(monkeypatch):
    import etl_factory

    monkeypatch.setenv("LEGISLATION_EXTERNAL_ENABLED", "1")
    graph = _Graph()
    monkeypatch.setattr(_FakeTask, "graph", graph)
    monkeypatch.setattr(etl_factory, "PythonOperator", _FakeTask)
    monkeypatch.setattr(etl_factory, "TaskGroup", _FakeGroup)
    etl_factory.build_monthly_task_group(None, "x", "ECHR", lambda **k: None)
    assert set(graph.tasks) == {"x_tasks.run_window"}


def test_window_callable_is_a_no_op_with_the_flag_off():
    assert linking_tasks.run_window_legislation("ECHR") is None


def test_promoter_paths():
    month = "2024-01-01"
    paths = {
        name: linking_tasks.legislation_artifact_paths(source, month)
        for name, source in linking_tasks.SOURCES.items()
    }
    assert paths == {
        "rechtspraak": [],
        "cellar": [(f"processed/{month}/links/legislation_external.jsonl", "legislation")],
        "echr": [(f"processed/{month}/links/echr_article.jsonl", "law_references")],
    }


# ---------------------------------------------------------------------------
# against a scratch database
# ---------------------------------------------------------------------------


def _add_echr_case(conn, ecli, item_ids, codes):
    case = execute(
        conn,
        "INSERT INTO cle_v2.cases (ecli, item_id, sources) VALUES (%s, %s, '{ECHR}') RETURNING id",
        (ecli, item_ids[0]),
    )[0][0]
    for item_id in item_ids:
        execute(
            conn,
            """INSERT INTO cle_v2.echr_document (item_id, case_id, language, doctype)
               VALUES (%s, %s, 'en', 'HEJUD')""",
            (item_id, case),
        )
    for item_id, kind, code in codes:
        execute(
            conn,
            "INSERT INTO cle_v2.echr_document_article (item_id, kind, article_code)"
            " VALUES (%s, %s, %s)",
            (item_id, kind, code),
        )
    return case


def _add_cellar_case(conn, ecli, celex, cited, lawrefs):
    case = add_case(conn, ecli, celex)
    for target in cited:
        execute(
            conn,
            """INSERT INTO cle_v2.case_citation (source_case_id, target_celex_raw, relation_type,
                   source_dataset) VALUES (%s, %s, 'cites', 'cellar_sparql')""",
            (case, target),
        )
    for resource, role in lawrefs:
        execute(
            conn,
            """INSERT INTO cle_v2.case_law_reference (case_id, raw_scheme, raw_resource, role,
                   source_dataset) VALUES (%s, 'celex', %s, %s, 'cellar_sparql')""",
            (case, resource, role),
        )
    return case


@needs_db
def test_catalog_extract_and_load(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    first = _add_cellar_case(
        conn,
        "ECLI:EU:C:2019:1",
        "62018CJ0001",
        ["12008E267", "32016R0679", "62010CJ0001", "52020PC0001"],
        [("32016R0679", "interprets"), ("11957E177", "based_on_treaty")],
    )
    _add_cellar_case(conn, "ECLI:EU:C:2019:2", "62018CJ0002", ["31977L0388R(01)"], [])
    out = tmp_path / "legislation_external.jsonl"

    written, stats = catalog.extract(conn, id_range=(first, first), out_path=out)
    records = list(acts.read_acts(out))
    # 12008E267 and 11957E177 name curated acts; the sector 5 and 6 values are skipped
    assert written == len(records) == 63 + 1
    assert stats["acts_in_fixture_referenced"] == 2
    assert stats["skipped_sector_6"] == 1 and stats["skipped_sector_5"] == 1
    assert {r.source_dataset for r in records[:63]} == {"legislation_curated"}
    assert set(records[:63]) == set(acts.curated_acts())
    cellar = {r.identifier: r for r in records if r.source_dataset == "legislation_cellar"}
    assert set(cellar) == {"32016R0679"}
    gdpr = cellar["32016R0679"]
    assert (gdpr.document_type, gdpr.enacted_year, gdpr.title) == ("regulation", 2016, None)

    result = legislation_loader.load_acts_artifact(conn, out)
    assert result["legislation_curated"]["inserted"] == 63
    assert result["legislation_curated"]["aliases_inserted"] == 120
    assert result["legislation_cellar"] == {"inserted": 1}
    again = legislation_loader.load_acts_artifact(conn, out)
    assert again == {
        "legislation_curated": {"existing": 63},
        "legislation_cellar": {"existing": 1},
    }
    rows = execute(
        conn,
        """SELECT l.scheme, l.identifier, l.title, j.iso_code, l.document_type, l.enacted_year,
                  l.source_dataset
             FROM cle_v2.legislation l JOIN cle_v2.jurisdiction j ON j.id = l.jurisdiction_id
            WHERE l.identifier IN ('12016E', '32016R0679', '005', 'V-2') ORDER BY 2""",
    )
    assert rows == [
        (
            "coe_treaty",
            "005",
            acts.curated_by_key()[("coe_treaty", "005")].title,
            "CE",
            "convention",
            1950,
            "legislation_curated",
        ),
        (
            "celex",
            "12016E",
            acts.curated_by_key()[("celex", "12016E")].title,
            "EU",
            "treaty",
            2016,
            "legislation_curated",
        ),
        ("celex", "32016R0679", None, "EU", "regulation", 2016, "legislation_cellar"),
        (
            "un_treaty",
            "V-2",
            "Convention relating to the Status of Refugees",
            "UN",
            "convention",
            1951,
            "legislation_curated",
        ),
    ]
    assert (
        execute(
            conn,
            """SELECT count(*) FROM cle_v2.legislation_alias a
             JOIN cle_v2.legislation l ON l.id = a.legislation_id
            WHERE a.alias = 'VWEU' AND l.identifier = '12016E' AND a.source = 'curated'""",
        )
        == [(1,)]
    )
    # the whole range: the second case adds the corrigendum's act
    catalog.extract(conn, out_path=out)
    assert legislation_loader.load_acts_artifact(conn, out)["legislation_cellar"] == {
        "existing": 1,
        "inserted": 1,
    }
    assert execute(
        conn, "SELECT count(*) FROM cle_v2.legislation WHERE identifier = '31977L0388'"
    ) == [(1,)]


@needs_db
def test_bwb_rows_are_outside_the_external_key(scratch_db):  # noqa: F811
    conn = scratch_db
    for _ in range(2):  # duplicate BWB identifiers stay possible, as today
        execute(
            conn,
            "INSERT INTO cle_v2.legislation (identifier, scheme) VALUES ('BWBR0001854', 'bwb')",
        )
    legislation_loader.load_curated(conn)
    assert legislation_loader.load_curated(conn) == {"legislation_curated": {"existing": 63}}


@needs_db
def test_echr_articles_extract_and_load(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    case = _add_echr_case(
        conn,
        "ECLI:CE:ECHR:2004:0101JUD001234500",
        ["001-1", "001-2"],
        [
            ("001-1", "violation", "6-1"),
            ("001-1", "violation", "6"),
            ("001-1", "applied", "P1-1"),
            ("001-2", "violation", "6-1"),  # same case, other language
            ("001-2", "nonviolation", "14+8"),
            ("001-2", "applied", "P1"),  # not parseable
        ],
    )
    other = _add_echr_case(conn, None, ["001-9"], [("001-9", "violation", "6-1")])
    # an existing provision without source_dataset is never touched
    execute(
        conn,
        """INSERT INTO cle_v2.legal_provision (element_type, article_label, title)
           VALUES ('artikel', '6', 'Artikel 6')""",
    )
    out = tmp_path / "echr_article.jsonl"

    written, stats = echr_articles.extract(conn, id_range=(case, other), out_path=out)
    assert written == 6
    assert stats["unparsed"] == 1

    result = legislation_loader.load_law_reference_artifact(conn, out)
    assert result["echr_article"] == {
        "inserted": 6,
        "provisions_inserted_article": 4,  # 6, 14, 8 of the Convention; 1 of Protocol 1
        "provisions_inserted_paragraph": 1,  # 6 § 1
    }
    # the acts came from the fixture, as the legislation artifact was not loaded
    assert result["legislation_curated"] == {"inserted": 2, "aliases_inserted": 12}
    assert legislation_loader.load_law_reference_artifact(conn, out) == {
        "echr_article": {"existing": 6}
    }
    rows = execute(
        conn,
        """SELECT c.ecli, c.item_id, l.identifier, p.element_type, p.article_label, p.paragraph,
                  parent.article_label, r.role, r.raw_subdivision, r.raw_reference,
                  r.raw_resource, r.legislation_id = p.legislation_id, r.extractor_version
             FROM cle_v2.case_law_reference r
             JOIN cle_v2.cases c ON c.id = r.case_id
             JOIN cle_v2.legal_provision p ON p.id = r.provision_id
             JOIN cle_v2.legislation l ON l.id = p.legislation_id
             LEFT JOIN cle_v2.legal_provision parent ON parent.id = p.parent_id
            WHERE r.source_dataset = 'echr_article'
            ORDER BY c.id, l.identifier, p.article_label, p.paragraph NULLS FIRST, r.role""",
    )
    ecli = "ECLI:CE:ECHR:2004:0101JUD001234500"
    version = "echr_article/1.0.0"
    assert rows == [
        (
            ecli,
            "001-1",
            "005",
            "article",
            "14",
            None,
            None,
            "nonviolation",
            "14",
            "14+8",
            None,
            True,
            version,
        ),
        (
            ecli,
            "001-1",
            "005",
            "article",
            "6",
            None,
            None,
            "violation",
            "6",
            "6",
            None,
            True,
            version,
        ),
        (
            ecli,
            "001-1",
            "005",
            "paragraph",
            "6",
            "1",
            "6",
            "violation",
            "6-1",
            "6-1",
            None,
            True,
            version,
        ),
        (
            ecli,
            "001-1",
            "005",
            "article",
            "8",
            None,
            None,
            "nonviolation",
            "8",
            "14+8",
            None,
            True,
            version,
        ),
        (
            ecli,
            "001-1",
            "009",
            "article",
            "1",
            None,
            None,
            "applied",
            "P1-1",
            "P1-1",
            None,
            True,
            version,
        ),
        (
            None,
            "001-9",
            "005",
            "paragraph",
            "6",
            "1",
            "6",
            "violation",
            "6-1",
            "6-1",
            None,
            True,
            version,
        ),
    ]
    assert execute(
        conn, "SELECT count(*) FROM cle_v2.legal_provision WHERE source_dataset IS NULL"
    ) == [(1,)]


@needs_db
def test_law_reference_with_missing_source_or_unknown_act(scratch_db):  # noqa: F811
    conn = scratch_db
    base = {
        "act": {"scheme": "coe_treaty", "identifier": "005"},
        "article": "3",
        "role": "violation",
        "source_dataset": "echr_article",
        "extractor_version": "test",
    }
    add_case(conn, "ECLI:CE:ECHR:2010:0101JUD000000110", sources=("ECHR",))
    records = [
        LawReferenceRecord.from_dict({**base, "source": {"ecli": "ECLI:CE:ECHR:2099:1"}}),
        LawReferenceRecord.from_dict(
            {
                **base,
                "source": {"ecli": "ECLI:CE:ECHR:2010:0101JUD000000110"},
                "act": {"scheme": "coe_treaty", "identifier": "999"},
            }
        ),
    ]
    result = legislation_loader.load_law_references(conn, records)
    assert result["echr_article"] == {"source_missing": 1, "act_missing": 1}


@needs_db
def test_legislation_month_and_backfill_cli(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    conn = scratch_db
    case = _add_echr_case(
        conn, "ECLI:CE:ECHR:2004:0101JUD001234500", ["001-1"], [("001-1", "violation", "3")]
    )
    folder = _processed(tmp_path, "2024-01-01", "ECHR_metadata_clean.csv", "document_id", ["001-1"])
    source = linking_tasks.SOURCES["echr"]

    counts = linking_tasks.run_legislation_month(conn, source, str(tmp_path), "2024-01-01")
    assert counts["outputs"]["echr_article"]["records"] == 1
    assert counts["outputs"]["echr_article"]["load"]["echr_article"] == {
        "inserted": 1,
        "provisions_inserted_article": 1,
    }
    assert (folder / "links" / "echr_article.jsonl").exists()
    assert json.loads((folder / "links" / "_legislation_counts.ECHR.json").read_text())
    assert (
        linking_tasks.run_legislation_month(
            conn, linking_tasks.SOURCES["rechtspraak"], str(tmp_path), "2024-01-01"
        )
        is None
    )

    monkeypatch.setenv("LEG_TEST_DSN", DSN.rpartition("/")[0] + "/" + conn.info.dbname)
    out = tmp_path / "backfill"
    argv = ["legislation-backfill", "--dsn-env", "LEG_TEST_DSN", "--source", "cellar"]
    argv += ["--from-id", str(case), "--to-id", str(case), "--out", str(out)]
    assert linking_tasks.main(argv) == 0  # read-only: nothing loaded
    assert sorted(p.name for p in out.iterdir()) == [
        "_legislation_counts.CELLAR.json",
        "legislation_external.jsonl",
    ]
    before = execute(conn, "SELECT count(*) FROM cle_v2.legislation")
    assert linking_tasks.main(argv) == 0
    assert execute(conn, "SELECT count(*) FROM cle_v2.legislation") == before
    assert linking_tasks.main(argv + ["--load"]) == 0
    assert execute(conn, "SELECT count(*) FROM cle_v2.legislation") == [(63,)]


# ---------------------------------------------------------------------------
# R3.5: rs_lido_sqlite rows carry their act
# ---------------------------------------------------------------------------


class _Client:
    """PostgresCLEClient on a plain psycopg2 connection (no Airflow hook)."""

    def __new__(cls, conn):
        from data_loading.clients.postgres import PostgresCLEClient

        client = PostgresCLEClient.__new__(PostgresCLEClient)
        client._conn = conn
        client._tx_depth = 0
        client.hook = None
        return client


@needs_db
def test_rs_law_references_resolve_by_exact_bwb_id(scratch_db):  # noqa: F811
    conn = scratch_db
    client = _Client(conn)
    case = add_case(conn, "ECLI:NL:HR:2024:5", sources=("RS",))
    act = execute(
        conn,
        "INSERT INTO cle_v2.legislation (identifier, scheme)"
        " VALUES ('BWBR0005290', 'bwb') RETURNING id",
    )[0][0]
    for _ in range(2):  # an ambiguous BWB id is not resolved
        execute(
            conn,
            "INSERT INTO cle_v2.legislation (identifier, scheme) VALUES ('BWBR0001854', 'bwb')",
        )
    # an earlier load left this reference unresolved
    execute(
        conn,
        """INSERT INTO cle_v2.case_law_reference (case_id, raw_scheme, raw_resource, raw_reference,
               role, source_dataset)
           VALUES (%s, 'bwb', 'BWBR0002656', 'old', 'cited', 'rs_lido_sqlite')""",
        (case,),
    )
    execute(
        conn, "INSERT INTO cle_v2.legislation (identifier, scheme) VALUES ('BWBR0002656', 'bwb')"
    )

    for _ in range(2):  # a reload inserts nothing new
        for resource in ("BWBR0005290", "BWBR0001854", "BWBR0002656", "BWBR0009999"):
            client.upsert_law_reference(
                case_id=case,
                raw_reference=resource,
                raw_resource=resource,
                source_dataset="rs_lido_sqlite",
                resolve_legislation=True,
            )
    rows = execute(
        conn,
        """SELECT raw_resource, legislation_id, raw_reference FROM cle_v2.case_law_reference
            WHERE case_id = %s ORDER BY raw_resource""",
        (case,),
    )
    assert rows == [
        ("BWBR0001854", None, "BWBR0001854"),
        ("BWBR0002656", None, "old"),  # its unresolved twin is kept, no second row
        ("BWBR0005290", act, "BWBR0005290"),
        ("BWBR0009999", None, "BWBR0009999"),
    ]
