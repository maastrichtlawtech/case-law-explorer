"""
Cellar referral data (R2.3): parsing national_judgement_xml, court rules,
matching to Rechtspraak decisions and the extract entry point.

The notices in fixtures/cellar_national_judgement.json are copied byte for
byte from the research files (cjeu-migration research-2026-11-24
cjeu/nj_nl.json). Rechtspraak metadata in the candidates comes from the
evaluation set's notes (R0.3) and the research matches (cjeu/matches.json).
"""

import json
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from data_extraction.linking import cellar_referrals as cr
from data_extraction.linking.artifact import read_jsonl
from tests.linking_db import add_case, add_identifier, execute, needs_db, scratch_db  # noqa: F401

FIXTURE = Path(__file__).parent / "fixtures" / "cellar_national_judgement.json"
NOTICES = {n["celex"]: n for n in json.loads(FIXTURE.read_text())["notices"]}


def notice(celex):
    return NOTICES[celex]["xml"]


def rs(ecli, decided, instance="Raad van State", zaaknummer=None, **kw):
    return cr.RsCandidate(
        ecli=ecli, decided=decided, instance=instance, zaaknummer=zaaknummer, **kw
    )


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


def test_parse_tjebbes_notice():
    xml = notice("62017CJ0221")
    lines = cr.parse_notice(xml)
    assert [line.code for line in lines] == ["A9", "P1"]
    a9, p1 = lines
    assert a9.decided == date(2017, 4, 19)
    assert a9.court == "Raad van State"
    assert a9.tokens == ("201504577/1/A3", "201507057/1/A3", "201508588/1/A3", "201601993/1/A3")
    assert a9.relation_type == "preliminary_reference"
    assert p1.relation_type == "national_follow_up"
    assert p1.tokens[-1] == "201608752/1/A3"
    # offsets point at the line in the stored XML
    start, end = a9.char_start, a9.char_end
    assert xml[start:end] == a9.raw_text


def test_parse_joined_cases_keeps_the_affaire_heading():
    lines = cr.parse_notice(notice("62012CJ0199"))
    a9s = [line for line in lines if line.code == "A9"]
    assert [line.affaire for line in a9s] == ["C-199/12", "C-200/12", "C-201/12"]
    assert [line.tokens for line in a9s] == [
        ("201012342/T1/V2",),
        ("201106615/T1/V2",),
        ("201109928/T1/V2",),
    ]
    # "uitpsraak" (sic) does not disturb the date
    assert {line.decided for line in a9s} == {date(2012, 4, 18)}


def test_parse_takes_the_ecli_from_the_line_and_from_the_link_after_it():
    lines = {line.code: line for line in cr.parse_notice(notice("62013CJ0205"))}
    assert lines["P2"].eclis == ("ECLI:NL:GHAMS:2019:262",)
    assert lines["P2"].tokens == ()
    # HTML entities are decoded in raw_text, offsets still cover the stored span
    assert "&amp;" not in lines["P2"].raw_text
    assert lines["A9"].tokens == ("11/04114",)


def test_parse_ljn_and_numbers():
    lines = {line.code: line for line in cr.parse_notice(notice("62009CJ0242"))}
    assert lines["P1"].ljns == ("BU1290",)
    assert lines["P1"].tokens == ("106.004.857/01",)
    assert lines["A9"].tokens == ("106.004.857/01", "755/06")


def test_interim_lines_have_no_relation():
    line = cr.parse_notice("<x><p>*I1* Hoge Raad der Nederlanden, arrest van 18/05/1962</p></x>")[0]
    assert line.relation_type is None


@pytest.mark.parametrize(
    "code, relation",
    [
        ("A9", "preliminary_reference"),
        ("A8", "earlier_instance"),
        ("A7", "earlier_instance"),
        ("P1", "national_follow_up"),
        ("P3", "national_follow_up"),
    ],
)
def test_line_codes(code, relation):
    xml = f"<x><p>*{code}* Raad van State, uitspraak van 01/02/2010 (200901234/1/H1)</p></x>"
    assert cr.parse_notice(xml)[0].relation_type == relation


