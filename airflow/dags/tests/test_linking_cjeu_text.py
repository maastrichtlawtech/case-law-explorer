"""
CJEU text -> ECtHR links (data_extraction/linking/cjeu_text.py).

Real excerpt: the CJEU's own words in D. and A. (C-175/11), as quoted in
cjeu-migration migration/verify/research-2026-11-24/echr/handcheck.txt line 4.
The gold-set reference (AG Sharpston's opinion 62012CC0199 citing F. v. the
United Kingdom, decision of 22 June 2004, by application number 17341/03 and
as "F. c. Royaume-Uni") is recorded in the research README without the
opinion's text, so the citations below are the minimal strings carrying those
recorded forms. DB tests need CLE_TEST_PG_DSN (see test_link_loader.py).
"""

import os
import uuid
from datetime import date
from pathlib import Path

import pytest

from data_extraction.linking import cjeu_text
from data_extraction.linking.artifact import CaseKey, read_jsonl
from data_extraction.linking.resolver import Candidate
from data_extraction.linking.text_common import DictLookup, Source, TextUnit

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"

OPINION = Source(CaseKey(ecli="ECLI:EU:C:2013:474", celex="62012CC0199"), date(2013, 7, 11))
F_V_UK = Candidate(
    900, "ECLI:CE:ECHR:2004:0622DEC001734103", None, "001-24020", date(2004, 6, 22),
    "decision", "17341/03",
)  # fmt: skip
APPNOS = {"17341/03": [F_V_UK]}

# handcheck.txt line 4 (CJEU text quoted by the ECtHR)
D_AND_A = (
    "(see, to that effect, judgment of 31 January 2013, D. and A., C‑175/11, EU:C:2013:45, "
    "paragraph 99, and ECtHR, 28 June 1984, Campbell and Fell v. United Kingdom , "
    "CE:ECHR:1984:0628JUD000781977, § 79; 2 June 2005, Zolotas v"
)


def run(text, appnos=None, source=OPINION, name_dates=False, name_index=None, language="fr"):
    unit = TextUnit(text, "fulltext", language, "CELLAR_ITEM")
    return cjeu_text.extract_text(
        unit, source, DictLookup({"echr_appno": appnos or {}}), name_dates, name_index
    )


def summary(records):
    return sorted(
        ((r.target.ecli if r.target else None), r.target_ref_raw, r.match_method, r.confidence)
        for r in records
    )


def test_gold_f_v_uk_by_application_number():
    text = "Cour EDH, F. c. Royaume-Uni (déc.), n° 17341/03, 22 juin 2004"
    records = run(text, APPNOS)
    assert summary(records) == [
        ("ECLI:CE:ECHR:2004:0622DEC001734103", "17341/03", "appno/echr_decision_cue", 0.95)
    ]
    record = records[0]
    assert record.source_dataset == "cjeu_text_echr" and record.relation_type == "cites"
    assert record.extractor_version == "cjeu_text/1.0.0"
    m = record.mentions[0]
    assert text[m.char_start : m.char_end] == "17341/03" == m.raw_text
    assert (m.text_field, m.language, m.text_source) == ("fulltext", "fr", "CELLAR_ITEM")


def test_gold_without_dec_cue_falls_back_to_the_only_decision():
    records = run("F. v. the United Kingdom, no. 17341/03, ECtHR", APPNOS, language="en")
    assert summary(records) == [
        ("ECLI:CE:ECHR:2004:0622DEC001734103", "17341/03", "appno/echr_decision_no_judgment", 0.85)
    ]


def test_ecli_with_year_from_real_text():
    assert summary(run(D_AND_A, language="en")) == [
        ("ECLI:CE:ECHR:1984:0628JUD000781977", None, "ecli", 0.99)
    ]


def test_ecli_without_year_needs_a_document_of_that_day():
    campbell = Candidate(
        5, "ECLI:CE:ECHR:1984:0628JUD000781977", None, "001-57456", date(1984, 6, 28),
        "judgment", "7819/77",
    )  # fmt: skip
    text = "Campbell and Fell v. United Kingdom, CE:ECHR:0628JUD000781977"
    assert summary(run(text, {"7819/77": [campbell]})) == [
        ("ECLI:CE:ECHR:1984:0628JUD000781977", "7819/77", "ecli/without_year_echr_judgment", 0.85)
    ]
    other_day = "Campbell and Fell v. United Kingdom, CE:ECHR:0629JUD000781977"
    assert summary(run(other_day, {"7819/77": [campbell]})) == [(None, "7819/77", "appno", None)]


def test_regulation_and_directive_numbers_are_not_application_numbers():
    text = (
        "Regulation (EEC) No 1408/71 and règlement (CEE) n° 1408/71, Directive 2004/38, "
        "decision No. 1/80 of the Association Council; ECtHR case-law"
    )
    assert run(text, {"1408/71": [F_V_UK], "1/80": [F_V_UK]}) == []


