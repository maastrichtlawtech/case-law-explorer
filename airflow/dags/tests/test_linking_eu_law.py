"""
EU-law references (roadmap R3.2-R3.4): CELEX rules, the text scanner, the
law-reference artifact and the record builders. Pure; no database.

Real text: only three EU-law references exist in the research files
(ECtHR passages in research-2026-11-24/echr/handcheck.txt, also in
fixtures/linking_evaluation.json); they are tested as REAL_PASSAGES. Every
other string here is ILLUSTRATIVE: written for the test in the forms courts
use, not copied from a judgment (see fixtures/precision_eu_law.md).
"""

import json
from collections import Counter
from datetime import date

import pytest

from data_extraction.linking import cellar_law_refs, eu_law, eu_law_text
from data_extraction.linking.artifact import ArtifactError, ArtifactWriter, CaseKey
from data_extraction.linking.law_artifact import LawReferenceRecord, LawTarget, read_jsonl
from data_extraction.linking.text_common import TextUnit


def refs(text, decided=date(2024, 6, 1), profile="rs"):
    return [(h.celex, h.raw_subdivision) for h in eu_law.scan(text, decided, profile)]


# ---------------------------------------------------------------------------
# CELEX rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, a, b, nr, expected",
    [
        ("L", "2011", "95", False, "32011L0095"),
        ("L", "93", "13", False, "31993L0013"),
        ("R", "2016", "679", False, "32016R0679"),
        ("R", "1408", "71", True, "31971R1408"),
        ("R", "604", "2013", True, "32013R0604"),
        ("R", "883", "2004", False, "32004R0883"),
        ("F", "2002", "584", False, "32002F0584"),
        ("D", "2010", "405", False, "32010D0405"),
        ("L", "1", "80", False, None),  # "Besluit nr. 1/80": year 1 is not a year
        ("L", "2011", "0", False, None),
        ("R", "2016", "2015", False, "32016R2015"),  # year/number from 2015
        ("R", "604", "2016", True, None),  # number/year ended in 2014
        ("L", "1993", "13", False, "31993L0013"),  # four-digit years from 1952
        ("L", "1951", "13", False, None),
        ("L", "99", "44", False, None),  # two-digit years before 1999 only
    ],
)
def test_act_celex(kind, a, b, nr, expected):
    assert eu_law.act_celex(kind, a, b, nr) == expected


# Illustrative strings (review findings of 2026-11-24), not copied from judgments.
@pytest.mark.parametrize(
    "text, celex",
    [
        ("Richtlijn 2003/9/EG", "32003L0009"),  # act numbers 1-9
        ("Directive 2011/7/EU", "32011L0007"),
        ("Verordening (EU) 2015/1", "32015R0001"),
        ("Richtlijn 1995/46/EG", "31995L0046"),  # four-digit years before 1999
        ("Directive 1993/13/EEC", "31993L0013"),
        ("Verordening (EEG) nr. 1408/1971", "31971R1408"),
        ("Verordening (EU) nr. 2016/679", "32016R0679"),  # year/number despite "nr."
        ("Verordening (EU) nr. 2016/2000", "32016R2000"),  # no (EU) act from 2000
        ("Verordening (EG) nr. 2016/2000", "32000R2016"),  # number/year: both year-like
        ("Verordening (EG) nr. 1408/71", "31971R1408"),
    ],
)
def test_act_numbers_from_the_review(text, celex):
    assert [h.celex for h in eu_law.scan(text, date(2024, 6, 1))] == [celex]


def test_aeuv_is_the_tfeu():
    """Illustrative (German abbreviation)."""
    assert refs("Art. 267 AEUV") == [("12016E/TXT", "267")]


def test_ec_treaty_versions_newest_first():
    ec = eu_law.TREATIES["EC"]
    assert (ec.raw_resource, ec.alternatives[:2]) == ("12006E/TXT", ("12006E", "12002E/TXT"))
    assert eu_law.TREATIES["TEU_1997"].raw_resource == "12006M/TXT"


def test_act_celex_rejects_acts_after_the_citing_decision():
    assert eu_law.act_celex("L", "2011", "95", False, max_year=2010) is None
    assert eu_law.act_celex("L", "2011", "95", False, max_year=2011) == "32011L0095"