# ---------------------------------------------------------------------------
# courts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "court, kind, seat",
    [
        ("Raad van State, afdeling bestuursrechtspraak, uitpsraak van", cr.RVS, None),
        ("Raad van State, voorzitter afdeling geschillen van bestuur, uitspraak van", cr.RVS, None),
        ("Hoge Raad der Nederlanden, 3e kamer, arrest van", cr.HR, None),
        ("Centrale Raad van Beroep, meervoudige kamer, uitspraak van", cr.CRVB, None),
        ("College van Beroep voor het bedrijfsleven, uitsrpaak van", cr.CBB, None),
        ("Tariefcommissie, uitspraak van", cr.TC, None),
        ("Arrondissementsrechtbank Rotterdam, vonnis van", cr.RB, "rotterdam"),
        ("Gerechtshof te 's-Gravenhage, arrest van", cr.GH, "den haag"),
        ("Rechtbank Den Haag, zittingsplaats Roermond, Beslissing van", cr.RB, "den haag"),
        ("Gerechtshof Arnhem-Leeuwarden, arrest van", cr.GH, "arnhem-leeuwarden"),
        ("Rechtbank Gelderland, Eerste aanleg - meervoudig, Beslissing van", cr.RB, "gelderland"),
        ("Benelux Gerechtshof, arrest van", cr.BNL, None),  # in the corpus as ECLI:NL:XX
    ],
)
def test_dutch_courts(court, kind, seat):
    assert cr.classify_court(court) == cr.Court(kind, seat)


@pytest.mark.parametrize(
    "court",
    [
        # all from the research notices; the first three passed parse_match.py
        "Rechtbank van eerste aanleg te Oudenaarde, vonnis van",
        "Rechtbank van 1e aanleg Turnhout, vonnis van",
        "Rechtbank van Koophandel te Dendermonde, kort geding, beschikking van",
        "Hof van Cassatie, 2e kamer, arrest van",
        "Arbeidsrechtbank Hasselt, 1e kamer, vonnis van",
        "Hof van beroep Brussel, 1e kamer, arrest van",
        "Nederlandstalige rechtbank van eerste aanleg Brussel, vonnis van",
        "Landesverwaltungsgericht Niederösterreich, Beschluss vom",
        "Raad van Beroep Amsterdam, uitspraak van",  # no Rechtspraak instance for it
        "Kantongerecht te Nijmegen, vonnis van",  # seat not in the list: skipped
    ],
)
def test_foreign_or_unknown_courts_are_refused(court):
    assert cr.classify_court(court) is None


def test_foreign_check_reads_the_court_name_not_the_whole_line():
    # parse_match.py rejected this line because "eerste aanleg" appears later on
    assert cr.classify_court("Rechtbank Gelderland, Eerste aanleg - meervoudig") is not None
    # and a Dutch place after a Belgian court does not let it through
    assert cr.classify_court("Rechtbank van eerste aanleg Antwerpen, zitting Maastricht") is None


def test_procureur_generaal_selects_the_parket():
    assert cr.classify_court("Hoge Raad der Nederlanden, conclusie A-G").kind == cr.PHR
    assert cr.classify_court("Parket bij de Hoge Raad, conclusie van").kind == cr.PHR


def test_court_matches_instance():
    assert cr.court_matches(cr.Court(cr.RB, "den haag"), "Rechtbank 's-Gravenhage")
    assert cr.court_matches(cr.Court(cr.RB, "rotterdam"), "Rechtbank Rotterdam")
    assert not cr.court_matches(cr.Court(cr.RB, "rotterdam"), "Rechtbank Amsterdam")
    assert not cr.court_matches(cr.Court(cr.GH, "arnhem"), "Gerechtshof Arnhem-Leeuwarden")
    assert cr.court_matches(cr.Court(cr.HR), "Hoge Raad")
    assert not cr.court_matches(cr.Court(cr.HR), "Parket bij de Hoge Raad")


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

