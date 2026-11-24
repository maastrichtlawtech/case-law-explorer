"""
Phase 4 authority extractors, pure parts (no database).

Where the strings come from:

* REAL: copied from the research files in cjeu-migration
  migration/verify/research-2026-11-24/ (cjeu/nj_nl.json, the
  national_judgement notices of 1,119 CJEU documents; cjeu/uuid_rows.json,
  Cellar sector 8 CELEX numbers).
* ILLUSTRATIVE: written for these tests in the citation forms Dutch courts,
  the ECtHR and the UN/Council of Europe use. The research files hold no
  Rechtspraak or HUDOC passages citing parliamentary papers, policy rules, UN
  treaty bodies or Council of Europe bodies, and no rs_document_publication
  rows, so these patterns have no real-data precision figure yet; they need a
  db-dev sample before the data reaches production.
"""

import json

import pytest

from data_extraction.linking import (
    authority_patterns,
    authority_text,
    cellar_authority,
    rs_publication,
)
from data_extraction.linking.artifact import ArtifactError, CaseKey
from data_extraction.linking.authority_artifact import (
    AuthorityDoc,
    AuthorityMention,
    AuthorityRecord,
    read_jsonl,
    write_jsonl,
)


def _ids(text, groups=authority_patterns.GROUPS):
    return [
        (h.doc.kind, h.doc.identifier_scheme, h.doc.identifier, h.pinpoint, text[h.start : h.end])
        for h in authority_patterns.scan(text, groups)
    ]


# ---------------------------------------------------------------------------
# R4.1 parliamentary papers (ILLUSTRATIVE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, scheme, identifier, pinpoint, written",
    [
        (
            "zie Kamerstukken II 2015/16, 34 356, nr. 3, p. 12 en verder",
            "officielebekendmakingen",
            "kst-34356-3",
            "p. 12",
            "Kamerstukken II 2015/16, 34 356, nr. 3, p. 12",
        ),
        (
            "Kamerstukken I 2016/17, 34 356, C, p. 3",
            "officielebekendmakingen",
            "kst-34356-C",
            "p. 3",
            "Kamerstukken I 2016/17, 34 356, C, p. 3",
        ),
        (
            "Kamerstukken II 2016/17, 34 550 VI, nr. 2",
            "officielebekendmakingen",
            "kst-34550-VI-2",
            None,
            "Kamerstukken II 2016/17, 34 550 VI, nr. 2",
        ),
        (
            "Kamerstukken II 2014/15, 21 501-20, nr. 1000",
            "officielebekendmakingen",
            "kst-21501-20-1000",
            None,
            "Kamerstukken II 2014/15, 21 501-20, nr. 1000",
        ),
        (
            "Kamerstukken II 2015-2016, 34 356 (R2034), nr. 3",
            "officielebekendmakingen",
            "kst-34356-3",
            None,
            "Kamerstukken II 2015-2016, 34 356 (R2034), nr. 3",
        ),
        (
            "(MvT, Kamerstukken II 1999/2000, 26 732, nr. 3, blz. 45-46)",
            "officielebekendmakingen",
            "kst-26732-3",
            "blz. 45-46",
            "Kamerstukken II 1999/2000, 26 732, nr. 3, blz. 45-46",
        ),
        (
            "TK 2015–2016, 34 356, nr. 3",
            "officielebekendmakingen",
            "kst-34356-3",
            None,
            "TK 2015–2016, 34 356, nr. 3",
        ),
        (
            "Kamerstukken II 2015/16, 34 356.",
            "nl_kamerstuk_dossier",
            "34356",
            None,
            "Kamerstukken II 2015/16, 34 356",
        ),
        (
            "Handelingen II 2014/15, nr. 45, item 7",
            "officielebekendmakingen",
            "h-tk-20142015-45-7",
            None,
            "Handelingen II 2014/15, nr. 45, item 7",
        ),
        (
            "Handelingen II 2005/06, p. 1234",
            "nl_handelingen_page",
            "h-tk-20052006-p1234",
            "p. 1234",
            "Handelingen II 2005/06, p. 1234",
        ),
    ],
)
def test_parliamentary_papers(text, scheme, identifier, pinpoint, written):
    assert _ids(text) == [("nl_parliamentary_paper", scheme, identifier, pinpoint, written)]