@pytest.mark.parametrize(
    "celex, identifier, alternatives, article, sector",
    [
        ("12008E267", "12008E267", ("12008E/TXT", "12008E"), "267", "1"),
        ("12016P047", "12016P047", ("12016P/TXT", "12016P"), "47", "1"),
        ("11992E130R", "11992E130R", ("11992E/TXT", "11992E"), "130r", "1"),
        ("12012P/TXT", "12012P/TXT", ("12012P",), None, "1"),
        ("12008M", "12008M", ("12008M/TXT",), None, "1"),
        ("32011L0095", "32011L0095", (), None, "3"),
        ("32004L0038R(01)", "32004L0038R(01)", (), None, "3"),
        ("21994A1231(01)", "21994A1231(01)", (), None, "2"),
        ("41994X1231", "41994X1231", (), None, "4"),
        ("02016R0679-20160504", "02016R0679-20160504", ("32016R0679",), None, "0"),
        (" celex:32016r0679 ", "32016R0679", (), None, "3"),
    ],
)
def test_cellar_target(celex, identifier, alternatives, article, sector):
    target = eu_law.cellar_target(celex)
    assert target == eu_law.CellarTarget(sector, identifier, alternatives, article)


@pytest.mark.parametrize("celex", ["52012PC0011", "62017CJ0221", "71995L0046FRA", "C2012/326", ""])
def test_cellar_target_skips_what_is_not_a_law_reference(celex):
    assert eu_law.cellar_target(celex) is None


def test_treaty_fixture_is_consistent():
    for treaty in eu_law.TREATIES.values():
        assert treaty.raw_resource.endswith("/TXT")
        assert treaty.raw_resource not in treaty.alternatives
        assert len(set(treaty.alternatives)) == len(treaty.alternatives)
        for celex in (treaty.raw_resource,) + treaty.alternatives:
            assert eu_law.cellar_target(celex).sector == "1"


# ---------------------------------------------------------------------------
# Scanner: the forms named in the roadmap (ILLUSTRATIVE strings)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Richtlijn 2011/95/EU", [("32011L0095", None)]),
        ("Verordening (EU) 2016/679", [("32016R0679", None)]),
        ("Verordening (EG) nr. 1408/71", [("31971R1408", None)]),
        ("artikel 267 VWEU", [("12016E/TXT", "267")]),
        ("art. 47 Handvest", [("12016P/TXT", "47")]),
        ("Kaderbesluit 2002/584/JBZ", [("32002F0584", None)]),
        ("artikel 4, lid 3, VEU", [("12016M/TXT", "4(3)")]),
        ("artikel 4, derde lid, VEU", [("12016M/TXT", "4(3)")]),
        (
            "artikel 15, aanhef en onder c, van Richtlijn 2011/95/EU",
            [("32011L0095", "15")],
        ),
        ("artikel 3, tweede lid, van Verordening (EU) nr. 604/2013", [("32013R0604", "3(2)")]),
        ("artikelen 7 en 8 van het Handvest", [("12016P/TXT", "7"), ("12016P/TXT", "8")]),
        ("artikel 267, derde alinea, VWEU", [("12016E/TXT", "267")]),
        (
            "artikel 47 van het Handvest van de grondrechten van de Europese Unie",
            [("12016P/TXT", "47")],
        ),
        ("artikel 6, eerste lid, aanhef en onder e, van de AVG", [("32016R0679", "6(1)")]),
        ("Richtlijnen 2004/83/EG en 2011/95/EU", [("32004L0083", None), ("32011L0095", None)]),
        ("Besluit 2010/405/EU", [("32010D0405", None)]),
        ("Beschikking 2000/520/EG", [("32000D0520", None)]),
        ("Uitvoeringsverordening (EU) 2018/1724", [("32018R1724", None)]),
        # English and French (ECtHR texts)
        ("Directive 2013/32/EU", [("32013L0032", None)]),
        ("Council Directive 2003/86/EC of 22 September 2003", [("32003L0086", None)]),
        ("Article 3(2) of Regulation (EU) No 604/2013", [("32013R0604", "3(2)")]),
        ("Regulation (EC) No. 1408/71", [("31971R1408", None)]),
        ("Council Framework Decision 2002/584/JHA", [("32002F0584", None)]),
        ("décision-cadre 2002/584/JAI", [("32002F0584", None)]),
        ("règlement (UE) n° 604/2013", [("32013R0604", None)]),
        ("article 267 TFUE", [("12016E/TXT", "267")]),
        ("Article 6 TEU", [("12016M/TXT", "6")]),
        (
            "Article 47 of the Charter of Fundamental Rights of the European Union",
            [("12016P/TXT", "47")],
        ),
        (
            "article 47 de la Charte des droits fondamentaux de l'Union européenne",
            [("12016P/TXT", "47")],
        ),
        ("Article 6 GDPR", [("32016R0679", "6")]),
    ],
)
def test_scan_finds_the_forms(text, expected):
    assert refs(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Besluit nr. 1/80 van de Associatieraad",  # not an EU act of this form
        "het besluit van 12 mei 2010/405",  # decision without suffix
        "artikel 8:69 Awb",  # Dutch law
        "artikel 6 EVRM",  # Convention: not EU law, and in BWB already
        "Article 6 § 1 of the Convention",
        "Article 1 of that Directive",  # anaphora
        "de Kwalificatierichtlijn",  # names two directives
        "artikel 999 VWEU",  # no such article
        "artikel 60 Handvest",  # the Charter has 54 articles
        "Richtlijn 2030/1/EU",  # after the citing decision
        "de Algemene plaatselijke verordening 2015",
        "het VWEU",  # a treaty only with an article
        "de AVG",  # the abbreviation only with an article
        "Article 6 EU",  # 'EU' alone is ambiguous
        "the EC Commission",
    ],
)
def test_scan_rejects(text):
    assert refs(text) == []


