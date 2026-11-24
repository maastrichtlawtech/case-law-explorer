"""
ECtHR text -> CJEU / Rechtspraak links (data_extraction/linking/echr_text.py).

The excerpts are copied verbatim from the research hand check
(cjeu-migration migration/verify/research-2026-11-24/echr/handcheck.txt, the
ctx column); the candidate sets follow rs/allres_nums.txt and
rs/allres_eclis.txt (what production holds for each case number). The DB
tests need CLE_TEST_PG_DSN (see test_link_loader.py).
"""

import json
import os
import uuid
from datetime import date
from pathlib import Path

import pytest

from data_extraction.linking import echr_text
from data_extraction.linking.artifact import CaseKey, read_jsonl
from data_extraction.linking.resolver import Candidate, cjeu_kind
from data_extraction.linking.text_common import DictLookup, Source, TextUnit

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"

SOURCE = Source(CaseKey(ecli="ECLI:CE:ECHR:2025:0101JUD000000125"), date(2025, 1, 1))


def cand(case_id, celex, ecli=None, value=None, decided=None):
    return Candidate(case_id, ecli, celex, None, decided, cjeu_kind(celex), value or "")


def lookup(numbers=None, ljns=None):
    return DictLookup({"cjeu_case_number": numbers or {}, "ljn": ljns or {}})


def run(text, numbers=None, ljns=None, segments=None, flag=True, source=SOURCE):
    unit = TextUnit(text, "fulltext", "en", "HUDOC")
    return echr_text.extract_text(unit, source, lookup(numbers, ljns), segments, domestic_flag=flag)


def targets(records):
    return sorted(
        (
            (r.source_dataset, r.relation_type,
             (r.target.ecli or r.target.celex) if r.target else None,
             r.target_ref_raw, r.match_method)
            for r in records
        ),
        key=lambda t: tuple("" if v is None else v for v in t),
    )  # fmt: skip


# handcheck.txt line 14 (La Quadrature du Net; the research picked the AG
# opinion 62018CC0520, the ECLI names the judgment)
LQDN = (
    "La Quadrature du Net and Others (C ‑ 511/18, C ‑ 512/18 and C ‑ 520/18, "
    "EU:C:2020:791)  78 . In a judgment of 6 October 2020, given pursuant to requests for a "
    "preliminary reference lodged by the French Council of State a"
)
LQDN_NUMBERS = {
    "C-511/18": [
        cand(3862565, "62018CC0511", "ECLI:EU:C:2020:6"),
        cand(3863606, "62018CJ0511", "ECLI:EU:C:2020:791"),
        cand(3863771, "62018CO0511"),
    ],
    "C-520/18": [cand(3862571, "62018CC0520", "ECLI:EU:C:2020:7")],
}

# handcheck.txt line 22 (the order C-204/21 R, not the 2023 judgment)
POLAND = (
    "e Court to either (i) suspend all actions (both procedural and administrative) of the "
    "Disciplinary Chamber of the Supreme Court against him until the Government fully "
    "implemented the order of the Vice-President of CJEU of 14 July 2021 ( Commission v. "
    "Poland , C-204/21 R, EU:C:2021:593) and the judgment of that court of 15 July 2021 (in "
    "Commission v. Poland (Disciplinary regime for judges) , C-791/19, EU:C:2021:596), "
)

# handcheck.txt line 11 (an Opinion cue after the citation, not before it)
LUDWIGS = (
    "législation nationale mettant en œuvre la faculté prévue à cette disposition, doit "
    "demeurer exceptionnelle afin de préserver l’effet utile de la procédure d’[autorisation de "
    "mise sur le marché] (voir, en ce sens, l’arrêt du 8 novembre 2007, Ludwigs-Apotheke , "
    "C-143/06, Rec. p. I-9623, points 33 et 35).  33. Ainsi que l’a exposé M. l’avocat général "
    "au point 34 de ses conclusions, la faculté, qui découle de l’article 5"
)

# handcheck.txt line 16 (truncated ECLI "C:2023:367" is not taken as an ECLI)
TAC = (
    "C. European Union case-law  38. The relevant parts of the judgment of the Court of "
    "Justice of the European Union (“the CJEU”) T.A.C. v. Agenția Națională de Integritate "
    "(ANI) (C-40/21, C:2023:367) of 4 May 2023 may be found in Păcurar v. Romania (no. "
    "17985/18, § 110, 24 June 2025)."
)