def test_parliamentary_paper_attributes_come_from_the_identifier():
    (hit,) = authority_patterns.scan("Kamerstukken II 2015/16, 34 356, nr. 3")
    assert hit.doc.url == "https://zoek.officielebekendmakingen.nl/kst-34356-3.html"
    assert hit.doc.title == "Kamerstuk 34356, nr. 3"
    (dossier,) = authority_patterns.scan("Kamerstukken II 2015/16, 34 356.")
    assert dossier.doc.url == "https://zoek.officielebekendmakingen.nl/dossier/34356"


@pytest.mark.parametrize(
    "text",
    [
        "Kamerstukken II 2015/17, 34 356, nr. 3",  # sessions must follow each other
        "Kamerstuk 1234",  # neither chamber nor session nor paper
        "de memorie van toelichting (MvT) bij het wetsvoorstel",  # names no document
        "TK 34 356, nr. 3",  # bare TK needs a session
    ],
)
def test_parliamentary_papers_rejected(text):
    assert [i for i in _ids(text) if i[0] == "nl_parliamentary_paper"] == []


def test_letter_numbers_only_for_the_eerste_kamer():
    assert _ids("Kamerstukken II 2016/17, 34 356, A, p. 3") == [
        (
            "nl_parliamentary_paper",
            "nl_kamerstuk_dossier",
            "34356",
            None,
            "Kamerstukken II 2016/17, 34 356",
        )
    ]


# ---------------------------------------------------------------------------
# official publications and R4.2 policy rules (ILLUSTRATIVE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, identifier",
    [
        ("Stb. 2017, 123", "stb-2017-123"),
        ("Stcrt. 2019, 12345;", "stcrt-2019-12345"),
        ("Trb. 1990, 12", "trb-1990-12"),
        ("Staatsblad 2004, nr. 5", "stb-2004-5"),
    ],
)
def test_official_publications(text, identifier):
    (hit,) = authority_patterns.scan(text)
    assert (hit.doc.kind, hit.doc.identifier) == ("nl_official_publication", identifier)
    assert hit.doc.url == f"https://zoek.officielebekendmakingen.nl/{identifier}.html"


def test_official_publications_switch_off():
    groups = authority_text.scan_groups(official_publications=False)
    assert "nl_official" not in groups
    assert authority_patterns.scan("Stb. 2017, 123", groups) == []


def test_official_publication_flag_read_from_env(monkeypatch):
    monkeypatch.setenv("AUTHORITY_NL_OFFICIAL_PUBLICATIONS", "false")
    assert "nl_official" not in authority_text.scan_groups()
    monkeypatch.delenv("AUTHORITY_NL_OFFICIAL_PUBLICATIONS")
    assert "nl_official" in authority_text.scan_groups()


@pytest.mark.parametrize(
    "text, identifier, pinpoint, written",
    [
        ("paragraaf C2/3.2 van de Vc 2000", "vc2000-C", "C2/3.2", None),
        ("Vc 2000 (C) C2/3.2", "vc2000-C", "C2/3.2", None),
        ("B8/3.1 Vc 2000", "vc2000-B", "B8/3.1", None),
        ("Vreemdelingencirculaire 2000, A3/7.1.", "vc2000-A", "A3/7.1", None),
        ("zoals neergelegd in de Vc 2000.", "vc2000", None, "Vc 2000"),
    ],
)
def test_vreemdelingencirculaire(text, identifier, pinpoint, written):
    (found,) = _ids(text)
    assert found[:4] == ("nl_policy_rule", "nl_vreemdelingencirculaire", identifier, pinpoint)
    if written:
        assert found[4] == written


def test_wbv_and_decrees():
    assert _ids("WBV 2014/1") == [("nl_policy_rule", "nl_wbv", "2014/1", None, "WBV 2014/1")]
    text = (
        "het besluit van de staatssecretaris van Financiën van 8 juli 2014, "
        "nr. DGB 2014/296M, bepaalt"
    )
    decrees = authority_text.scan_groups(nl_decrees=True)
    (hit,) = authority_patterns.scan(text, decrees)
    assert (hit.doc.identifier_scheme, hit.doc.identifier, hit.doc.date) == (
        "nl_besluit_kenmerk",
        "DGB2014/296M",
        "2014-07-08",
    )
    (numeric,) = authority_patterns.scan(
        "het besluit van 15 december 2016, nr. 2016-187170", decrees
    )
    assert numeric.doc.identifier == "2016-187170"


