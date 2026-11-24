"""
Rechtspraak text extractor (data_extraction/linking/rs_text.py, roadmap R2.1).

The pure tests feed texts and an in-memory lookup to rs_text.extract_records.
Short citation strings are built for the mechanics only; real passages come
from the research files (ECtHR texts quoted in echr/handcheck.txt) and are
marked as such. The database test (extract over a scratch database built from
db/schema.sql) runs only with CLE_TEST_PG_DSN, like test_link_loader.py.
"""

import json
import os
import uuid
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from data_extraction.linking import rs_text
from data_extraction.linking.artifact import read_jsonl
from data_extraction.linking.resolver import Candidate

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"

# CJEU documents (CELEX, ECLI, date) used by the lookups below.
TJEBBES = Candidate(
    1, "ECLI:EU:C:2019:189", "62017CJ0221", None, date(2019, 3, 12), "judgment", "C-221/17"
)
TJEBBES_AG = Candidate(
    2, "ECLI:EU:C:2018:639", "62017CC0221", None, date(2018, 7, 12), "opinion", "C-221/17"
)
XYZ = Candidate(
    3, "ECLI:EU:C:2013:720", "62012CJ0199", None, date(2013, 11, 7), "judgment", "C-199/12"
)
XYZ_AG = Candidate(
    4, "ECLI:EU:C:2013:474", "62012CC0199", None, date(2013, 7, 11), "opinion", "C-199/12"
)
# Non-lead joined members carry the lead judgment (case_identifier from Cellar joins).
XYZ_200 = Candidate(
    3, "ECLI:EU:C:2013:720", "62012CJ0199", None, date(2013, 11, 7), "judgment", "C-200/12"
)
XYZ_201 = Candidate(
    3, "ECLI:EU:C:2013:720", "62012CJ0199", None, date(2013, 11, 7), "judgment", "C-201/12"
)
KREUZIGER = Candidate(
    5, "ECLI:EU:C:2018:972", "62016CJ0619", None, date(2018, 11, 6), "judgment", "C-619/16"
)
MAX_PLANCK = Candidate(
    6, "ECLI:EU:C:2018:874", "62016CJ0684", None, date(2018, 11, 6), "judgment", "C-684/16"
)
ORDER_R = Candidate(
    7, "ECLI:EU:C:2021:593", "62021CO0204", None, date(2021, 7, 14), "order", "C-204/21 R"
)
JUDGMENT_204 = Candidate(
    8, "ECLI:EU:C:2023:442", "62021CJ0204", None, date(2023, 6, 5), "judgment", "C-204/21"
)
VAN_GEND = Candidate(
    9, "ECLI:EU:C:1963:1", "61962CJ0026", None, date(1963, 2, 5), "judgment", "26/62"
)

CJEU = {}
for _c in (
    TJEBBES,
    TJEBBES_AG,
    XYZ,
    XYZ_AG,
    XYZ_200,
    XYZ_201,
    KREUZIGER,
    MAX_PLANCK,
    ORDER_R,
    JUDGMENT_204,
    VAN_GEND,
):
    CJEU.setdefault(_c.value.split(" ")[0], []).append(_c)
ECLIS = {c.ecli: c for cs in CJEU.values() for c in cs}

# ECtHR documents of one application number: chamber judgment, GC judgment, decision.
ECHR_JUD_1 = Candidate(
    20,
    "ECLI:CE:ECHR:2004:0101JUD001234500",
    None,
    "001-1",
    date(2004, 1, 1),
    "judgment",
    "12345/00",
)
ECHR_JUD_2 = Candidate(
    21,
    "ECLI:CE:ECHR:2006:0202JUD001234500",
    None,
    "001-2",
    date(2006, 2, 2),
    "judgment",
    "12345/00",
)
ECHR_DEC = Candidate(
    22,
    "ECLI:CE:ECHR:2002:0303DEC001234500",
    None,
    "001-3",
    date(2002, 3, 3),
    "decision",
    "12345/00",
)
ECHR = {"12345/00": [ECHR_JUD_1, ECHR_JUD_2, ECHR_DEC]}
ECLIS.update({c.ecli: c for c in ECHR["12345/00"]})


