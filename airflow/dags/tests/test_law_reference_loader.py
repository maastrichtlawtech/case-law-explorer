"""
Law references into case_law_reference (roadmap R3.2-R3.4) against a scratch
Postgres built from db/schema.sql: the loader, the three extractors end to
end, the flagged Cellar CDM insert in cjeu_loader and the weekly month task.
Runs only when CLE_TEST_PG_DSN is set (see tests/linking_db.py).

Texts are ILLUSTRATIVE strings in the forms courts use, not copied from
judgments.
"""

import json
from datetime import date

import pytest

import linking_tasks
from data_extraction.linking import cellar_law_refs, echr_eu_law, rs_eu_law
from data_extraction.linking.artifact import CaseKey
from data_extraction.linking.law_artifact import LawReferenceRecord, LawTarget
from data_loading import cjeu_loader, law_reference_loader
from tests.linking_db import add_case, execute, needs_db, scratch_db  # noqa: F401

pytestmark = needs_db

RS = "ECLI:NL:RVS:2020:423"


def record(source=RS, identifier="32011L0095", alternatives=(), sub=None, article=None, **kw):
    values = dict(
        source=CaseKey(ecli=source),
        target=LawTarget("celex", identifier, tuple(alternatives)),
        raw_scheme="celex",
        raw_resource=identifier,
        raw_subdivision=sub,
        article=article,
        source_dataset="rs_text_eu_law",
        extractor_version="eu_law_text/1.0.0",
        match_method="act_number",
        confidence=0.95,
    )
    values.update(kw)
    return LawReferenceRecord(**values)


def rows(conn, dataset=None):
    return execute(
        conn,
        """SELECT c.ecli, r.legislation_id IS NOT NULL, r.provision_id IS NOT NULL, r.raw_scheme,
                  r.raw_resource, r.raw_subdivision, r.role, r.source_dataset,
                  r.extractor_version, r.match_method, r.confidence
             FROM cle_v2.case_law_reference r JOIN cle_v2.cases c ON c.id = r.case_id
            WHERE %(d)s::text IS NULL OR r.source_dataset = %(d)s
            ORDER BY 1, 5, 6 NULLS FIRST, 2""",
        {"d": dataset},
    )


def add_act(conn, identifier, scheme="celex"):
    return execute(
        conn,
        "INSERT INTO cle_v2.legislation (scheme, identifier) VALUES (%s, %s) RETURNING id",
        (scheme, identifier),
    )[0][0]


def add_article(conn, legislation_id, label):
    return execute(
        conn,
        """INSERT INTO cle_v2.legal_provision (legislation_id, element_type, article_label)
           VALUES (%s, 'article', %s) RETURNING id""",
        (legislation_id, label),
    )[0][0]


def test_unresolved_then_resolved_twin_insert_only(scratch_db):  # noqa: F811
    conn = scratch_db
    add_case(conn, ecli=RS, sources=("RS",))
    records = [record(), record(sub="15", article="15"), record(source="ECLI:NL:XX:2020:1")]

    first = law_reference_loader.load_records(conn, records)
    assert first == {"rs_text_eu_law": {"inserted_unresolved": 2, "source_missing": 1}}
    again = law_reference_loader.load_records(conn, records)
    assert again == {"rs_text_eu_law": {"existing": 2, "source_missing": 1}}
    assert [r[1:3] for r in rows(conn)] == [(False, False), (False, False)]

    # The act arrives (R3.1): a re-run adds the resolved row; the unresolved stays.
    act = add_act(conn, "32011L0095")
    add_article(conn, act, "15")
    third = law_reference_loader.load_records(conn, records)
    assert third == {"rs_text_eu_law": {"inserted": 2, "with_provision": 1, "source_missing": 1}}
    assert rows(conn) == [
        (RS, False, False, "celex", "32011L0095", None, "cited", "rs_text_eu_law",
         "eu_law_text/1.0.0", "act_number", 0.95),
        (RS, True, False, "celex", "32011L0095", None, "cited", "rs_text_eu_law",
         "eu_law_text/1.0.0", "act_number", 0.95),
        (RS, False, False, "celex", "32011L0095", "15", "cited", "rs_text_eu_law",
         "eu_law_text/1.0.0", "act_number", 0.95),
        (RS, True, True, "celex", "32011L0095", "15", "cited", "rs_text_eu_law",
         "eu_law_text/1.0.0", "act_number", 0.95),
    ]  # fmt: skip
    fourth = law_reference_loader.load_records(conn, records)
    assert fourth == {"rs_text_eu_law": {"existing": 2, "source_missing": 1}}
    assert len(rows(conn)) == 4