def test_decrees_off_by_default(monkeypatch):
    """Illustrative string: an individual administrative decision is no
    policy rule, and the decree pattern that takes it for one is off unless
    AUTHORITY_NL_DECREES is set."""
    text = "het besluit van 14 maart 2018, kenmerk 2018/12345, is herroepen"
    monkeypatch.delenv("AUTHORITY_NL_DECREES", raising=False)
    assert "nl_decree" not in authority_text.scan_groups()
    assert authority_patterns.scan(text) == []
    assert authority_patterns.scan(text, authority_text.scan_groups()) == []
    monkeypatch.setenv("AUTHORITY_NL_DECREES", "true")
    assert "nl_decree" in authority_text.scan_groups()


@pytest.mark.parametrize(
    "text",
    [
        "besluit van 15 december 2016, nr. 12",  # an ordinary number is no reference
        "het bestreden besluit van 3 maart 2020",  # no number at all
        "de Beleidsregels boeterecht",  # a bare name
    ],
)
def test_policy_rules_rejected(text):
    assert [i for i in _ids(text) if i[0] == "nl_policy_rule"] == []


# ---------------------------------------------------------------------------
# R4.4 foreign ECLIs
# ---------------------------------------------------------------------------


def test_foreign_eclis_real():
    # REAL: lines of cjeu/nj_nl.json (C-407/19, C-471/19 and C-703/22 notices)
    for line, ecli in [
        (
            "*P1* Grondwettelijk Hof, arrest van 25/11/2021 (ECLI:BE:GHCC:2021:ARR.168)",
            "ECLI:BE:GHCC:2021:ARR.168",
        ),
        (
            "*P1* Raad van State, XIIe kamer, arrest van 26/11/2024 "
            "(ECLI:BE:RVSCE:2024:ARR.261.479)",
            "ECLI:BE:RVSCE:2024:ARR.261.479",
        ),
    ]:
        (hit,) = authority_patterns.foreign_ecli_hits(line)
        assert (hit.doc.kind, hit.doc.identifier) == ("national_court_decision", ecli)
        assert hit.doc.issuer == ecli.split(":")[1] + ":" + ecli.split(":")[2]
        assert line[hit.start : hit.end] == ecli


def test_foreign_eclis_skip_the_collections_and_trailing_dots():
    # ILLUSTRATIVE
    text = (
        "ECLI:NL:HR:2020:593, ECLI:EU:C:2019:189, ECLI:CE:ECHR:2004:0622DEC001734103 "
        "and ECLI:DE:BGH:2018:141118BXII292.16.0."
    )
    assert [h.doc.identifier for h in authority_patterns.foreign_ecli_hits(text)] == [
        "ECLI:DE:BGH:2018:141118BXII292.16.0"
    ]