def test_act_number_after_an_unrelated_article_keeps_no_article():
    assert refs("artikel 8:69 Awb en Richtlijn 2011/95/EU") == [("32011L0095", None)]


def test_suffix_inside_an_act_number_is_not_the_ec_treaty():
    assert refs("artikel 2 van Richtlijn 2004/38/EG") == [("32004L0038", "2")]


def test_ec_treaty_needs_the_article_right_before_it_and_follows_the_date():
    assert refs("artikel 234 EG") == [("12006E/TXT", "234")]
    assert refs("artikel 177 EG-Verdrag", decided=date(1995, 1, 1)) == [("11992E/TXT", "177")]
    assert refs("artikel 234 van het EG") == []


def test_ec_treaty_old_numbering_cue():
    assert refs("artikel 85 EG-Verdrag (oud)") == [("11992E/TXT", "85")]
    assert refs("Article 81 EC") == [("12006E/TXT", "81")]
    assert {h.confidence for h in eu_law.scan("artikel 81 EG", date(2005, 1, 1))} == {0.8}


def test_teu_before_lisbon():
    assert refs("artikel 6 VEU", decided=date(2005, 1, 1)) == [("12006M/TXT", "6")]


def test_bare_charter_in_rechtspraak_text():
    assert refs("artikel 47 Handvest") == [("12016P/TXT", "47")]
    # another charter in the text: only the full name counts
    text = "artikel 47 Handvest; artikel 6 van het Europees Sociaal Handvest"
    assert refs(text) == []
    text = "artikel 24 van het Handvest van de grondrechten; het Europees Sociaal Handvest"
    assert refs(text) == [("12016P/TXT", "24")]


def test_bare_charter_in_echr_text_needs_the_full_name_somewhere():
    assert refs("Article 47 of the Charter", profile="echr") == []
    text = (
        "The Charter of Fundamental Rights of the European Union provides ... "
        "Article 47 of the Charter"
    )
    assert refs(text, profile="echr") == [("12016P/TXT", "47")]
    text += " ... the European Social Charter"
    assert refs(text, profile="echr") == []


def test_ecthr_paragraph_sign_and_lists():
    assert refs("Articles 7, 8 and 52 § 1 of the Charter of Fundamental Rights") == [
        ("12016P/TXT", "52(1)"),
        ("12016P/TXT", "7"),
        ("12016P/TXT", "8"),
    ]


def test_offsets_cover_the_whole_citation():
    text = "Gelet op artikel 4, lid 3, VEU en artikel 267 VWEU."
    hits = eu_law.scan(text, date(2024, 1, 1))
    assert [text[h.start : h.end] for h in hits] == ["artikel 4, lid 3, VEU", "artikel 267 VWEU"]


# ---------------------------------------------------------------------------
# Real passages (research-2026-11-24/echr/handcheck.txt)
# ---------------------------------------------------------------------------