def lookup():
    return rs_text.StaticLookup(eclis=ECLIS, cjeu=CJEU, echr=ECHR)


def run(text, field="fulltext", ecli="ECLI:NL:RVS:2020:1", decided=date(2020, 6, 1), stats=None):
    source = rs_text.SourceCase(ecli, decided, [(field, "nl", text)])
    return rs_text.extract_records(source, lookup(), stats)


def by_dataset(records, dataset):
    return [r for r in records if r.source_dataset == dataset]


def targets(records, dataset=None):
    return sorted(
        (r.target.to_dict().get("ecli") if r.target else ("ref", r.target_ref_raw))
        for r in records
        if dataset is None or r.source_dataset == dataset
    )


# ---------------------------------------------------------------------------
# ECLIs
# ---------------------------------------------------------------------------


def test_full_and_short_eclis_with_offsets_and_self_citation():
    text = (
        "ECLI:NL:RVS:2020:1\nZie HvJ 12 maart 2019, Tjebbes, ECLI:EU:C:2019:189, en "
        "NL:HR:2020:593; EHRM CE:ECHR:2004:0101JUD001234500."
    )
    stats = Counter()
    records = by_dataset(run(text, stats=stats), rs_text.DATASET_ECLI)
    assert targets(records) == [
        "ECLI:CE:ECHR:2004:0101JUD001234500",
        "ECLI:EU:C:2019:189",
        "ECLI:NL:HR:2020:593",
    ]
    assert stats["ecli_self"] == 1
    for record in records:
        (mention,) = record.mentions
        assert text[mention.char_start : mention.char_end] == mention.raw_text
        assert mention.text_source == "RECHTSPRAAK" and mention.language == "nl"
        assert record.extractor_version == "rs_text/1.0.0" and record.relation_type == "cites"
    tjebbes = next(r for r in records if r.target.ecli == "ECLI:EU:C:2019:189")
    assert (tjebbes.match_method, tjebbes.confidence) == ("ecli", 1.0)
    # An ECLI this database lacks keeps its ECLI as target (written unresolved by the loader).
    hr = next(r for r in records if r.target.ecli == "ECLI:NL:HR:2020:593")
    assert hr.target_ref_raw is None


def test_ecli_trailing_text_not_swallowed():
    hits = rs_text.scan_eclis("ECLI:EU:C:2019:189.Zie ook EU:T:2020:459, rov. 3")
    assert [h.value for h in hits] == ["ECLI:EU:C:2019:189", "ECLI:EU:T:2020:459"]
    assert [h.raw_text for h in hits] == ["ECLI:EU:C:2019:189", "EU:T:2020:459"]


def test_one_record_per_target_with_all_mentions_from_fulltext_and_summary():
    source = rs_text.SourceCase(
        "ECLI:NL:HR:2022:1",
        date(2022, 4, 1),
        [
            ("fulltext", "nl", "HvJ EU 12 maart 2019, C-221/17 (Tjebbes). Later: C-221/17."),
            ("summary", "nl", "Tjebbes (C-221/17)."),
        ],
    )
    (record,) = rs_text.extract_records(source, lookup())
    assert record.target.ecli == "ECLI:EU:C:2019:189"
    assert [(m.text_field, m.raw_text) for m in record.mentions] == [
        ("fulltext", "C-221/17"),
        ("fulltext", "C-221/17"),
        ("summary", "C-221/17"),
    ]


# ---------------------------------------------------------------------------
# CJEU case numbers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("zaak C‑221/17", ["C-221/17"]),  # U+2011
        ("zaak C ‑ 221/17", ["C-221/17"]),  # spaced hyphen
        ("arrest C-04/19 van het Hof", ["C-4/19"]),
        ("HvJ 7 november 2013, C 199/12", ["C-199/12"]),  # plain space with a cue
        ("van Gend & Loos, zaak 26/62", ["26/62"]),
        ("Case 6/64", ["6/64"]),
        ("gevoegde zaken C-6/90 en 9/90", ["C-6/90", "C-9/90"]),
        ("zaak C-89/24 PPU", ["C-89/24"]),
    ],
)
def test_case_number_forms(text, expected):
    hits = rs_text.scan_cjeu_case_numbers(text, max_year=2026)
    assert [h.value for h in hits] == expected