# ---------------------------------------------------------------------------
# R4.5 UN treaty bodies, Council of Europe bodies (ILLUSTRATIVE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, kind, scheme, identifier",
    [
        ("CCPR/C/GC/36,", "un_treaty_body", "un_symbol", "CCPR/C/GC/36"),
        ("views CCPR/C/108/D/2149/2012.", "un_treaty_body", "un_symbol", "CCPR/C/108/D/2149/2012"),
        ("E/C.12/GC/20", "un_treaty_body", "un_symbol", "E/C.12/GC/20"),
        (
            "Human Rights Committee, communication No. 2149/2012",
            "un_treaty_body",
            "un_communication",
            "CCPR/2149/2012",
        ),
        (
            "het VN-Kinderrechtencomité, communicatie nr. 12/2017",
            "un_treaty_body",
            "un_communication",
            "CRC/12/2017",
        ),
        ("CDL-AD(2016)007", "coe_body", "coe_cdl", "CDL-AD(2016)007"),
        ("CDL-AD(2016)7", "coe_body", "coe_cdl", "CDL-AD(2016)007"),
        ("CPT/Inf (2017) 1", "coe_body", "coe_cpt", "CPT/Inf(2017)1"),
        ("GrecoEval4Rep(2016)3", "coe_body", "coe_greco", "GrecoEval4Rep(2016)3"),
        ("CRI(2019)19", "coe_body", "coe_ecri", "CRI(2019)19"),
        ("ECRI General Policy Recommendation No. 15", "coe_body", "coe_ecri_gpr", "15"),
        ("Recommendation Rec(2006)2", "coe_body", "coe_cm", "Rec(2006)2"),
        ("CM/Rec(2010)5", "coe_body", "coe_cm", "CM/Rec(2010)5"),
        ("CM/ResDH(2019)1", "coe_body", "coe_cm", "CM/ResDH(2019)1"),
        ("CommDH(2019)1", "coe_body", "coe_commdh", "CommDH(2019)1"),
    ],
)
def test_un_and_coe(text, kind, scheme, identifier):
    (hit,) = authority_patterns.scan(text)
    assert (hit.doc.kind, hit.doc.identifier_scheme, hit.doc.identifier) == (
        kind,
        scheme,
        identifier,
    )


def test_un_symbol_url():
    (hit,) = authority_patterns.scan("CCPR/C/GC/36")
    assert hit.doc.url == "https://undocs.org/CCPR/C/GC/36"
    assert hit.doc.issuer == "Human Rights Committee"


@pytest.mark.parametrize(
    "text",
    [
        "Res(2004)3 without a cue",  # bare Rec/Res needs Recommendation/Resolution before it
        "application no. 2149/2012",  # an ECtHR application, not a communication
        "communication No. 2149/2012",  # no committee named
        "CAT/C",  # too short to be a document symbol
    ],
)
def test_un_and_coe_rejected(text):
    assert [i for i in _ids(text) if i[0] in ("un_treaty_body", "coe_body")] == []


# Illustrative strings (not from real case texts) for the review findings.
@pytest.mark.parametrize(
    "text",
    [
        "the cat was found on 3 May; communication No. 2149/2012",  # "cat" is no CAT
        "the hrc noted in communication No. 2149/2012",  # lower-case acronym
        "HRC, communication No. 2149/2012",  # bare HRC: the Council or the Committee
        "cedaw: communication No. 1/2012",
    ],
)
def test_committee_acronyms_need_capitals(text):
    assert [i for i in _ids(text) if i[1] == "un_communication"] == []


@pytest.mark.parametrize(
    "text, identifier",
    [
        ("CAT, communication No. 2149/2012", "CAT/2149/2012"),
        ("UN HRC, communication No. 2149/2012", "CCPR/2149/2012"),
        ("CCPR, communication No. 2149/2012", "CCPR/2149/2012"),
        ("CEDAW, communication No. 1/2012", "CEDAW/1/2012"),
    ],
)
def test_committee_acronyms_in_capitals(text, identifier):
    assert [i[2] for i in _ids(text) if i[1] == "un_communication"] == [identifier]


def test_kamerstuk_paper_number_with_a_letter_is_not_truncated():
    """Illustrative: "nr. 3a" is not paper 3."""
    ids = [i[2] for i in _ids("Kamerstukken II 2015/16, 34 356, nr. 3a")]
    assert "kst-34356-3" not in ids


def test_official_publication_needs_a_separator_after_the_year():
    """Illustrative: "Stb. 2017123" is no Staatsblad 2017, 123."""
    assert _ids("Stb. 2017123") == []
    assert [i[2] for i in _ids("Stcrt. 2019 12345")] == ["stcrt-2019-12345"]


def test_overlaps_keep_the_longest():
    text = "paragraaf C2/3.2 van de Vc 2000 (C) en Stcrt. 2019, 12345"
    assert [i[2] for i in _ids(text)] == ["vc2000-C", "stcrt-2019-12345"]