def test_alternatives_then_curated_aliases_resolve_and_pick_the_article(scratch_db):  # noqa: F811
    conn = scratch_db
    add_case(conn, ecli=RS, sources=("RS",))
    tfeu = add_act(conn, "12008E")  # the version legislation happens to hold
    article = add_article(conn, tfeu, "267")
    charter = add_act(conn, "CHARTER-ROW")
    execute(
        conn,
        "INSERT INTO cle_v2.legislation_alias (legislation_id, alias, source) VALUES "
        "(%s, '12016P/TXT', 'curated'), (%s, '32011L0095', 'opschrift')",
        (charter, charter),
    )
    records = [
        record(identifier="12016E/TXT", alternatives=("12012E/TXT", "12008E"), sub="267(3)",
               article="267", match_method="treaty_article"),
        record(identifier="12016P/TXT", alternatives=("12016P",), sub="47", article="47",
               match_method="treaty_article"),
        record(identifier="32011L0095"),  # only a non-curated alias: unresolved
    ]  # fmt: skip

    counts = law_reference_loader.load_records(conn, records)

    assert counts == {
        "rs_text_eu_law": {"inserted": 2, "inserted_unresolved": 1, "with_provision": 1}
    }
    got = execute(
        conn,
        """SELECT raw_resource, raw_subdivision, legislation_id, provision_id
             FROM cle_v2.case_law_reference ORDER BY raw_resource""",
    )
    assert got == [
        ("12016E/TXT", "267(3)", tfeu, article),
        ("12016P/TXT", "47", charter, None),
        ("32011L0095", None, None, None),
    ]


def test_loader_refuses_a_schema_without_the_provenance_columns(scratch_db):  # noqa: F811
    conn = scratch_db
    execute(conn, "ALTER TABLE cle_v2.case_law_reference DROP COLUMN confidence")
    with pytest.raises(RuntimeError, match="0012"):
        law_reference_loader.load_records(conn, [record()])