def test_ecli_in_same_citation_wins_over_case_numbers():
    records = run(LQDN, LQDN_NUMBERS)
    assert targets(records) == [
        ("echr_text_cjeu", "cites", "ECLI:EU:C:2020:791", None, "ecli"),
    ]
    raws = [m.raw_text for m in records[0].mentions]
    assert raws == ["C ‑ 511/18", "C ‑ 512/18", "C ‑ 520/18", "EU:C:2020:791"]
    for m in records[0].mentions:
        assert LQDN[m.char_start : m.char_end] == m.raw_text


def test_interim_order_by_ecli_and_second_citation():
    numbers = {
        "C-204/21": [
            cand(3868034, "62021CJ0204", "ECLI:EU:C:2023:442"),
            cand(3865255, "62021CO0204(01)", "ECLI:EU:C:2021:593", value="C-204/21 R"),
        ],
        "C-791/19": [cand(1, "62019CJ0791", "ECLI:EU:C:2021:596")],
    }
    assert targets(run(POLAND, numbers)) == [
        ("echr_text_cjeu", "cites", "ECLI:EU:C:2021:593", None, "ecli"),
        ("echr_text_cjeu", "cites", "ECLI:EU:C:2021:596", None, "ecli"),
    ]


def test_suffix_r_without_ecli_never_takes_the_judgment():
    numbers = {"C-204/21": [cand(3868034, "62021CJ0204", "ECLI:EU:C:2023:442")]}
    records = run("the order of the Vice-President (Commission v. Poland, C-204/21 R).", numbers)
    assert targets(records) == [
        ("echr_text_cjeu", "cites", None, "C-204/21", "case_number"),
    ]


def test_conflicting_ecli_keeps_the_ecli_and_leaves_the_number_unresolved():
    numbers = {"C-684/16": [cand(10, "62016CJ0684", "ECLI:EU:C:2018:874")]}
    records = run("judgment in Max-Planck (C-684/16, EU:C:2018:871).", numbers)
    assert targets(records) == [
        ("echr_text_cjeu", "cites", None, "C-684/16", "case_number"),
        ("echr_text_cjeu", "cites", "ECLI:EU:C:2018:871", None, "ecli"),
    ]
    assert {r.confidence for r in records if r.target} == {echr_text.CONF_ECLI_CONFLICT}


def test_no_opinion_without_a_cue_before_the_citation():
    numbers = {"C-143/06": [cand(1, "62006CC0143"), cand(2, "62006CJ0143")]}
    records = run(LUDWIGS, numbers)
    assert [r.target.celex for r in records] == ["62006CJ0143"]


def test_opinion_when_written_before_the_citation():
    numbers = {"C-143/06": [cand(1, "62006CC0143"), cand(2, "62006CJ0143")]}
    records = run("see the Opinion of Advocate General Bot in Ludwigs-Apotheke, C-143/06.", numbers)
    assert [r.target.celex for r in records] == ["62006CC0143"]
    records = run("conclusions de l’avocat général dans l’affaire C-143/06.", numbers)
    assert [r.target.celex for r in records] == ["62006CC0143"]


def test_truncated_ecli_is_ignored_and_case_number_resolves():
    numbers = {"C-40/21": [cand(3867077, "62021CC0040"), cand(3867914, "62021CJ0040")]}
    records = run(TAC, numbers)
    assert [(r.target.celex, r.match_method) for r in records] == [("62021CJ0040", "case_number")]


def test_joined_range_goes_to_the_lead_case_and_plain_space():
    numbers = {"C-199/12": [cand(5, "62012CJ0199", "ECLI:EU:C:2013:720")]}
    text = "CJUE, X, Y et Z, affaires jointes C 199/12 à C 201/12, 7 novembre 2013"
    records = run(text, numbers)
    assert targets(records) == [("echr_text_cjeu", "cites", "ECLI:EU:C:2013:720", "C-199/12",
                                 "case_number")]  # fmt: skip
    assert [m.raw_text for m in records[0].mentions] == ["C 199/12", "C 201/12"]


def test_joined_member_resolving_alone_is_used_when_lead_is_unknown():
    numbers = {"C-201/12": [cand(5, "62012CJ0199", "ECLI:EU:C:2013:720")]}
    records = run("Joined Cases C-199/12 to C-201/12 X, Y and Z", numbers)
    assert [(r.target.ecli, r.target_ref_raw) for r in records] == [
        ("ECLI:EU:C:2013:720", "C-201/12")
    ]