def test_records_for_text_offsets_and_context():
    text = "Uit de wetsgeschiedenis (Kamerstukken II 2015/16, 34 356, nr. 3, p. 12) volgt dat"
    key = CaseKey(ecli="ECLI:NL:RBDHA:2020:1")
    (record,) = authority_text.records_for_text(
        key, text, "fulltext", "nl", "RECHTSPRAAK", "rs_text_authority"
    )
    assert text[record.mention.char_start : record.mention.char_end] == record.raw_reference
    assert record.raw_reference == "Kamerstukken II 2015/16, 34 356, nr. 3, p. 12"
    assert record.pinpoint == "p. 12"
    assert record.match_method == "nl_kamerstuk"
    assert record.extractor_version == authority_text.EXTRACTOR_VERSION
    assert "wetsgeschiedenis" in record.mention.context


# ---------------------------------------------------------------------------
# R4.3 / R4.4 Cellar CELEX targets
# ---------------------------------------------------------------------------

# REAL: sector 8 CELEX numbers in cjeu/uuid_rows.json
REAL_SECTOR8 = [
    ("82018AT0228(51)", "AT", "2018-02-28"),
    ("82020AT1008(52)", "AT", "2020-10-08"),
    ("82018CZ0327(51)", "CZ", "2018-03-27"),
    ("82024CZ1119(51)", "CZ", "2024-11-19"),
    ("82020DE0512(51)", "DE", "2020-05-12"),
    ("82022DE0428(52)", "DE", "2022-04-28"),
    ("82016FI0912(51)", "FI", "2016-09-12"),
    ("82010SI0115(51)", "SI", "2010-01-15"),
    ("82016SI1219(51)", "SI", "2016-12-19"),
]


@pytest.mark.parametrize("celex, country, decided", REAL_SECTOR8)
def test_sector8_real(celex, country, decided):
    doc, reason = cellar_authority.classify_celex(celex)
    assert reason == "sector8"
    assert (doc.kind, doc.identifier_scheme, doc.identifier) == (
        "national_court_decision",
        "celex",
        celex,
    )
    assert (doc.issuer, doc.date) == (country, decided)
    assert doc.url == f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


@pytest.mark.parametrize(
    "celex, kind, title, reason",
    [
        # ILLUSTRATIVE: built to the CELEX structure; no sector 5/E/3 target
        # values are in the research files.
        ("52012PC0011", "eu_preparatory_act", "COM(2012) 11", "sector5"),
        ("52013JC0001", "eu_preparatory_act", "JOIN(2013) 1", "sector5"),
        ("52011SC1234", "eu_preparatory_act", None, "sector5"),
        ("32013D0123", "eu_decision", None, "sector3_decision"),
        ("E2012J0012", "efta_court", None, "sectorE"),
        ("E2012C0012", "efta_document", None, "sectorE"),
    ],
)
def test_other_sectors(celex, kind, title, reason):
    doc, got = cellar_authority.classify_celex(celex)
    assert got == reason
    assert (doc.kind, doc.identifier, doc.title) == (kind, celex, title)


@pytest.mark.parametrize(
    "celex, reason",
    [
        ("32013R0604", "sector3_not_authority"),  # regulation: legislation (Phase 3)
        ("12012E267", "sector1_not_authority"),
        ("82020NL0101(51)", "sector8_nl"),
        ("62012CJ0199", "sector6_not_authority"),
        ("not a celex", "celex_unparsed"),
    ],
)
def test_celex_left_out(celex, reason):
    assert cellar_authority.classify_celex(celex) == (None, reason)


def test_sector3_decisions_switch_off():
    assert cellar_authority.classify_celex("32013D0123", decisions=False) == (
        None,
        "sector3_decision_off",
    )


def test_celex_suffix_stripped_from_identifier():
    doc, _ = cellar_authority.classify_celex("52012PC0011_EXT")
    assert doc.identifier == "52012PC0011"


def test_citation_records_merge_directions():
    from collections import Counter

    stats = Counter()
    key = CaseKey(ecli="ECLI:EU:C:2013:720", celex="62012CJ0199")
    records = cellar_authority.citation_records(
        key,
        [
            ("52012PC0011", "cites"),
            ("52012PC0011", "cited_by"),
            ("82020DE0512(51)", "cited_by"),
            ("32013R0604", "cites"),
            ("62012CC0199", "joins"),
        ],
        stats,
    )
    assert [(r.raw_reference, r.match_method) for r in records] == [
        ("52012PC0011", "cellar_cited_by,cellar_cites"),
        ("82020DE0512(51)", "cellar_cited_by"),
    ]
    assert stats["celex_sector3_not_authority"] == 1
    assert all(r.mention.text_field == "metadata" for r in records)