def test_rs_and_echr_texts_end_to_end(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    rs = add_case(conn, ecli=RS, decided=date(2020, 2, 12), sources=("RS",))
    echr = add_case(conn, ecli="ECLI:CE:ECHR:2021:0101JUD000000120", decided=date(2021, 1, 1),
                    sources=("ECHR",))  # fmt: skip
    execute(
        conn,
        """INSERT INTO cle_v2.case_text (case_id, language, fulltext, summary, source) VALUES
           (%s, 'nl', 'Gelet op artikel 47 Handvest en artikel 15, aanhef en onder c, van '
                      'Richtlijn 2011/95/EU.', 'Verordening (EU) nr. 604/2013', 'RECHTSPRAAK'),
           (%s, 'en', 'The Charter of Fundamental Rights of the European Union ... Article 47 '
                      'of the Charter; Article 6 of the Convention.', NULL, 'HUDOC')""",
        (rs, echr),
    )
    rs_path, echr_path = tmp_path / "rs.jsonl", tmp_path / "echr.jsonl"

    assert rs_eu_law.extract(conn, out_path=str(rs_path))["records"] == 3
    assert echr_eu_law.extract(conn, out_path=str(echr_path))["records"] == 1
    lines = [json.loads(line) for line in rs_path.read_text().splitlines()]
    assert {(x["raw_resource"], x.get("raw_subdivision")) for x in lines} == {
        ("12016P/TXT", "47"),
        ("32011L0095", "15"),
        ("32013R0604", None),
    }
    assert all(x["source"] == {"ecli": RS} for x in lines)

    assert law_reference_loader.load_artifact(conn, rs_path) == {
        "rs_text_eu_law": {"inserted_unresolved": 3}
    }
    assert law_reference_loader.load_artifact(conn, echr_path) == {
        "echr_text_eu_law": {"inserted_unresolved": 1}
    }
    assert [r[4:6] for r in rows(conn, "echr_text_eu_law")] == [("12016P/TXT", "47")]


def _cellar_citations(conn):
    cjeu = add_case(conn, ecli="ECLI:EU:C:2019:189", celex="62017CJ0221", sources=("CJEU",))
    other = add_case(conn, ecli="ECLI:EU:C:2010:1", celex="62010CJ0001", sources=("CJEU",))
    execute(
        conn,
        """INSERT INTO cle_v2.case_citation (source_case_id, target_case_id, target_celex_raw,
                                             relation_type, source_dataset)
           VALUES (%(s)s, NULL, '32004L0038', 'cites', 'cellar_sparql'),
                  (%(s)s, NULL, '12008E267', 'cites', 'cellar_sparql'),
                  (%(s)s, NULL, '52012PC0011', 'cites', 'cellar_sparql'),
                  (%(s)s, NULL, '32004L0038', 'cited_by', 'cellar_sparql'),
                  (%(s)s, %(o)s, '62010CJ0001', 'cites', 'cellar_sparql'),
                  (%(s)s, NULL, '32003L0086', 'cites', 'rs_lido_sqlite')""",
        {"s": cjeu, "o": other},
    )
    return cjeu


def test_cellar_unresolved_citations_become_law_references(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    _cellar_citations(conn)
    tfeu = add_act(conn, "12008E")
    add_article(conn, tfeu, "267")
    before = execute(conn, "SELECT count(*) FROM cle_v2.case_citation")
    path = tmp_path / "cellar_law_ref.jsonl"

    stats = cellar_law_refs.extract(conn, out_path=str(path))
    counts = law_reference_loader.load_artifact(conn, path)

    assert stats == {"records": 2, "sector_1": 1, "sector_3": 1, "skipped_sector_5": 1}
    assert counts == {
        "cellar_law_ref": {"inserted": 1, "inserted_unresolved": 1, "with_provision": 1}
    }
    assert [r[:6] for r in rows(conn, "cellar_law_ref")] == [
        ("ECLI:EU:C:2019:189", True, True, "celex", "12008E267", "267"),
        ("ECLI:EU:C:2019:189", False, False, "celex", "32004L0038", None),
    ]
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_citation") == before


def test_cjeu_loader_resolves_new_cdm_law_references_only_with_the_flag(
    scratch_db, monkeypatch  # noqa: F811
):
    conn = scratch_db
    old = add_case(conn, ecli="ECLI:EU:C:2019:189", celex="62017CJ0221", sources=("CJEU",))
    add_case(conn, ecli="ECLI:EU:C:2026:691", celex="62025CJ0147", sources=("CJEU",))
    execute(
        conn,
        """INSERT INTO cle_v2.case_law_reference (case_id, raw_scheme, raw_resource, role,
                                                  source_dataset)
           VALUES (%s, 'celex', '12016P047', 'legal_basis', 'cellar_sparql')""",
        (old,),
    )
    charter = add_act(conn, "12016P")
    article = add_article(conn, charter, "47")
    batch = [
        ("ECLI:EU:C:2019:189", "12016P047", "legal_basis"),  # loaded before: left alone
        ("ECLI:EU:C:2026:691", "12016P047", "legal_basis"),
        ("ECLI:EU:C:2026:691", "32004L0038", "interprets"),
    ]

    def run(sql, params):
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            n = cursor.rowcount
        conn.commit()
        return n

    assert not law_reference_loader.enabled()
    monkeypatch.setenv("LAW_REFERENCE_EXTRACTION_ENABLED", "1")
    assert law_reference_loader.enabled()
    params = cjeu_loader._tuples(cjeu_loader.lawref_rows(batch), 5)
    assert run(cjeu_loader.SQL_LAWREF_RESOLVED, params) == 2
    assert run(cjeu_loader.SQL_LAWREF_RESOLVED, params) == 0
    got = execute(
        conn,
        """SELECT c.ecli, r.raw_resource, r.raw_subdivision, r.role, r.legislation_id,
                  r.provision_id
             FROM cle_v2.case_law_reference r JOIN cle_v2.cases c ON c.id = r.case_id
            ORDER BY 1, 2""",
    )
    assert got == [
        ("ECLI:EU:C:2019:189", "12016P047", None, "legal_basis", None, None),
        ("ECLI:EU:C:2026:691", "12016P047", None, "legal_basis", charter, article),
        ("ECLI:EU:C:2026:691", "32004L0038", None, "interprets", None, None),
    ]


def test_month_task_writes_and_loads_law_references(
    scratch_db, tmp_path, monkeypatch  # noqa: F811
):
    conn = scratch_db
    monkeypatch.setenv("LAW_REFERENCE_EXTRACTION_ENABLED", "1")
    _cellar_citations(conn)
    folder = tmp_path / "processed" / "2019-02-01"
    folder.mkdir(parents=True)
    (folder / "cellar_csv_data_clean.csv").write_text("celex,title\n62017CJ0221,x\n")

    counts = linking_tasks.run_month_law(
        conn, linking_tasks.SOURCES["cellar"], str(tmp_path), "2019-02-01"
    )

    assert linking_tasks.law_artifact_paths(linking_tasks.SOURCES["cellar"], "2019-02-01") == [
        "processed/2019-02-01/law_references/cellar_law_ref.jsonl"
    ]
    out = folder / "law_references"
    assert sorted(p.name for p in out.iterdir()) == ["_counts.CELLAR.json", "cellar_law_ref.jsonl"]
    assert counts["datasets"]["cellar_law_ref"] == {
        "records": 2,
        "load": {"inserted_unresolved": 2},
    }
    # off per extractor: the file is still written, empty
    monkeypatch.setenv("LAW_CELLAR_REFS", "0")
    counts = linking_tasks.run_month_law(
        conn, linking_tasks.SOURCES["cellar"], str(tmp_path), "2019-02-01"
    )
    assert counts["extractor"]["status"] == "skipped"
    assert (out / "cellar_law_ref.jsonl").stat().st_size == 0
    assert counts["datasets"]["cellar_law_ref"] == {"records": 0, "load": {}}


def test_backfill_law_without_load_writes_only_the_file(scratch_db, tmp_path):  # noqa: F811
    conn = scratch_db
    cjeu = _cellar_citations(conn)
    counts = linking_tasks.backfill_law(
        conn, linking_tasks.SOURCES["cellar"], cjeu, cjeu, str(tmp_path / "out")
    )
    assert counts["datasets"] == {"cellar_law_ref": {"records": 2}}
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_law_reference") == [(0,)]
    assert (tmp_path / "out" / "cellar_law_ref.jsonl").is_file()