def test_unresolved_numbers_are_written_unresolved():
    records = run("Joined Cases C ‑ 71/11 and C-99/11", {})
    assert targets(records) == [
        ("echr_text_cjeu", "cites", None, "C-71/11", "case_number"),
        ("echr_text_cjeu", "cites", None, "C-99/11", "case_number"),
    ]


def test_application_numbers_and_domestic_file_numbers_are_not_case_numbers():
    text = (
        "Păcurar v. Romania (no. 17985/18, § 110, 24 June 2025); "
        "the District Court (sygn. akt I C 123/05) and II C 45/10; Case 26/62 Van Gend en Loos"
    )
    records = run(text, {"26/62": [cand(7, "61962CJ0026")]})
    assert targets(records) == [("echr_text_cjeu", "cites", "61962CJ0026", "26/62", "case_number")]


def test_dated_after_source_is_not_chosen():
    numbers = {"C-1/24": [cand(1, "62024CJ0001", decided=date(2026, 5, 1))]}
    records = run("judgment of the CJEU, C-1/24", numbers)
    assert records[0].target is None


def test_bare_eu_ecli_and_ecli_prefix():
    records = run("ECLI:EU:C:2019:189 and EU:T:2020:459.", {})
    assert targets(records) == [
        ("echr_text_cjeu", "cites", "ECLI:EU:C:2019:189", None, "ecli"),
        ("echr_text_cjeu", "cites", "ECLI:EU:T:2020:459", None, "ecli"),
    ]


# ---------------------------------------------------------------------------
# Rechtspraak
# ---------------------------------------------------------------------------


def rs(case_id, ecli, decided=None):
    return Candidate(case_id, ecli, None, None, decided, "other", ecli.rsplit(":", 1)[-1])


def test_dutch_ecli_and_ljn():
    ljns = {
        "BR0132": [rs(1, "ECLI:NL:HR:2011:BR0132")],
        "BV3436": [rs(2, "ECLI:NL:HR:2012:BV3436"), rs(3, "ECLI:NL:PHR:2012:BV3436")],
    }
    text = (
        "Hoge Raad, ECLI:NL:HR:2013:BZ3640; LJN BR0132; Supreme Court, LJN: BV3436; "
        "conclusie van de advocaat-generaal, LJN BV3436"
    )
    assert targets(run(text, ljns=ljns)) == [
        ("echr_text_rs", "cites", "ECLI:NL:HR:2011:BR0132", "BR0132", "ljn"),
        ("echr_text_rs", "cites", "ECLI:NL:HR:2012:BV3436", "BV3436", "ljn"),
        ("echr_text_rs", "cites", "ECLI:NL:HR:2013:BZ3640", None, "ecli"),
        ("echr_text_rs", "cites", "ECLI:NL:PHR:2012:BV3436", "BV3436", "ljn"),
    ]


def test_ambiguous_ljn_is_unresolved():
    ljns = {"BW3076": [rs(1, "ECLI:NL:RVS:2012:BW3076"), rs(2, "ECLI:NL:RVS:2012:4057")]}
    assert targets(run("LJN BW3076", ljns=ljns)) == [
        ("echr_text_rs", "cites", None, "BW3076", "ljn"),
    ]


def test_ljn_list():
    ljns = {"BR0132": [rs(1, "ECLI:NL:GHSGR:2011:BR0132")],
            "BR0133": [rs(2, "ECLI:NL:GHSGR:2011:BR0133")]}  # fmt: skip
    records = run("LJN BR0132 and BR0133", ljns=ljns)
    assert sorted(r.target.ecli for r in records) == [
        "ECLI:NL:GHSGR:2011:BR0132",
        "ECLI:NL:GHSGR:2011:BR0133",
    ]


# ---------------------------------------------------------------------------
# Sections (D4)
# ---------------------------------------------------------------------------

JUDGMENT = (
    "PROCEDURE  1. The case originated in an application. THE FACTS  2. The Supreme Court "
    "relied on Chacón Navas, C-13/05, EU:C:2006:456. II. RELEVANT LEGAL FRAMEWORK A. Domestic "
    "law 3. The court cited LJN BR0132. B. European Union law 4. Kadi, EU:C:2008:461. "
    "THE LAW I. ALLEGED VIOLATION OF ARTICLE 8 5. The Court refers to EU:C:2006:456 and "
    "EU:C:2014:238. FOR THESE REASONS, THE COURT"
)