@pytest.mark.parametrize(
    "text",
    [
        "C221/17",  # no separator
        "in 12/34 gevallen",  # letterless without a cue
        "zaaknummer C-12/13",  # Dutch case-number label
        "rolnummer: C 12/13",
        "AWB 12/34",
        "zaak 12/34",  # letterless after 1988 numbering
        "zaak C-12/75",  # C- numbers start in 1989
        "zaak F-12/20",  # Civil Service Tribunal 2005-2016
        "kamer C 12/13 is",  # space only, no CJEU cue
        "BC-12/13",  # letterless fall-back behind a letter
    ],
)
def test_case_number_rejections(text):
    assert rs_text.scan_cjeu_case_numbers(text, max_year=2026) == []


def test_case_number_later_than_source_year_is_left_out():
    assert rs_text.scan_cjeu_case_numbers("zaak C-1/25", max_year=2024) == []


def test_caribbean_context_needs_an_eu_cue():
    text = "Het Gemeenschappelijk Hof van Justitie, zaak C-12/13, overweegt"
    assert rs_text.scan_cjeu_case_numbers(text, max_year=2026) == []
    caribbean_court = "zaak C-12/13 van het Hof"
    assert (
        rs_text.scan_cjeu_case_numbers(
            caribbean_court, source_ecli="ECLI:NL:OGHACMB:2020:1", max_year=2026
        )
        == []
    )
    eu = "Het Gemeenschappelijk Hof verwijst naar HvJ EU, zaak C-221/17"
    assert [h.value for h in rs_text.scan_cjeu_case_numbers(eu, max_year=2026)] == ["C-221/17"]


def test_range_expands_and_joined_members_resolve_to_the_lead_judgment():
    text = "HvJ 7 november 2013, gevoegde zaken C-199/12 tot en met C-201/12, X, Y en Z"
    records = run(text, decided=date(2015, 1, 1))
    (record,) = by_dataset(records, rs_text.DATASET_CJEU)
    assert record.target.ecli == "ECLI:EU:C:2013:720"
    assert record.target_ref_raw == "C-199/12"
    raws = [m.raw_text for m in record.mentions]
    assert raws == ["C-199/12", "C-199/12 tot en met C-201/12", "C-201/12"]


def test_unresolved_range_member_is_not_written_but_written_numbers_are():
    stats = Counter()
    records = run("zaken C-1/99 t/m C-3/99", stats=stats)
    assert targets(records) == [("ref", "C-1/99"), ("ref", "C-3/99")]
    assert stats["cjeu_range_member_unresolved"] == 1
    unresolved = records[0]
    assert unresolved.target is None and unresolved.target_ref_scheme == "cjeu_case_number"
    assert unresolved.confidence is None and unresolved.match_method == "case_number"


def test_judgment_by_default_opinion_only_with_cue():
    (judgment,) = run("HvJ 12 maart 2019, C-221/17, Tjebbes")
    assert judgment.target.celex is None and judgment.target.ecli == "ECLI:EU:C:2019:189"
    assert judgment.match_method == "case_number/cjeu_judgment" and judgment.confidence == 0.95
    (opinion,) = run("zie de conclusie van A-G Mengozzi in zaak C-221/17")
    assert opinion.target.ecli == "ECLI:EU:C:2018:639"
    assert opinion.match_method == "case_number/cjeu_opinion"
    # The cue belongs to another citation (cut at ';'), or a judgment is named after it.
    (other,) = run("conclusie van A-G Mengozzi; HvJ 12 maart 2019, C-221/17")
    assert other.target.ecli == "ECLI:EU:C:2019:189"
    (after_cue,) = run("conclusie van A-G Mengozzi bij het arrest van 12 maart 2019, C-221/17")
    assert after_cue.target.ecli == "ECLI:EU:C:2019:189"
    # "tot de conclusie" without an Advocate General is not a cue.
    (plain,) = run("Het Hof komt tot de conclusie dat zaak C-221/17 van toepassing is")
    assert plain.target.ecli == "ECLI:EU:C:2019:189"