REAL_PASSAGES = [
    # (case_id in the research file, passage as stored, expected references)
    (
        3773393,
        "y analogy to grounds of discrimination other than those that were explicitly listed "
        "in Article 1 of that Directive.  129 . In this connection, the Supreme Court relied on "
        "the following: judgment of 11 July 2006, Sonia Chacón Navas v Eurest Colectividades SA "
        ", C-13/05, ECLI:EU:C:2006:456, in which the CJEU had held that Directive 2000/78/EC "
        "could not be extended by analogy to prohibit discrimination on the grounds of ",
        [("32000L0078", None)],
    ),
    (
        3722101,
        "o free prescriptions was not objectively justified to ensure coherence between the "
        "retirement pension system and the regulations concerning prescriptions and was not "
        "necessarily linked to the difference between pensionable ages for men and women.  In "
        "the Case C-9/91 The Queen v. Secretary of State for Social Security , ex parte Equal "
        "Opportunities Commission [2000] ECR I-3701 (“the EOC case” concerning reference for ",
        [],
    ),
    (
        3779973,
        "bsence of such case-law, that the interpretation of EU law was so obvious to the "
        "national court or tribunal of last instance as to leave no scope for any reasonable "
        "doubt.”  21 . The CJEU confirmed this obligation in its judgment of 15 October 2024 in "
        "KUBERA (C-144/23, EU:C:2024:881, paragraph 65) in the context of decisions refusing "
        "leave to appeal:  “... Article 267 TFEU, read in the light of the second paragraph o",
        [("12016E/TXT", "267")],
    ),
    (
        3742097,
        "ge classes where necessary for them to undergo normal schooling.  In 2007 the European "
        "Commission asked the CJEC (now the CJEU) to examine whether Greece was fulfilling its "
        "obligations concerning the reception of refugees. In a judgment of 19 April 2007 (Case "
        "C-72/06 Commission v . Greece ), the CJEC found that Greece had failed to fulfil its "
        "obligations under the Reception Directive. The Greek authorities subsequent",
        [],  # "the Reception Directive" names no number (2003/9/EC or 2013/33/EU)
    ),
    (
        3776363,
        "e que modifiée, doit prendre toutes les mesures nécessaires afin de s’acquitter de ses "
        "obligations au titre de l’article 16, paragraphe 6, de ladite directive et des points "
        "3.2, 3.3, 4.1 à 4.3 et 5.1 de l’annexe II de celle-ci (CJUE, 16 février 2017, Schmitt, "
        "C-219/15).  Il résulte de cette décision que, en présence d’indices laissant supposer "
        "qu’un dispositif médical ne serait pas conforme aux exigences qui découlen",
        [],  # "ladite directive": anaphora
    ),
    (
        3755428,
        "1 on law enforcement operational needs with respect to public telecommunication "
        "networks and services.  147. The judgment the Court of Justice of the European Union "
        "(CJEU) of 8 April 2014 in the joined cases of Digital Rights Ireland and Seitinger and "
        "Others (C-293/12 and C-594/12, EU:C:2014:238) declared invalid the Data Retention "
        "Directive 2006/24/EC laying down the obligation on the providers of publicly available",
        [("32006L0024", None)],
    ),
]


@pytest.mark.parametrize("case_id, text, expected", REAL_PASSAGES)
def test_real_passages(case_id, text, expected):
    assert refs(text, decided=date(2026, 1, 1), profile="echr") == expected


# Real Dutch text: annotation titles in Cellar's national_judgement field
# (research-2026-11-24/cjeu/nj_nl.json, entries 427 = C-126/97 Eco Swiss,
# 1 June 1999, and 885 = C-271/17 PPU). Not a text the extractors scan, but
# the only real Dutch EU-law references in the research files.
REAL_DUTCH = [
    (
        "Stuyck, J.: (ambtshalve) Toepassing van de nietigheidssanctie van artikel 85, tweede "
        "lid EG-Verdrag in het kader van arbitrage?, Nederlands tijdschrift vo",
        date(1999, 6, 1),
        # read as Amsterdam art. 85(2); the author meant the old art. 85(2)
        # (competition), so this one is WRONG (see precision_eu_law.md)
        [("12006E/TXT", "85(2)")],
    ),
    (
        "Hoogervorst, F.M.: Strijd met openbare orde wegens schending art. 81 EG; vernietiging "
        "arbitraal vonnis, Nederlands tijdschrift voor burgerlij",
        date(1999, 6, 1),
        [("12006E/TXT", "81")],
    ),
    (
        "Garben, Sacha; Janssen, Sally: Kaderbesluit 2002/584/JBZ - Europees aanhoudingsbevel - "
        "Artikel 4bis - Gronden t",
        date(2017, 8, 10),
        [("32002F0584", None)],
    ),
]


@pytest.mark.parametrize("text, decided, expected", REAL_DUTCH)
def test_real_dutch_passages(text, decided, expected):
    assert refs(text, decided=decided) == expected