D12 = date(2012, 4, 18)
D13 = date(2013, 12, 18)
# Rechtspraak metadata of the gold set (linking evaluation set notes)
GOLD_RS = [
    rs("ECLI:NL:RVS:2012:BW3078", D12, zaaknummer="201012342/1/T1/V2"),
    rs("ECLI:NL:RVS:2012:BW3077", D12, zaaknummer="201106615/1/T1/V2"),
    rs("ECLI:NL:RVS:2012:BW3076", D12, zaaknummer="201109928/T1/V2"),
    rs("ECLI:NL:RVS:2013:2423", D13, zaaknummer="201012342/1/V2"),
    rs("ECLI:NL:RVS:2013:2424", D13, zaaknummer="201106615/1/V2"),
    rs("ECLI:NL:RVS:2013:2422", D13, zaaknummer="201109928/1/V2"),
    rs(
        "ECLI:NL:RVS:2017:1098",
        date(2017, 4, 19),
        zaaknummer="201504577/1/A3, 201507057/1/A3, 201508588/1/A3, 201601993/1/A3",
    ),
    rs(
        "ECLI:NL:RVS:2020:423",
        date(2020, 2, 12),
        zaaknummer="201504577/2/A3, 201507057/2/A3, 201508588/2/A3, 201601993/2/A3, "
        "201604943/1/A3, 201608752/1/A3",
    ),
    # unrelated decisions of the same days
    rs("ECLI:NL:RVS:2012:BW3000", D12, zaaknummer="201100001/1/H1"),
    rs("ECLI:NL:RBAMS:2012:BW3001", D12, instance="Rechtbank Amsterdam", zaaknummer="201012342"),
]


def _links(celex, candidates, **kw):
    doc = cr.CjeuDocument(NOTICES[celex]["ecli"], celex, None, notice(celex))
    stats = Counter()
    return cr.links_for_document(doc, candidates, stats, **kw), stats


def test_gold_referrals_and_follow_ups():
    links, stats = _links("62012CJ0199", GOLD_RS)
    got = {(r.source.ecli, r.relation_type, r.match_method, r.confidence) for r in links}
    assert got == {
        ("ECLI:NL:RVS:2012:BW3078", "preliminary_reference", "metadata/zaaknummer", 0.95),
        ("ECLI:NL:RVS:2012:BW3077", "preliminary_reference", "metadata/zaaknummer", 0.95),
        ("ECLI:NL:RVS:2012:BW3076", "preliminary_reference", "metadata/zaaknummer", 0.95),
        # Cellar writes the referral's number; the decision is filed under .../1/V2
        ("ECLI:NL:RVS:2013:2423", "national_follow_up", "metadata/zaaknummer_base", 0.9),
        ("ECLI:NL:RVS:2013:2424", "national_follow_up", "metadata/zaaknummer_base", 0.9),
        ("ECLI:NL:RVS:2013:2422", "national_follow_up", "metadata/zaaknummer_base", 0.9),
    }
    assert all(r.target.ecli == "ECLI:EU:C:2013:720" for r in links)
    assert all(r.source_dataset == "cellar_national_judgement" for r in links)
    mention = next(r for r in links if r.source.ecli.endswith("BW3078")).mentions[0]
    assert mention.text_field == "national_judgement_xml"
    assert mention.section == "A9" and mention.context == "AFFAIRE C-199/12"
    assert mention.raw_text.startswith("*A9* Raad van State")


def test_tjebbes_referral_and_follow_up():
    links, _ = _links("62017CJ0221", GOLD_RS)
    assert {(r.source.ecli, r.relation_type) for r in links} == {
        ("ECLI:NL:RVS:2017:1098", "preliminary_reference"),
        ("ECLI:NL:RVS:2020:423", "national_follow_up"),
    }