def test_application_number_needs_an_echr_cue():
    assert run("see no. 17341/03 of the national register", APPNOS) == []


def test_unresolved_application_number_is_written_unresolved():
    assert summary(run("ECtHR, X v. Y, no. 12345/67", {})) == [(None, "12345/67", "appno", None)]


def test_cited_date_and_dec_cue_pick_among_several_documents():
    def doc(case_id, kind, day):
        return Candidate(
            case_id, f"ECLI:CE:ECHR:{day.year}:X{case_id}", None, None, day, kind, "1/10"
        )

    docs = [
        doc(1, "decision", date(2011, 1, 5)),
        doc(2, "judgment", date(2013, 2, 1)),
        doc(3, "judgment", date(2014, 3, 1)),
    ]
    appnos = {"1/10": docs}
    late = Source(OPINION.key, date(2020, 1, 1))
    by_date = run("ECtHR, A v. B, no. 1/10, 1 March 2014", appnos, source=late, language="en")
    assert summary(by_date)[0][0] == "ECLI:CE:ECHR:2014:X3"
    dec = run("ECtHR, A v. B (dec.), no. 1/10, 5 January 2011", appnos, source=late)
    assert summary(dec)[0][0] == "ECLI:CE:ECHR:2011:X1"
    later = run(
        "Eur. Court H.R., A v. B, no. 1/10", appnos, source=Source(OPINION.key, date(2013, 6, 1))
    )
    assert summary(later)[0][0] == "ECLI:CE:ECHR:2013:X2"


def test_application_number_list():
    a = Candidate(1, "ECLI:CE:ECHR:2008:A", None, None, date(2008, 1, 1), "judgment", "30562/04")
    text = "S. and Marper v. the United Kingdom [GC], nos. 30562/04 and 30566/04, ECHR 2008"
    records = run(text, {"30562/04": [a], "30566/04": [a]}, language="en")
    assert summary(records) == [("ECLI:CE:ECHR:2008:A", "30562/04", "appno/echr_judgment", 0.95)]
    assert [m.raw_text for m in records[0].mentions] == ["30562/04", "30566/04"]


def test_name_date_is_off_by_default(monkeypatch):
    monkeypatch.delenv("NAME_DATE_LINKS", raising=False)
    text = "the ECtHR held in F. v. the United Kingdom, 22 June 2004, that"
    index = {("F V UNITED KINGDOM", date(2004, 6, 22)): [F_V_UK]}
    unit = TextUnit(text, "fulltext", "en", "CELLAR_ITEM")
    assert cjeu_text.extract_text(unit, OPINION, DictLookup(), name_index=index) == []
    monkeypatch.setenv("NAME_DATE_LINKS", "1")
    records = cjeu_text.extract_text(unit, OPINION, DictLookup(), name_index=index)
    assert summary(records) == [
        (
            "ECLI:CE:ECHR:2004:0622DEC001734103",
            "F V UNITED KINGDOM|2004-06-22",
            "name_date/echr_decision_no_judgment",
            0.7,
        )
    ]


def test_name_date_matches_french_name_and_drops_sentence_words():
    index = {("F V UNITED KINGDOM", date(2004, 6, 22)): [F_V_UK]}
    text = "Voir F. c. Royaume-Uni (déc.), 22 juin 2004."
    records = run(text, name_dates=True, name_index=index)
    assert [r.target.ecli for r in records] == ["ECLI:CE:ECHR:2004:0622DEC001734103"]


def test_name_date_unmatched_or_ambiguous_is_unresolved_and_number_wins():
    other = Candidate(901, "ECLI:CE:ECHR:2004:Z", None, None, date(2004, 6, 22), "decision", "")
    index = {("F V UNITED KINGDOM", date(2004, 6, 22)): [F_V_UK, other]}
    text = "ECtHR, F. v. the United Kingdom, 22 June 2004"
    assert summary(run(text, name_dates=True, name_index=index)) == [
        (None, "F V UNITED KINGDOM|2004-06-22", "name_date", None)
    ]
    covered = "F. v. the United Kingdom, 22 June 2004, no. 17341/03 (ECtHR)"
    records = run(covered, APPNOS, name_dates=True, name_index=index)
    assert [r.match_method for r in records] == ["appno/echr_decision_no_judgment"]


def test_normalize_case_name():
    assert cjeu_text.normalize_case_name("CASE OF F. v. THE UNITED KINGDOM") == "F V UNITED KINGDOM"
    assert cjeu_text.normalize_case_name("AFFAIRE F. c. ROYAUME-UNI") == "F V UNITED KINGDOM"
    assert cjeu_text.normalize_case_name("Soering v. the United Kingdom [GC]") == (
        "SOERING V UNITED KINGDOM"
    )
    assert cjeu_text.normalize_case_name("no versus here") is None


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DSN = os.environ.get("CLE_TEST_PG_DSN")
needs_db = pytest.mark.skipif(not DSN, reason="CLE_TEST_PG_DSN not set")