# ---------------------------------------------------------------------------
# R4.6 Cellar literature lines (REAL, cjeu/nj_nl.json)
# ---------------------------------------------------------------------------

# The hand-checked sample (30 random lines, seed 20261124, of 2,282 distinct
# literature lines): 29 parsed to the right document, 1 skipped (no year).
REAL_LITERATURE = [
    (
        "- Uitspraken College van Beroep voor het Bedrijfsleven 1988 nº 90",
        "literature",
        "uitspraken college van beroep voor het bedrijfsleven|1988|no. 90",
    ),
    (
        "- Administratieve en rechterlijke beslissingen 1966 p.383-384 (*)",
        "literature",
        "administratieve en rechterlijke beslissingen|1966|p.383-384",
    ),
    (
        "- J.H.N.: Jurisprudentie milieurecht 1992 p.410-413",
        "annotation",
        "j.h.n.|jurisprudentie milieurecht|1992|p.410-413",
    ),
    (
        "- Sewandono, I.: Administratiefrechtelijke beslissingen ; Rechtspraak bestuursrecht "
        "2005 nº 363",
        "annotation",
        "sewandono, i.|administratiefrechtelijke beslissingen ; rechtspraak bestuursrecht|2005|"
        "no. 363",
    ),
    (
        "- Europäisches Wirtschafts- & Steuerrecht - 2008 p.400 (résumé) (Texte allemand)",
        "literature",
        "europäisches wirtschafts- & steuerrecht|2008|p.400",
    ),
    (
        "- Monster, Mies: Rechtspraak vrouwen en recht in 231 uitspraken en annotaties 1992 "
        "p.232-235",
        "annotation",
        "monster, mies|rechtspraak vrouwen en recht in 231 uitspraken en annotaties|1992|"
        "p.232-235",
    ),
    ("- AB-Kort 1993 nº 1140 (*)", "literature", "ab-kort|1993|no. 1140"),
    ("- Pasicrisie belge 1976 II p.90-93 (*)", "literature", "pasicrisie belge|1976|ii p.90-93"),
    (
        "- Rechtskundig weekblad 1980-81 Col.1737-1740",
        "literature",
        "rechtskundig weekblad|1980-81|col.1737-1740",
    ),
    (
        "- Nederlandse jurisprudentie ; Uitspraken in burgerlijke en strafzaken 2017 n°63",
        "literature",
        "nederlandse jurisprudentie ; uitspraken in burgerlijke en strafzaken|2017|no. 63",
    ),
    (
        "- Periodiek voor sociale verzekering, sociale voorzieningen en arbeidsrecht 1992 "
        "p.763-764",
        "literature",
        "periodiek voor sociale verzekering, sociale voorzieningen en arbeidsrecht|1992|"
        "p.763-764",
    ),
    (
        "- Fruytier, M.P.A.M.: Nederlandse jurisprudentie ; Uitspraken in burgerlijke en "
        "strafzaken 2014 nº 5421-5427",
        "annotation",
        "fruytier, m.p.a.m.|nederlandse jurisprudentie ; uitspraken in burgerlijke en "
        "strafzaken|2014|no. 5421-5427",
    ),
    (
        "- Raaijmakers, M.J.G.C.: Nietige en non-existente vennootschap, Ars aequi 1989 "
        "p.1005-1010",
        "literature",
        "raaijmakers, m.j.g.c.|ars aequi|1989|p.1005-1010",
    ),
    (
        "- N.W.: Journal du droit international 1989 p.1089-1090",
        "annotation",
        "n.w.|journal du droit international|1989|p.1089-1090",
    ),
    (
        "- S.E.W. : Tijdschrift voor Europees en economisch recht 1970 p.400-403",
        "literature",
        "s.e.w. : tijdschrift voor europees en economisch recht|1970|p.400-403",
    ),
    (
        "- Common Market Law Reports 1990 Vol.2 p.100-110 + p.111-120 (*)",
        "literature",
        "common market law reports|1990|vol.2 p.100-110 + p.111-120",
    ),
]