def test_belgian_notice_gives_nothing_even_with_matching_numbers():
    # an RS decision that happens to share date and number with the Belgian line
    trap = rs(
        "ECLI:NL:RBAMS:1976:X1",
        date(1976, 6, 25),
        instance="Rechtbank Amsterdam",
        zaaknummer="105/76 1773",
    )
    links, stats = _links("61976CJ0065", [trap])
    assert links == []
    assert stats["foreign_or_unknown_court"] == 2


def test_hoge_raad_never_matches_the_parket():
    line = cr.parse_notice(
        "<x><p>*A9* Hoge Raad der Nederlanden, 3e kamer, arrest van 22/09/2006 (40.230)</p></x>"
    )[0]
    hr = rs("ECLI:NL:HR:2006:AY8800", date(2006, 9, 22), "Hoge Raad", "40.230")
    phr = rs("ECLI:NL:PHR:2006:AY8800", date(2006, 9, 22), "Parket bij de Hoge Raad", "40.230")
    match, _ = cr.match_line(line, [phr, hr])
    assert match.ecli == "ECLI:NL:HR:2006:AY8800"
    assert cr.match_line(line, [phr]) == (None, "no_decision_that_day")


def test_duplicate_publications_resolve_to_one_canonical_case():
    """RVS:2012:BW3076 = RVS:2012:4057 = 4059 (English): decision D2."""
    line = [ln for ln in cr.parse_notice(notice("62012CJ0199")) if ln.affaire == "C-201/12"][0]
    dupes = [
        rs("ECLI:NL:RVS:2012:4059", D12, zaaknummer="201109928/T1/V2", language="en"),
        rs("ECLI:NL:RVS:2012:4057", D12, zaaknummer="201109928/T1/V2", published=date(2013, 3, 1)),
        rs(
            "ECLI:NL:RVS:2012:BW3076",
            D12,
            zaaknummer="201109928/T1/V2",
            published=date(2012, 4, 18),
        ),
    ]
    match, reason = cr.match_line(line, dupes)
    assert (match.ecli, match.confidence, reason) == ("ECLI:NL:RVS:2012:BW3076", 0.92, "ok")
    # without the LJN-style one, the Dutch numeric publication wins over the translation
    match, _ = cr.match_line(line, dupes[:2])
    assert match.ecli == "ECLI:NL:RVS:2012:4057"


def test_publications_with_and_without_the_instance_segment_are_one_decision():
    """Illustrative (review round 3): the same decision filed once as
    201012342/1/T1/V2 and once as 201012342/T1/V2."""
    line = [ln for ln in cr.parse_notice(notice("62012CJ0199")) if ln.affaire == "C-199/12"][0]
    dupes = [
        rs("ECLI:NL:RVS:2012:BW3078", D12, zaaknummer="201012342/1/T1/V2"),
        rs("ECLI:NL:RVS:2012:9999", D12, zaaknummer="201012342/T1/V2"),
    ]
    match, reason = cr.match_line(line, dupes)
    assert (match.ecli, reason) == ("ECLI:NL:RVS:2012:BW3078", "ok")
    chosen, publications = cr.canonical(dupes)
    assert (chosen.ecli, publications) == ("ECLI:NL:RVS:2012:BW3078", 2)


def test_date_court_fallback_flag_is_read_when_extract_runs(monkeypatch):
    """REFERRAL_DATE_COURT_FALLBACK set after import still applies."""
    xml = "<x><p>*A9* Raad van State, uitspraak van 01/02/2010</p></x>"
    doc = cr.CjeuDocument("ECLI:EU:C:2011:1", "62010CJ0001", None, xml)
    candidate = rs("ECLI:NL:RVS:2010:BL0001", date(2010, 2, 1))
    monkeypatch.setattr(cr, "iter_documents", lambda *a, **k: iter([[doc]]))
    monkeypatch.setattr(
        cr, "fetch_candidates", lambda cursor, dates: {date(2010, 2, 1): [candidate]}
    )

    class Conn:
        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def rollback(self):
            pass

    monkeypatch.delenv("REFERRAL_DATE_COURT_FALLBACK", raising=False)
    assert cr.extract(Conn())[0] == 0
    monkeypatch.setenv("REFERRAL_DATE_COURT_FALLBACK", "true")
    assert cr.extract(Conn())[0] == 1
    assert cr.extract(Conn(), date_court_fallback=False)[0] == 0