@pytest.fixture
def conn():
    psycopg2 = pytest.importorskip("psycopg2")
    name = "cle_cjeu_text_test_" + uuid.uuid4().hex[:8]
    admin = psycopg2.connect(DSN)
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE "{name}"')
    base, _, _ = DSN.rpartition("/")
    db = psycopg2.connect(f"{base}/{name}")
    try:
        sql = SCHEMA_SQL.read_text().replace('CREATE SCHEMA "public";', "")
        with db.cursor() as cursor:
            cursor.execute(sql)
            cursor.execute("""
                INSERT INTO cle_v2.cases (id, ecli, celex_id, item_id, date_decision, sources)
                OVERRIDING SYSTEM VALUE VALUES
                  (1, 'ECLI:EU:C:2013:474', '62012CC0199', NULL, '2013-07-11', '{CJEU}'),
                  (2, 'ECLI:EU:C:2013:720', '62012CJ0199', NULL, '2013-11-07', '{CJEU}'),
                  (900, 'ECLI:CE:ECHR:2004:0622DEC001734103', NULL, '001-24020', '2004-06-22',
                   '{ECHR}');
                INSERT INTO cle_v2.case_identifier
                  (case_id, scheme, value, value_normalized, source)
                VALUES (900, 'echr_appno', '17341/03', '17341/03', 'echr_document_appno');
                INSERT INTO cle_v2.echr_document (item_id, case_id, language, doctype, docname,
                                                  judgement_date)
                VALUES ('001-24020', 900, 'en', 'HEDEC', 'F. v. THE UNITED KINGDOM',
                        '2004-06-22 00:00:00+00');
                INSERT INTO cle_v2.case_text (case_id, language, source, fulltext, document_kind)
                VALUES
                  (1, 'fr', 'CELLAR_ITEM', 'Cour EDH, F. c. Royaume-Uni (déc.), n° 17341/03, '
                                           '22 juin 2004', 'opinion'),
                  (1, 'fr', 'INFOCURIA_BLOB_HTML', 'Cour EDH, n° 17341/03 (copie)', 'opinion'),
                  (1, 'en', 'CELLAR_ITEM', 'ECtHR, F. v. the United Kingdom, 22 June 2004',
                   'opinion'),
                  (2, 'en', 'CELLAR_ITEM', 'Eur. Court H.R., no. 17341/03 (misfiled text)',
                   'misfiled'),
                  (2, 'de', 'CELLAR_ITEM', 'EGMR, Nr. 17341/03, Zusammenfassung', 'summary'),
                  (2, 'de', 'INFOCURIA_BLOB_HTML', 'EGMR, F. gegen Vereinigtes Königreich, '
                                                   'Beschwerde Nr. 17341/03', 'judgment');
                """)
        db.commit()
        yield db
    finally:
        db.close()
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
        admin.close()


@needs_db
def test_extract_from_database(conn, tmp_path):
    from data_loading.link_loader import load_artifact

    out = tmp_path / "links"
    out.mkdir()
    result = cjeu_text.extract(conn, id_range=(1, 2), out_path=str(out), name_dates=False)
    records = list(read_jsonl(out / "cjeu_text_echr.jsonl"))
    got = sorted(
        (r.source.ecli, r.target.ecli, sorted((m.language, m.text_source) for m in r.mentions))
        for r in records
    )
    # The opinion: CELLAR's French text only (not InfoCuria's copy); the English
    # text has only a name + date citation (flag off). The judgment: the German
    # decision text, not the summary, never the misfiled English text.
    assert got == [
        (
            "ECLI:EU:C:2013:474",
            "ECLI:CE:ECHR:2004:0622DEC001734103",
            [("fr", "CELLAR_ITEM")],
        ),
        (
            "ECLI:EU:C:2013:720",
            "ECLI:CE:ECHR:2004:0622DEC001734103",
            [("de", "INFOCURIA_BLOB_HTML")],
        ),
    ]
    assert result["by_method"] == {
        "appno/echr_decision_cue": 1,
        "appno/echr_decision_no_judgment": 1,
    }
    counts = load_artifact(conn, out / "cjeu_text_echr.jsonl")
    assert counts["cjeu_text_echr"]["inserted"] == 2


@needs_db
def test_extract_name_date_from_database(conn, tmp_path):
    out = tmp_path / "nd.jsonl"
    cjeu_text.extract(conn, case_ids=[1], out_path=str(out), name_dates=True)
    records = list(read_jsonl(out))
    # One link: the application number (French text) and the name + date
    # (English text) reach the same decision; the surer rule is kept.
    assert [(r.match_method, r.target.ecli) for r in records] == [
        ("appno/echr_decision_cue", "ECLI:CE:ECHR:2004:0622DEC001734103")
    ]
    assert sorted(m.language for m in records[0].mentions) == ["en", "fr"]