def test_never_a_document_dated_after_the_citing_decision():
    stats = Counter()
    # The opinion (July 2018) exists, the judgment (March 2019) does not yet.
    (record,) = run("conclusie A-G in zaak C-221/17", decided=date(2018, 9, 1))
    assert record.target.ecli == "ECLI:EU:C:2018:639"
    assert run("zaak C-221/17", decided=date(2018, 1, 1), stats=stats) == []
    assert stats["cjeu_only_later_candidates"] == 1


def test_cited_suffix_selects_the_separate_document():
    (order,) = run("beschikking van 14 juli 2021, C-204/21 R", decided=date(2022, 1, 1))
    assert order.target.ecli == "ECLI:EU:C:2021:593"
    (judgment,) = run("arrest van 5 juni 2023, C-204/21", decided=date(2024, 1, 1))
    assert judgment.target.ecli == "ECLI:EU:C:2023:442"


def test_skip_case_number_only_when_nearby_ecli_is_the_same_case():
    # RBGEL:2026:1195: C-684/16 sits 65 characters from the ECLI of C-619/16.
    text = (
        "HvJ EU 6 november 2018, C-619/16, ECLI:EU:C:2018:972 (Kreuziger) en HvJ EU 6 november "
        "2018, C-684/16 (Max-Planck)"
    )
    gap = text.index("C-684/16") - text.index("ECLI:EU:C:2018:972") - len("ECLI:EU:C:2018:972")
    assert gap <= rs_text.NEAR_ECLI_CHARS
    stats = Counter()
    records = run(text, ecli="ECLI:NL:RBGEL:2026:1195", decided=date(2026, 3, 1), stats=stats)
    assert targets(records, rs_text.DATASET_ECLI) == ["ECLI:EU:C:2018:972"]
    assert targets(records, rs_text.DATASET_CJEU) == ["ECLI:EU:C:2018:874"]
    assert stats["cjeu_skipped_near_ecli"] == 1


def test_nearby_unrelated_ecli_far_away_does_not_skip():
    text = "C-619/16" + " " * 100 + "ECLI:EU:C:2018:972"
    records = run(text, decided=date(2020, 1, 1))
    assert targets(records, rs_text.DATASET_CJEU) == ["ECLI:EU:C:2018:972"]


# ---------------------------------------------------------------------------
# ECtHR application numbers
# ---------------------------------------------------------------------------


def test_appnos_need_an_echr_text():
    assert run("besluit nr. 12345/00 van de gemeente") == []


def test_appno_judgment_decision_date_year_and_gc():
    base = "Artikel 8 EVRM. "
    (r,) = run(base + "EHRM 2 februari 2006, X tegen Nederland, nr. 12345/00")
    assert r.target.ecli == ECHR_JUD_2.ecli and r.match_method == "appno/echr_judgment_cited_date"
    (r,) = run(base + "EHRM (dec.) 3 maart 2002, nr. 12345/00")
    assert r.target.ecli == ECHR_DEC.ecli and r.match_method == "appno/echr_decision_cue"
    (r,) = run(base + "X v. the Netherlands, no. 12345/00, ECHR 2004-I")
    assert r.target.ecli == ECHR_JUD_1.ecli and r.match_method == "appno/echr_judgment_cited_year"
    (r,) = run(base + "X t. Nederland [GC], klachtnummer 12345/00")
    assert r.target.ecli == ECHR_JUD_1.ecli
    assert (
        r.match_method == "appno/echr_judgment_earliest_of_several_gc_cited"
        and r.confidence == 0.65
    )