def test_different_decisions_are_ambiguous_not_guessed():
    line = cr.parse_notice(
        "<x><p>*A9* Hoge Raad der Nederlanden, arrest van 05/04/2013 (12/00667)</p></x>"
    )[0]
    a = rs("ECLI:NL:HR:2013:BZ1", date(2013, 4, 5), "Hoge Raad", "12/00667")
    b = rs("ECLI:NL:HR:2013:BZ2", date(2013, 4, 5), "Hoge Raad", "12/00667, 12/00668")
    assert cr.match_line(line, [a, b]) == (None, "ambiguous")


def test_ecli_in_the_line_wins_and_court_mismatch_lowers_confidence():
    lines = {ln.code: ln for ln in cr.parse_notice(notice("62013CJ0387"))}
    # "Hoge Raad der Nederlanden ... (ECLI:NL:CBB:2016:111)": the ECLI names the CBB
    match, _ = cr.match_line(lines["P1"], [])
    assert (match.ecli, match.method, match.confidence) == ("ECLI:NL:CBB:2016:111", "ecli", 0.85)
    gh = {ln.code: ln for ln in cr.parse_notice(notice("62013CJ0205"))}["P2"]
    match, _ = cr.match_line(gh, [])
    assert (match.ecli, match.confidence) == ("ECLI:NL:GHAMS:2019:262", 0.99)


def test_ljn_match():
    p1 = {ln.code: ln for ln in cr.parse_notice(notice("62006CJ0402"))}["P1"]
    hit = rs("ECLI:NL:HR:2008:BD0427", date(2008, 4, 25), "Hoge Raad", "40.230")
    other = rs("ECLI:NL:HR:2008:BD0001", date(2008, 4, 25), "Hoge Raad", "40.111")
    match, _ = cr.match_line(p1, [other, hit])
    assert (match.ecli, match.method) == ("ECLI:NL:HR:2008:BD0427", "ljn")


def test_numeric_core_match():
    """Rechtspraak adds letters to Cellar's number: research matches.json."""
    line = cr.parse_notice(
        "<x><p>*P1* Hoge Raad der Nederlanden, 3e kamer, arrest van 12/07/2013 (07/12617)</p></x>"
    )[0]
    hit = rs("ECLI:NL:HR:2013:17", date(2013, 7, 12), "Hoge Raad", "07/12617bis")
    other = rs("ECLI:NL:HR:2013:18", date(2013, 7, 12), "Hoge Raad", "12/01617")
    match, _ = cr.match_line(line, [other, hit])
    assert (match.ecli, match.rule, match.confidence) == (
        "ECLI:NL:HR:2013:17",
        "zaaknummer_core",
        0.9,
    )
    assert cr.number_cores("C/09/450182 / HA ZA 13-999") == {"09/450182", "13-999"}
    assert cr.number_cores("AWB 00/392A") == {"00/392"}
    assert cr.number_cores("12") == set()


def test_case_identifier_values_are_used_too():
    line = cr.parse_notice(
        "<x><p>*A9* Centrale Raad van Beroep, uitspraak van 04/06/2013 (10/719 WW)</p></x>"
    )[0]
    hit = rs(
        "ECLI:NL:CRVB:2013:CA1",
        date(2013, 6, 4),
        "Centrale Raad van Beroep",
        zaaknummer=None,
        identifiers=("10/719WW",),
    )
    assert cr.match_line(line, [hit])[0].ecli == "ECLI:NL:CRVB:2013:CA1"