@pytest.mark.parametrize("line, kind, identifier", REAL_LITERATURE)
def test_literature_lines_real(line, kind, identifier):
    parts = cellar_authority.parse_literature(line)
    doc = cellar_authority.literature_doc(parts)
    assert (doc.kind, doc.identifier_scheme, doc.identifier) == (
        kind,
        "cellar_literature",
        identifier,
    )


@pytest.mark.parametrize(
    "line",
    [
        "- JURIFAST",  # REAL
        "- Rechtspraak sociale verzekering nº 149",  # REAL, no year
        "- Europees belastingrecht: regelgeving en jurisprudentie (Koninklijke Vermande - "
        "Lelystad) p.346 (résumé)",  # REAL, a loose-leaf edition without a year
        'Publication Flash News "Décisions de suivi" N° 1/22',  # REAL, not a '-' line
    ],
)
def test_literature_lines_skipped(line):
    assert cellar_authority.parse_literature(line) is None


def test_notice_records_real_notice():
    # REAL: the start of the notice of 61961CJ0013 in cjeu/nj_nl.json
    xml = (
        "<national_judgement>\n"
        "        <p>*A6* Arrondissementsrechtbank Rotterdam, vonnis van 26/10/1960 (465/60)</p>\n"
        "        <p>- Nederlandse jurisprudentie ; Uitspraken in burgerlijke en strafzaken "
        "1961 nº 159 (*)</p>\n"
        "        <p>*A8* Gerechtshof &#39;s-Gravenhage, arrest van 07/04/1961</p>\n"
        "        <p>- Nederlandse jurisprudentie ; Uitspraken in burgerlijke en strafzaken "
        "1961 nº 204 (*)</p>\n"
        "        <p>*P1* Gerechtshof &#39;s-Gravenhage, brief van 11/05/1966</p>\n"
        "      </national_judgement>"
    )
    from collections import Counter

    stats = Counter()
    key = CaseKey(ecli="ECLI:EU:C:1962:11", celex="61961CJ0013")
    records = cellar_authority.notice_records(key, xml, stats)
    assert [(r.pinpoint, r.authority.identifier) for r in records] == [
        ("A6", "nederlandse jurisprudentie ; uitspraken in burgerlijke en strafzaken|1961|no. 159"),
        ("A8", "nederlandse jurisprudentie ; uitspraken in burgerlijke en strafzaken|1961|no. 204"),
    ]
    for r in records:
        assert r.mention.text_field == "national_judgement_xml"
        assert xml[r.mention.char_start : r.mention.char_end] == r.raw_reference
        assert r.match_method == "national_judgement_literature"


def test_notice_foreign_ecli_line_real():
    # REAL: from the notice of C-703/22 (62022CJ0703) in cjeu/nj_nl.json
    xml = (
        "<national_judgement>\n"
        "        <p>*A9* Raad van State, VIIe kamer, arrest van 22/12/2022 "
        "(255.360 ; A. 225.504/VII-40.308)</p>\n"
        "        <p>*P1* Raad van State, XIIe kamer, arrest van 26/11/2024 "
        "(ECLI:BE:RVSCE:2024:ARR.261.479)</p>\n"
        "      </national_judgement>"
    )
    from collections import Counter

    (record,) = cellar_authority.notice_records(CaseKey(celex="62022CJ0703"), xml, Counter())
    assert record.authority.identifier == "ECLI:BE:RVSCE:2024:ARR.261.479"
    assert record.pinpoint == "P1"
    assert record.match_method == "national_judgement_ecli"
    assert xml[record.mention.char_start : record.mention.char_end] == record.raw_reference