def test_sections_and_domestic_relation():
    ljns = {"BR0132": [rs(1, "ECLI:NL:HR:2011:BR0132")]}
    records = run(JUDGMENT, ljns=ljns)
    by_target = {}
    for r in records:
        by_target.setdefault(r.target.ecli, []).append(
            (r.relation_type, [m.section for m in r.mentions])
        )
    assert by_target == {
        "ECLI:EU:C:2006:456": [
            ("cites_in_domestic_law", ["facts", "facts"]),
            ("cites", ["law"]),
        ],
        "ECLI:NL:HR:2011:BR0132": [("cites_in_domestic_law", ["domestic_law"])],
        "ECLI:EU:C:2008:461": [("cites", ["eu_international_law"])],
        "ECLI:EU:C:2014:238": [("cites", ["law"])],
    }


def test_flag_off_keeps_sections_but_every_relation_is_cites():
    records = run(JUDGMENT, flag=False)
    assert {r.relation_type for r in records} == {"cites"}
    assert any(m.section == "facts" for r in records for m in r.mentions)


def test_flag_from_environment(monkeypatch):
    unit = TextUnit(JUDGMENT, "fulltext", "en", "HUDOC")
    monkeypatch.setenv("ECHR_DOMESTIC_LAW_RELATION", "0")
    records = echr_text.extract_text(unit, SOURCE, lookup())
    assert {r.relation_type for r in records} == {"cites"}
    monkeypatch.delenv("ECHR_DOMESTIC_LAW_RELATION")
    records = echr_text.extract_text(unit, SOURCE, lookup())
    assert "cites_in_domestic_law" in {r.relation_type for r in records}


def test_segments_give_sections_when_headings_are_missing():
    text = (
        "1. The applicant complained. 2. The Supreme Court relied on EU:C:2006:456 in its "
        "judgment of that year. 3. The Court considers, having regard to EU:C:2014:238, that"
    )
    segments = {
        "facts": "2. The Supreme Court relied on EU:C:2006:456 in its judgment of that year.",
        "law": "3. The Court considers, having regard to EU:C:2014:238, that",
    }
    records = run(text, segments=segments)
    assert sorted((r.target.ecli, r.relation_type, r.mentions[0].section) for r in records) == [
        ("ECLI:EU:C:2006:456", "cites_in_domestic_law", "facts"),
        ("ECLI:EU:C:2014:238", "cites", "law"),
    ]


def test_mention_provenance():
    records = run("see EU:C:2014:238.")
    m = records[0].mentions[0]
    assert (m.text_field, m.language, m.text_source, m.raw_text) == (
        "fulltext",
        "en",
        "HUDOC",
        "EU:C:2014:238",
    )
    assert (m.char_start, m.char_end) == (4, 17) and "see" in m.context
    assert records[0].extractor_version == "echr_text/1.0.0"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DSN = os.environ.get("CLE_TEST_PG_DSN")
needs_db = pytest.mark.skipif(not DSN, reason="CLE_TEST_PG_DSN not set")