def test_date_court_fallback_is_off_by_default(monkeypatch):
    line = cr.parse_notice(
        "<x><p>*A9* Tariefcommissie, uitspraak van 18/09/1962 (8297 T - 8463 T)</p></x>"
    )[0]
    only = rs("ECLI:NL:TC:1962:1", date(1962, 9, 18), "Tariefcommissie", "1234")
    monkeypatch.delenv("REFERRAL_DATE_COURT_FALLBACK", raising=False)
    assert cr.date_court_fallback_enabled() is False
    assert cr.match_line(line, [only]) == (None, "no_zaaknummer_match")
    match, _ = cr.match_line(line, [only], date_court_fallback=True)
    assert (match.ecli, match.confidence) == ("ECLI:NL:TC:1962:1", 0.6)
    two = [only, rs("ECLI:NL:TC:1962:2", date(1962, 9, 18), "Tariefcommissie", "99")]
    assert cr.match_line(line, two, date_court_fallback=True) == (None, "ambiguous_date_court")


def test_dates_must_agree_with_the_ruling():
    doc = cr.CjeuDocument(
        "ECLI:EU:C:2019:189",
        "62017CJ0221",
        date(2016, 1, 1),  # pretend the ruling predates the referral
        notice("62017CJ0221"),
    )
    stats = Counter()
    links = cr.links_for_document(doc, GOLD_RS, stats)
    # the 2017 referral cannot precede a 2016 ruling; the 2020 follow-up still can follow it
    assert [r.relation_type for r in links] == ["national_follow_up"]
    assert stats["date_inconsistent"] == 1


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------


@needs_db
def test_extract_and_load(scratch_db, tmp_path):  # noqa: F811
    from data_loading.link_loader import load_artifact

    conn = scratch_db
    doc_id = add_case(conn, "ECLI:EU:C:2013:720", "62012CJ0199", date(2013, 11, 7))
    execute(
        conn,
        """INSERT INTO cle_v2.cjeu_document (case_id, celex_id, ecli, national_judgement_xml)
           VALUES (%s, '62012CJ0199', 'ECLI:EU:C:2013:720', %s)""",
        (doc_id, notice("62012CJ0199")),
    )
    for c in GOLD_RS:
        case_id = add_case(conn, c.ecli, None, c.decided, sources=("RS",))
        execute(
            conn,
            """INSERT INTO cle_v2.rs_document (case_id, date_decision, instance, zaaknummer)
               VALUES (%s, %s, %s, %s)""",
            (case_id, c.decided, c.instance, c.zaaknummer),
        )
    # the identifier task's form of one number (exact match through case_identifier)
    bw3078 = execute(conn, "SELECT id FROM cle_v2.cases WHERE ecli = 'ECLI:NL:RVS:2012:BW3078'")
    add_identifier(conn, bw3078[0][0], "nl_zaaknummer", "201012342/1/T1/V2", "201012342/T1/V2")

    out = tmp_path / "cellar_national_judgement.jsonl"
    written, stats = cr.extract(conn, out_path=out, batch_size=1)
    assert written == 6 and stats["documents"] == 1
    assert {r.source.ecli for r in read_jsonl(out)} == {
        "ECLI:NL:RVS:2012:BW3078",
        "ECLI:NL:RVS:2012:BW3077",
        "ECLI:NL:RVS:2012:BW3076",
        "ECLI:NL:RVS:2013:2423",
        "ECLI:NL:RVS:2013:2424",
        "ECLI:NL:RVS:2013:2422",
    }
    # id_range outside the document: nothing
    assert cr.extract(conn, id_range=(doc_id + 1, doc_id + 5), out_path=None)[0] == 0

    counts = load_artifact(conn, out)
    assert counts["cellar_national_judgement"]["inserted"] == 6
    rows = execute(
        conn,
        """SELECT DISTINCT relation_type, is_cross_jurisdiction, match_method
             FROM cle_v2.case_citation ORDER BY 1""",
    )
    # R2.7: RS decision -> CJEU ruling is cross-jurisdiction
    assert rows == [
        ("national_follow_up", True, "metadata/zaaknummer_base"),
        ("preliminary_reference", True, "metadata/zaaknummer"),
    ]
    assert execute(conn, "SELECT count(*) FROM cle_v2.case_citation_mention")[0][0] == 6