# ---------------------------------------------------------------------------
# R4.6 Rechtspraak publications (ILLUSTRATIVE: no rows in the research files)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, kind, identifier",
    [
        ("NJ 2019/123", "literature", "NJ 2019/123"),
        ("RvdW 2019/123", "literature", "RVDW 2019/123"),
        ("Gst. 2014/12", "literature", "GST 2014/12"),
        ("AB 2020, 45", "literature", "AB 2020/45"),
        ("V-N 2017/12.5", "literature", "V-N 2017/12.5"),
        ("NJ 2019/123 m.nt. J. Spier", "annotation", "NJ 2019/123 m.nt. J. Spier"),
        (
            "NJ 2019/123 met annotatie van mr. T.F.E. Tjong Tjin Tai",
            "annotation",
            "NJ 2019/123 m.nt. T.F.E. Tjong Tjin Tai",
        ),
        ("JOR 2019/1, m.nt. prof. mr. B. Bier", "annotation", "JOR 2019/1 m.nt. B. Bier"),
        ("EHRC 2019/12 (annotatie: A. Bc)", "annotation", "EHRC 2019/12 m.nt. A. Bc"),
    ],
)
def test_rs_publication_raw(raw, kind, identifier):
    doc = rs_publication.publication_doc(rs_publication.parse_publication(raw))
    assert (doc.kind, doc.identifier_scheme, doc.identifier) == (
        kind,
        "nl_journal_locator",
        identifier,
    )


@pytest.mark.parametrize("raw", ["Rechtspraak.nl", "ECLI:NL:HR:2019:1", "Nieuwsbrief", ""])
def test_rs_publication_skipped(raw):
    assert rs_publication.parse_publication(raw) is None


def test_rs_publication_columns_win():
    parts = rs_publication.parse_publication("NJ 2019, 123 (Spier)", "NJ", 2019, "123", "Spier")
    assert parts["method"] == "publication_columns"
    assert rs_publication.publication_doc(parts).identifier == "NJ 2019/123 m.nt. Spier"


def test_rs_publication_vindplaatsen_dedupe():
    from collections import Counter

    stats = Counter()
    records = rs_publication.records_for_case(
        CaseKey(ecli="ECLI:NL:HR:2019:1"),
        [("NJ 2019/123 m.nt. J. Spier", None, None, None, None)],
        ["NJ 2019/123 m.nt. J. Spier", "RvdW 2019/5", "Rechtspraak.nl"],
        stats,
    )
    assert [(r.raw_reference, r.match_method) for r in records] == [
        ("NJ 2019/123 m.nt. J. Spier", "publication_raw"),
        ("RvdW 2019/5", "vindplaatsen"),
    ]
    assert stats["vindplaatsen_skipped"] == 1


# ---------------------------------------------------------------------------
# artifact
# ---------------------------------------------------------------------------


def _record(**overrides):
    values = dict(
        source=CaseKey(ecli="ECLI:NL:HR:2019:1"),
        authority=AuthorityDoc("literature", "nl_journal_locator", "NJ 2019/123"),
        raw_reference="NJ 2019/123",
        source_dataset="rs_publication",
        extractor_version="rs_publication/1.0.0",
        mention=AuthorityMention(text_field="metadata"),
    )
    values.update(overrides)
    return AuthorityRecord(**values)


def test_artifact_round_trip_and_stable_order(tmp_path):
    a = _record()
    b = _record(raw_reference="RvdW 2019/5", authority=AuthorityDoc("literature", "x", "RVDW"))
    path = tmp_path / "a.jsonl"
    assert write_jsonl([b, a], path) == 2
    first = path.read_bytes()
    write_jsonl([a, b], path)
    assert path.read_bytes() == first
    assert sorted(r.raw_reference for r in read_jsonl(path)) == ["NJ 2019/123", "RvdW 2019/5"]


@pytest.mark.parametrize(
    "change",
    [
        {"source_dataset": "rs_text_ecli"},
        {"raw_reference": "  "},
        {"confidence": 1.5},
        {"authority": AuthorityDoc("not_a_kind", "x", "y")},
        {"authority": AuthorityDoc("literature", "x", " y")},
        {"authority": AuthorityDoc("literature", "x", "y", date="2019-13-01")},
        {"mention": AuthorityMention(text_field="body")},
        {"mention": AuthorityMention(text_field="fulltext", char_start=5, char_end=1)},
    ],
)
def test_artifact_rejects(change):
    with pytest.raises(ArtifactError):
        _record(**change).validate()


def test_artifact_rejects_unknown_fields(tmp_path):
    line = _record().to_dict()
    line["surprise"] = 1
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(line) + "\n")
    with pytest.raises(ArtifactError, match="bad.jsonl:1"):
        list(read_jsonl(path))