def test_appno_lists_and_unresolved():
    records = run("EVRM. EHRM 4 december 2008, S. en Marper t. VK, nrs. 30562/04 en 30566/04")
    assert targets(records) == [("ref", "30562/04"), ("ref", "30566/04")]
    assert all(r.target_ref_scheme == "echr_appno" for r in records)


@pytest.mark.parametrize(
    "text",
    [
        "EVRM. Kamerstukken II 2005/06, 30 300, nr. 12/13",  # parliamentary papers
        "EVRM. Het besluit nr. 123/12 van de raad",  # generic nr. without an ECtHR cue
        "Artikel 6 EVRM. Bezwaar tegen het besluit nr. 123/12",
    ],
)
def test_appno_rejections(text):
    assert run(text) == []


# ---------------------------------------------------------------------------
# Gold set (E-01): every RS -> CJEU citation, with the reference forms
# research goldset/trace2.json recorded in each decision's text
# ---------------------------------------------------------------------------

GOLD_RS = [
    # (source, decision date, field, reference forms found in that field)
    ("ECLI:NL:RVS:2020:423", date(2020, 2, 12), "fulltext", ["EU:C:2019:189"], TJEBBES),
    ("ECLI:NL:HR:2020:593", date(2020, 4, 3), "fulltext", ["EU:C:2019:189", "C-221/17"], TJEBBES),
    # art. 81 RO: only the summary cites (independent review of trace2).
    ("ECLI:NL:HR:2022:637", date(2022, 4, 22), "summary", ["C-221/17", "EU:C:2019:189"], TJEBBES),
    ("ECLI:NL:RVS:2013:2423", date(2013, 12, 18), "fulltext", ["C-199/12"], XYZ),
    ("ECLI:NL:RVS:2013:2424", date(2013, 12, 18), "fulltext", ["C-199/12"], XYZ),
    ("ECLI:NL:RVS:2013:2422", date(2013, 12, 18), "fulltext", ["C-199/12", "C-201/12"], XYZ),
    (
        "ECLI:NL:RVS:2015:2170",
        date(2015, 7, 8),
        "fulltext",
        ["EU:C:2013:720", "C-199/12", "C-201/12"],
        XYZ,
    ),
    (
        "ECLI:NL:RVS:2015:4062",
        date(2015, 12, 23),
        "fulltext",
        ["EU:C:2013:720", "C-199/12", "C-201/12"],
        XYZ,
    ),
]


@pytest.mark.parametrize("source,decided,field,forms,target", GOLD_RS, ids=[g[0] for g in GOLD_RS])
def test_gold_set_rs_citations_found(source, decided, field, forms, target):
    # Each form in its own sentence, as a citation would carry it ("HvJ ... <form>").
    text = " ".join(f"Zie HvJ, {form}." for form in forms)
    records = run(text, field=field, ecli=source, decided=decided)
    assert target.ecli in targets(records)
    assert all(m.text_field == field for r in records for m in r.mentions)


# ---------------------------------------------------------------------------
# Real passages from the research files (ECtHR texts, echr/handcheck.txt)
# ---------------------------------------------------------------------------


def test_handcheck_passage_with_u2011_and_short_eclis():
    # echr/handcheck.txt row 3769528 (C-175/11, D. and A.)
    text = (
        "(see, to that effect, judgment of 31 January 2013, D. and A., C‑175/11, EU:C:2013:45, "
        "paragraph 99, and ECtHR, 28 June 1984, Campbell and Fell v. United Kingdom , "
        "CE:ECHR:1984:0628JUD000781977, § 79; 2 June 2005, Zolotas v"
    )
    da = Candidate(
        30, "ECLI:EU:C:2013:45", "62011CJ0175", None, date(2013, 1, 31), "judgment", "C-175/11"
    )
    source = rs_text.SourceCase("ECLI:NL:RVS:2020:1", date(2020, 1, 1), [("fulltext", "en", text)])
    stats = Counter()
    records = rs_text.extract_records(
        source, rs_text.StaticLookup(eclis={da.ecli: da}, cjeu={"C-175/11": [da]}), stats
    )
    assert targets(records, rs_text.DATASET_ECLI) == [
        "ECLI:CE:ECHR:1984:0628JUD000781977",
        "ECLI:EU:C:2013:45",
    ]
    # The case number sits next to the ECLI of the same case: the ECLI is the citation.
    assert by_dataset(records, rs_text.DATASET_CJEU) == []
    assert stats["cjeu_skipped_near_ecli"] == 1