@pytest.fixture
def conn():
    psycopg2 = pytest.importorskip("psycopg2")
    name = "cle_echr_text_test_" + uuid.uuid4().hex[:8]
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
            cursor.execute(
                """
                INSERT INTO cle_v2.cases (id, ecli, celex_id, item_id, date_decision, sources)
                OVERRIDING SYSTEM VALUE VALUES
                  (1, 'ECLI:CE:ECHR:2021:0101JUD000000121', NULL, '001-1', '2021-01-01', '{ECHR}'),
                  (2, 'ECLI:CE:ECHR:2022:0101JUD000000222', NULL, '001-2', '2022-01-01', '{ECHR}'),
                  (10, 'ECLI:EU:C:2020:791', '62018CJ0511', NULL, '2020-10-06', '{CJEU}'),
                  (11, 'ECLI:EU:C:2020:6', '62018CC0511', NULL, '2020-01-15', '{CJEU}'),
                  (12, 'ECLI:EU:C:2020:7', '62018CC0520', NULL, '2020-01-15', '{CJEU}'),
                  (13, 'ECLI:EU:C:2010:104', '62008CJ0135', NULL, '2010-03-02', '{CJEU}'),
                  (20, 'ECLI:NL:HR:2011:BR0132', NULL, NULL, '2011-07-01', '{RS}');
                INSERT INTO cle_v2.case_identifier
                  (case_id, scheme, value, value_normalized, source)
                VALUES
                  (10, 'cjeu_case_number', 'C-511/18', 'C-511/18', 'cjeu_document.case_number'),
                  (11, 'cjeu_case_number', 'C-511/18', 'C-511/18', 'cjeu_document.case_number'),
                  (12, 'cjeu_case_number', 'C-520/18', 'C-520/18', 'cjeu_document.case_number'),
                  (13, 'cjeu_case_number', 'C-135/08', 'C-135/08', 'cjeu_document.case_number'),
                  (20, 'ljn', 'BR0132', 'BR0132', 'rs_document.replaces_identifier');
                INSERT INTO cle_v2.echr_document (item_id, case_id, language, doctype) VALUES
                  ('001-1', 1, 'en', 'HEJUD'), ('001-1b', 1, 'fr', 'HFJUD'),
                  ('001-2', 2, 'en', 'HEJUD');
                INSERT INTO cle_v2.case_text (case_id, language, source, fulltext) VALUES
                  (1, 'en', 'HUDOC', %s), (2, 'en', 'HUDOC', %s),
                  (10, 'en', 'CELLAR_ITEM', 'C-135/08 not scanned here');
                INSERT INTO cle_v2.echr_document_secondary_text (item_id, fulltext) VALUES
                  ('001-1b', 'Voir l’arrêt Rottmann, C-135/08, EU:C:2010:104.');
                INSERT INTO cle_v2.echr_extractor_segments (item_id, facts, law) VALUES
                  ('001-2', 'The domestic court relied on the judgment in Rottmann , C ‑ 135/08 '
                            'and followed it closely in every respect.', NULL);
                """,
                (
                    "THE FACTS 1. " + LQDN + " THE LAW 2. Hoge Raad LJN BR0132.",
                    "1. The domestic court relied on the judgment in Rottmann , C ‑ 135/08 "
                    "and followed it closely in every respect. 2. See also EU:C:2099:1.",
                ),
            )
        db.commit()
        yield db
    finally:
        db.close()
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
        admin.close()


@needs_db
def test_extract_from_database_writes_one_file_per_dataset_and_loads(conn, tmp_path):
    from data_loading.link_loader import load_artifact

    out = tmp_path / "links"
    out.mkdir()
    result = echr_text.extract(conn, id_range=(1, 5), out_path=str(out), batch_size=1)
    assert result["by_dataset"] == {"echr_text_cjeu": 4, "echr_text_rs": 1}
    cjeu = list(read_jsonl(out / "echr_text_cjeu.jsonl"))
    rs = list(read_jsonl(out / "echr_text_rs.jsonl"))
    summary = sorted(
        (r.source.ecli[-6:], r.relation_type, r.target.ecli if r.target else None,
         sorted({(m.text_source, m.section) for m in r.mentions}))
        for r in cjeu
    )  # fmt: skip
    assert summary == [
        ("000121", "cites", "ECLI:EU:C:2010:104", [("HUDOC_SECONDARY", None)]),
        ("000121", "cites_in_domestic_law", "ECLI:EU:C:2020:791", [("HUDOC", "facts")]),
        ("000222", "cites", "ECLI:EU:C:2099:1", [("HUDOC", None)]),
        ("000222", "cites_in_domestic_law", "ECLI:EU:C:2010:104", [("HUDOC", "facts")]),
    ]
    assert [(r.target.ecli, r.mentions[0].section) for r in rs] == [
        ("ECLI:NL:HR:2011:BR0132", "law")
    ]

    counts = {}
    for name in ("echr_text_cjeu.jsonl", "echr_text_rs.jsonl"):
        counts.update(load_artifact(conn, out / name))
    assert counts["echr_text_cjeu"]["inserted"] == 3
    assert counts["echr_text_cjeu"]["inserted_unresolved"] == 1
    assert counts["echr_text_rs"]["inserted"] == 1
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM cle_v2.case_citation_mention WHERE case_text_id IS NOT NULL"
        )
        assert cursor.fetchone()[0] >= 4


@needs_db
def test_extract_by_case_ids_single_file(conn, tmp_path):
    out = tmp_path / "all.jsonl"
    result = echr_text.extract(conn, case_ids=[2], out_path=str(out))
    assert result["records"] == 2
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert {line["source"]["ecli"] for line in lines} == {"ECLI:CE:ECHR:2022:0101JUD000000222"}