# ---------------------------------------------------------------------------
# Artifact and records
# ---------------------------------------------------------------------------

SOURCE = CaseKey(ecli="ECLI:NL:RVS:2020:423")


def test_text_records_merge_mentions_per_act_and_subdivision(tmp_path):
    units = [
        TextUnit(
            "Gelet op artikel 47 Handvest en Richtlijn 2011/95/EU. Ook artikel 47 Handvest.",
            "fulltext",
            "nl",
            "RECHTSPRAAK",
        ),
        TextUnit("Richtlijn 2011/95/EU", "summary", "nl", "RECHTSPRAAK"),
    ]
    source = eu_law_text.TextSource(SOURCE, date(2020, 2, 12))
    records = eu_law_text.records_for(source, units, "rs_text_eu_law", "rs")
    by_key = {(r.raw_resource, r.raw_subdivision): r for r in records}
    assert set(by_key) == {("12016P/TXT", "47"), ("32011L0095", None)}
    charter = by_key[("12016P/TXT", "47")]
    assert charter.target == LawTarget(
        "celex", "12016P/TXT", eu_law.TREATIES["CHARTER"].alternatives
    )
    assert charter.article == "47"
    assert charter.raw_reference == "artikel 47 Handvest"
    assert [m.char_start for m in charter.mentions] == [9, 58]
    directive = by_key[("32011L0095", None)]
    assert [m.text_field for m in directive.mentions] == ["fulltext", "summary"]
    assert directive.match_method == "act_number" and directive.role == "cited"

    path = tmp_path / "rs_text_eu_law.jsonl"
    with ArtifactWriter(path) as writer:
        writer.write(records)
    assert list(read_jsonl(path)) == sorted(
        records, key=lambda r: json.dumps(r.to_dict(), sort_keys=True, ensure_ascii=False)
    )
    again = tmp_path / "again.jsonl"
    with ArtifactWriter(again) as writer:
        writer.write(list(reversed(records)))
    assert path.read_bytes() == again.read_bytes()


def test_record_validation():
    good = LawReferenceRecord(
        source=SOURCE,
        target=LawTarget("celex", "32011L0095"),
        raw_scheme="celex",
        raw_resource="32011L0095",
        source_dataset="rs_text_eu_law",
        extractor_version="x/1",
    )
    good.validate()
    assert LawReferenceRecord.from_dict(good.to_dict()) == good
    for change in (
        {"source_dataset": "rs_text_ecli"},
        {"raw_scheme": "bwb"},
        {"match_method": "guess"},
        {"confidence": 1.5},
        {"article": "4"},
    ):
        bad = dict(good.to_dict(), **change)
        with pytest.raises(ArtifactError):
            LawReferenceRecord.from_dict(bad)
    with pytest.raises(ArtifactError):
        LawReferenceRecord.from_dict(
            dict(good.to_dict(), target={"scheme": "bwb", "identifier": "x"})
        )
    with pytest.raises(ArtifactError):
        LawReferenceRecord.from_dict(dict(good.to_dict(), extra=1))


def test_cellar_records_by_sector():
    stats = Counter()
    rows = [
        (1, "ECLI:EU:C:2019:189", "62017CJ0221", None, "32004L0038"),
        (1, "ECLI:EU:C:2019:189", "62017CJ0221", None, "12008E267"),
        (1, "ECLI:EU:C:2019:189", "62017CJ0221", None, "12008E267"),  # repeated row
        (1, "ECLI:EU:C:2019:189", "62017CJ0221", None, "52012PC0011"),  # preparatory: Phase 4
        (1, "ECLI:EU:C:2019:189", "62017CJ0221", None, "62010CJ0001"),  # case law
        (2, None, None, None, "32004L0038"),  # no natural key
    ]
    records = cellar_law_refs.records_from_rows(rows, stats)
    assert sorted((r.raw_resource, r.raw_subdivision) for r in records) == [
        ("12008E267", "267"),
        ("32004L0038", None),
    ]
    treaty = next(r for r in records if r.raw_resource == "12008E267")
    assert treaty.target.identifiers == ("12008E267", "12008E/TXT", "12008E")
    assert treaty.source_dataset == "cellar_law_ref" and treaty.role == "cited"
    assert treaty.match_method == "celex_metadata"
    assert stats == Counter(
        sector_3=1, sector_1=2, skipped_sector_5=1, skipped_sector_6=1, source_without_key=1
    )