# ---------------------------------------------------------------------------
# Database entry point
# ---------------------------------------------------------------------------

DSN = os.environ.get("CLE_TEST_PG_DSN")
needs_db = pytest.mark.skipif(not DSN, reason="CLE_TEST_PG_DSN not set")


@pytest.fixture
def conn():
    psycopg2 = pytest.importorskip("psycopg2")
    name = "cle_rs_text_test_" + uuid.uuid4().hex[:8]
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
                INSERT INTO cle_v2.cases (ecli, celex_id, item_id, date_decision, sources) VALUES
                  ('ECLI:NL:HR:2022:637', NULL, NULL, '2022-04-22', '{RS}'),
                  ('ECLI:NL:RVS:2013:2422', NULL, NULL, '2013-12-18', '{RS}'),
                  ('ECLI:EU:C:2019:189', '62017CJ0221', NULL, '2019-03-12', '{CJEU}'),
                  ('ECLI:EU:C:2018:639', '62017CC0221', NULL, '2018-07-12', '{CJEU}'),
                  ('ECLI:EU:C:2013:720', '62012CJ0199', NULL, '2013-11-07', '{CJEU}'),
                  ('ECLI:CE:ECHR:2004:0101JUD001234500', NULL, '001-1', '2004-01-01', '{ECHR}'),
                  ('ECLI:NL:RVS:2099:1', NULL, NULL, '2099-01-01', '{RS}');
                INSERT INTO cle_v2.case_identifier
                       (case_id, scheme, value, value_normalized, source)
                SELECT c.id, v.scheme, v.value, v.value, v.src
                  FROM (VALUES
                    ('ECLI:EU:C:2019:189', 'cjeu_case_number', 'C-221/17', 'cjeu_document'),
                    ('ECLI:EU:C:2018:639', 'cjeu_case_number', 'C-221/17', 'cjeu_document'),
                    ('ECLI:EU:C:2013:720', 'cjeu_case_number', 'C-199/12', 'cjeu_document'),
                    ('ECLI:EU:C:2013:720', 'cjeu_case_number', 'C-201/12', 'cellar_joins'),
                    ('ECLI:CE:ECHR:2004:0101JUD001234500', 'echr_appno', '12345/00', 'appno'),
                    ('ECLI:EU:C:2013:720', 'ecli', 'ECLI:EU:C:2013:999', 'test alias')
                  ) AS v(ecli, scheme, value, src)
                  JOIN cle_v2.cases c ON c.ecli = v.ecli;
                INSERT INTO cle_v2.echr_document (item_id, case_id, language, doctype)
                SELECT '001-1', id, 'en', 'HEJUD' FROM cle_v2.cases WHERE item_id = '001-1';
                INSERT INTO cle_v2.case_text (case_id, language, source, fulltext, summary)
                SELECT id, 'nl', 'RECHTSPRAAK', NULL,
                       'Art. 81 RO. Tjebbes (C-221/17, EU:C:2019:189).'
                  FROM cle_v2.cases WHERE ecli = 'ECLI:NL:HR:2022:637';
                INSERT INTO cle_v2.case_text (case_id, language, source, fulltext, summary)
                SELECT id, 'nl', 'RECHTSPRAAK',
                       'ECLI:NL:RVS:2013:2422. HvJ 7 november 2013, C-199/12 en C-201/12; '
                       || 'EVRM: EHRM, nr. 12345/00; zaak C-5/13.' || repeat(' ', 100)
                       || 'ECLI:EU:C:2013:999 als alias.',
                       NULL
                  FROM cle_v2.cases WHERE ecli = 'ECLI:NL:RVS:2013:2422';
                INSERT INTO cle_v2.case_text (case_id, language, source, fulltext)
                SELECT id, 'en', 'HUDOC', 'C-221/17' FROM cle_v2.cases
                 WHERE ecli = 'ECLI:CE:ECHR:2004:0101JUD001234500';
                """)
        db.commit()
        yield db
    finally:
        db.close()
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
        admin.close()


def _key(record):
    return (
        record.source.ecli,
        record.source_dataset,
        record.target.to_dict() if record.target else record.target_ref_raw,
    )


@needs_db
def test_extract_against_database(conn, tmp_path):
    out = tmp_path / "rs_text.jsonl"
    written, stats = rs_text.extract(conn, out_path=out, batch_size=1)
    records = list(read_jsonl(out))
    assert written == len(records)
    keys = sorted(map(_key, records), key=json.dumps)
    assert keys == sorted(
        [
            ("ECLI:NL:HR:2022:637", "rs_text_ecli", {"ecli": "ECLI:EU:C:2019:189"}),
            # The summary's case number sits next to the ECLI of the same case: skipped.
            ("ECLI:NL:RVS:2013:2422", "rs_text_cjeu_casenum", {"ecli": "ECLI:EU:C:2013:720"}),
            ("ECLI:NL:RVS:2013:2422", "rs_text_cjeu_casenum", "C-5/13"),
            ("ECLI:NL:RVS:2013:2422", "rs_text_ecli", {"ecli": "ECLI:EU:C:2013:720"}),
            (
                "ECLI:NL:RVS:2013:2422",
                "rs_text_echr_appno",
                {"ecli": "ECLI:CE:ECHR:2004:0101JUD001234500"},
            ),
        ],
        key=json.dumps,
    )
    assert stats["cjeu_skipped_near_ecli"] == 1 and stats["ecli_self"] == 1
    xyz = next(
        r for r in records if r.source_dataset == "rs_text_cjeu_casenum" and r.target is not None
    )
    assert [m.raw_text for m in xyz.mentions] == ["C-199/12", "C-201/12"]
    alias = next(
        r for r in records if r.source_dataset == "rs_text_ecli" and r.source.ecli.endswith("2422")
    )
    assert alias.match_method == "ecli/case_identifier"
    summary = next(r for r in records if r.source.ecli == "ECLI:NL:HR:2022:637")
    (mention,) = summary.mentions
    assert mention.text_field == "summary" and mention.raw_text == "EU:C:2019:189"

    # The artifact loads through the insert-only link loader, twice without change.
    from data_loading.link_loader import load_artifact

    counts = load_artifact(conn, out)
    assert counts["rs_text_cjeu_casenum"] == {
        "inserted": 1,
        "inserted_unresolved": 1,
        "mentions_inserted": 3,
    }
    assert counts["rs_text_ecli"]["inserted"] == 2
    assert counts["rs_text_echr_appno"]["inserted"] == 1
    again = load_artifact(conn, out)
    assert all("inserted" not in c and "mentions_inserted" not in c for c in again.values())


@needs_db
def test_extract_by_case_ids_and_range(conn, tmp_path):
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM cle_v2.cases WHERE ecli = 'ECLI:NL:HR:2022:637'")
        (hr,) = cursor.fetchone()
    written, _ = rs_text.extract(conn, case_ids=[hr], out_path=tmp_path / "a.jsonl")
    assert written == 1
    written, _ = rs_text.extract(conn, id_range=(hr + 1, hr + 1), out_path=tmp_path / "b.jsonl")
    assert written == 4  # RVS:2013:2422 is the next case


@needs_db
def test_cli(conn, tmp_path, monkeypatch):
    base, _, _ = DSN.rpartition("/")
    with conn.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        (name,) = cursor.fetchone()
    monkeypatch.setenv("RS_TEXT_TEST_DSN", f"{base}/{name}")
    out = tmp_path / "cli.jsonl"
    assert (
        rs_text.main(
            ["--dsn-env", "RS_TEXT_TEST_DSN", "--from-id", "1", "--to-id", "1", "--out", str(out)]
        )
        == 0
    )
    assert len(list(read_jsonl(out))) == 1
