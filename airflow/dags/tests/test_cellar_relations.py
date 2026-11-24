"""
Resolving Cellar's procedural relations (R2.5). URIs, dossier identifiers and
CELEX numbers are real (research cjeu/uuid_rows.json, uuid_dossier.json,
uuid_map.json, cn_map.json). Nothing here calls Cellar: the SPARQL fetch is
exercised with a fake urlopen.
"""

import io
import json
from collections import Counter
from datetime import date

import pytest

from data_extraction.linking import cellar_relations as rel
from data_extraction.linking import identifiers, resolver
from data_extraction.linking.artifact import read_jsonl
from tests.linking_db import add_case, add_identifier, execute, needs_db, scratch_db  # noqa: F401

CELLAR = "http://publications.europa.eu/resource/cellar/"
# uuid_rows.json id 322871: 61999TJ0120 subject_to_appeal -> this URI;
# uuid_dossier.json: -> "C-361/01 P"
U_KIK = CELLAR + "8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1"
# uuid_map.json: -> 62020CJ0646 (a work, not a dossier)
U_WORK = CELLAR + "05a39798-64c7-11ed-92ed-01aa75ed71a1"


def doc(case_id, celex, decided=None, ecli=None):
    return rel.Document(case_id, ecli, celex, None, decided)


def cand(case_id, celex, decided, value):
    return resolver.Candidate(case_id, None, celex, None, decided, resolver.cjeu_kind(celex), value)


def lookups(dossier=None, celex_map=None, by_celex=None, by_number=None, by_ecli=None):
    return rel.Lookups(
        uuid_dossier={identifiers.normalize_cellar_uuid(k): v for k, v in (dossier or {}).items()},
        uuid_celex={identifiers.normalize_cellar_uuid(k): v for k, v in (celex_map or {}).items()},
        by_celex=by_celex or {},
        by_ecli=by_ecli or {},
        by_case_number=by_number or {},
    )


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (U_KIK, ("uuid", "8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1", "")),
        (
            U_KIK.upper().replace("HTTP://PUBLICATIONS.EUROPA.EU/RESOURCE/CELLAR/", CELLAR)
            + ".0001",
            ("uuid", "8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1", ""),
        ),
        (
            "http%3A%2F%2Fpublications.europa.eu%2Fresource%2Fcellar%2F"
            "8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1",
            ("uuid", "8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1", ""),
        ),
        ("http://publications.europa.eu/resource/celex/62001CJ0361", ("celex", "62001CJ0361", "")),
        ("62019CO0001(01)", ("celex", "62019CO0001", "")),
        ("61998CJ0448_INF", ("celex", "61998CJ0448", "")),
        (
            "http://publications.europa.eu/resource/ecli/ECLI%3AEU%3AC%3A2013%3A720",
            ("ecli", "ECLI:EU:C:2013:720", ""),
        ),
        ("C-361/01 P", ("case_number", "C-361/01", "P")),
        ("case:T-167/09 P", ("case_number", "T-167/09", "P")),
        (
            "http://publications.europa.eu/resource/case/C-278%2F13%20P(R)",
            ("case_number", "C-278/13", "P(R)"),
        ),
        ("T-401/11 P-RENV-RX", ("case_number", "T-401/11", "P-RENV-RX")),
        ("C‑89/24 PPU", ("case_number", "C-89/24", "PPU")),
        ("something else", ("unknown", None, "")),
    ],
)
def test_parse_reference(raw, expected):
    ref = rel.parse_reference(raw)
    assert (ref.kind, ref.value, ref.suffix) == expected


def test_normalize_cellar_uuid():
    assert identifiers.normalize("cellar_dossier_uuid", U_KIK + ".0002.03") == (
        "8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1"
    )
    assert identifiers.normalize_cellar_uuid("not a uuid") is None


def test_load_uuid_map(tmp_path):
    path = tmp_path / "uuid_dossier.json"
    path.write_text(json.dumps({U_KIK: ["C-361/01 P"], "bad": ["x"]}))
    assert rel.load_uuid_map(path) == {"8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1": ["C-361/01 P"]}
    assert rel.load_uuid_map(None) == {}


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------

KIK_GC = doc(10, "61999TJ0120", date(2001, 7, 12), "ECLI:EU:T:2001:184")
KIK_ROW = rel.CellarRow(322871, "subject_to_appeal", U_KIK, KIK_GC)
KIK_APPEAL = cand(20, "62001CJ0361", date(2003, 9, 9), "C-361/01 P")


def test_appeal_is_reversed():
    lk = lookups(dossier={U_KIK: ["C-361/01 P"]}, by_number={"C-361/01": [KIK_APPEAL]})
    records, idents = rel.links_for_rows([KIK_ROW], lk)
    assert len(records) == 1
    r = records[0]
    assert (r.source.celex, r.target.ecli, r.relation_type) == (
        "62001CJ0361",
        "ECLI:EU:T:2001:184",
        "appeal_of",
    )
    assert (r.source_dataset, r.match_method, r.confidence) == (
        "cellar_relation_resolved",
        "case_number/uuid_dossier_cjeu_judgment",
        0.95,
    )
    assert r.mentions[0].raw_text == U_KIK and r.mentions[0].text_field == "metadata"
    assert idents == [
        {
            "case": {"celex": "62001CJ0361"},
            "scheme": "cellar_dossier_uuid",
            "value": U_KIK,
            "value_normalized": "8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1",
            "source": "cellar_sparql.dossier_identifier",
        }
    ]


def test_appeal_rules():
    stats = Counter()
    # interim order in the appeal: only a candidate stored with "P(R)" may be taken
    row = rel.CellarRow(1, "subject_to_appeal", "C-278/13 P(R)", doc(10, "62012TO0462"))
    lk = lookups(by_number={"C-278/13": [cand(20, "62013CJ0278", None, "C-278/13 P")]})
    assert rel.links_for_rows([row], lk, stats)[0] == []
    assert stats["subject_to_appeal:no_candidate_with_suffix"] == 1
    lk = lookups(by_number={"C-278/13": [cand(21, "62013CO0278", None, "C-278/13 P(R)")]})
    assert rel.links_for_rows([row], lk)[0][0].source.celex == "62013CO0278"
    # an appeal without "P" is not an appeal
    row = rel.CellarRow(2, "subject_to_appeal", "case:C-176/19", doc(10, "62014TJ0691"))
    assert rel.resolve_row(row, lookups()) == (None, "appeal_without_p_suffix")
    # appeals from the Civil Service Tribunal go to the General Court, not the Court of Justice
    row = rel.CellarRow(3, "subject_to_appeal", "C-167/09 P", doc(10, "62008FJ0038"))
    assert rel.resolve_row(row, lookups()) == (None, "appeal_court_mismatch")
    # the appeal decision must not predate the decision under appeal
    early = cand(20, "62001CJ0361", date(2000, 1, 1), "C-361/01 P")
    lk = lookups(dossier={U_KIK: ["C-361/01 P"]}, by_number={"C-361/01": [early]})
    assert rel.resolve_row(KIK_ROW, lk) == (None, "no_candidate_after_source")
    # an appeal not in the database cannot be the source of a row
    lk = lookups(dossier={U_KIK: ["C-361/01 P"]})
    assert rel.resolve_row(KIK_ROW, lk) == (None, "no_case_with_case_number")
    assert rel.resolve_row(KIK_ROW, lookups()) == (None, "uuid_unmapped")


def test_judgment_preferred_over_order_and_other_suffixes_left_out():
    candidates = [
        cand(21, "62001CO0361", date(2002, 1, 1), "C-361/01 P(R)"),
        cand(22, "62001CO0361(01)", date(2004, 1, 1), "C-361/01 P"),
        KIK_APPEAL,
    ]
    lk = lookups(dossier={U_KIK: ["C-361/01 P"]}, by_number={"C-361/01": candidates})
    resolved, _ = rel.resolve_row(KIK_ROW, lk)
    assert resolved.target.case_id == 20


def test_preliminary_reference_via_work_celex():
    # uuid_rows.json: 82018AT0228(51) referred_for_preliminary_ruling -> a work URI;
    # here the work maps to a CELEX (uuid_map.json format)
    national = doc(30, "82018AT0228(51)", date(2018, 2, 28))
    row = rel.CellarRow(962969, "referred_for_preliminary_ruling", U_WORK, national)
    ruling = doc(40, "62020CJ0646", date(2022, 11, 10), "ECLI:EU:C:2022:879")
    records, _ = rel.links_for_rows(
        [row], lookups(celex_map={U_WORK: ["62020CJ0646"]}, by_celex={"62020CJ0646": ruling})
    )
    r = records[0]
    assert (r.source.celex, r.target.ecli, r.relation_type, r.match_method) == (
        "82018AT0228(51)",
        "ECLI:EU:C:2022:879",
        "preliminary_reference",
        "celex/uuid_celex",
    )
    # not loaded yet: without the ruling's date a referral cannot be told from a
    # follow-up, so nothing is written
    lk = lookups(celex_map={U_WORK: ["62020CJ0646"]})
    assert rel.resolve_row(row, lk) == (None, "ruling_not_in_database")


def test_national_decision_after_the_ruling_is_a_follow_up():
    # uuid_rows.json: 82023DE0426(51) referred_for_preliminary_ruling -> the work of
    # 62020CJ0646 (uuid_map.json), a ruling of 2022: the decision follows it
    national = doc(30, "82023DE0426(51)", date(2023, 4, 26))
    row = rel.CellarRow(1, "referred_for_preliminary_ruling", U_WORK, national)
    ruling = doc(40, "62020CJ0646", date(2022, 11, 10), "ECLI:EU:C:2022:879")
    lk = lookups(celex_map={U_WORK: ["62020CJ0646"]}, by_celex={"62020CJ0646": ruling})
    records, _ = rel.links_for_rows([row], lk)
    assert [(r.source.celex, r.relation_type) for r in records] == [
        ("82023DE0426(51)", "national_follow_up")
    ]
    undated = rel.CellarRow(1, "referred_for_preliminary_ruling", U_WORK, doc(30, "82023DE0426"))
    assert rel.resolve_row(undated, lk) == (None, "no_dates")


def test_targets_must_be_decisions_and_several_orders_are_not_guessed():
    # uuid_map.json: 82020DE0624(51) -> 62020CN0604, the published request, not a ruling
    national = doc(30, "82020DE0624(51)", date(2020, 6, 24))
    row = rel.CellarRow(1, "referred_for_preliminary_ruling", U_WORK, national)
    lk = lookups(celex_map={U_WORK: ["62020CN0604"]})
    assert rel.resolve_row(row, lk) == (None, "target_not_a_decision")
    orders = [
        cand(21, "62001CO0361", date(2002, 1, 1), "C-361/01 P"),
        cand(22, "62001CO0361(01)", date(2004, 1, 1), "C-361/01 P"),
    ]
    lk = lookups(dossier={U_KIK: ["C-361/01 P"]}, by_number={"C-361/01": orders})
    assert rel.resolve_row(KIK_ROW, lk) == (None, "several_orders")
    lk = lookups(dossier={U_KIK: ["C-361/01 P"]}, by_number={"C-361/01": orders[:1]})
    assert rel.resolve_row(KIK_ROW, lk)[0].confidence == 0.85


def test_unresolved_case_numbers():
    # a review decision not loaded yet: written unresolved for late binding
    row = rel.CellarRow(5, "reexamined_by", "C-1/11 RX", doc(30, "62010TJ0001"))
    records, _ = rel.links_for_rows([row], lookups())
    assert records[0].target is None
    assert (records[0].target_ref_raw, records[0].target_ref_scheme) == (
        "C-1/11",
        "cjeu_case_number",
    )
    # an unresolved reference: the method alone, no confidence
    assert (records[0].match_method, records[0].confidence) == ("case_number", None)
    # a referral to a ruling not loaded yet: skipped (no date to tell)
    row = rel.CellarRow(5, "referred_for_preliminary_ruling", "C-89/24 PPU", doc(30, "82024NL1"))
    assert rel.resolve_row(row, lookups()) == (None, "ruling_not_in_database")


def test_reexamined_by_keeps_direction():
    reviewed = doc(50, "62010TJ0001", date(2011, 1, 1))
    review = cand(51, "62011CJ0001", date(2012, 1, 1), "C-1/11 RX-II")
    row = rel.CellarRow(6, "reexamined_by", "C-1/11 RX-II", reviewed)
    records, _ = rel.links_for_rows([row], lookups(by_number={"C-1/11": [review]}))
    assert (records[0].source.celex, records[0].target.celex, records[0].relation_type) == (
        "62010TJ0001",
        "62011CJ0001",
        "reexamined_by",
    )


def test_already_resolved_rows_and_ambiguous_uuids():
    target = doc(20, "62001CJ0361", date(2003, 9, 9))
    row = rel.CellarRow(7, "subject_to_appeal", "62001CJ0361", KIK_GC, target)
    records, _ = rel.links_for_rows([row], lookups())
    assert records[0].source.celex == "62001CJ0361"
    lk = lookups(dossier={U_KIK: ["C-361/01 P", "C-362/01 P"]})
    assert rel.resolve_row(KIK_ROW, lk) == (None, "uuid_ambiguous")


def test_duplicate_rows_merge_into_one_record():
    lk = lookups(dossier={U_KIK: ["C-361/01 P"]}, by_number={"C-361/01": [KIK_APPEAL]})
    other = rel.CellarRow(9, "subject_to_appeal", U_KIK + ".0001", KIK_GC)
    records, _ = rel.links_for_rows([KIK_ROW, other], lk)
    assert len(records) == 1 and len(records[0].mentions) == 2


# ---------------------------------------------------------------------------
# SPARQL refresh: separate, never called by extract
# ---------------------------------------------------------------------------


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_uuid_values_with_a_fake_endpoint():
    seen = []

    def fake_urlopen(request, timeout):
        seen.append(request.data.decode())
        body = {"results": {"bindings": [{"w": {"value": U_KIK}, "v": {"value": "C-361/01 P"}}]}}
        return _Response(json.dumps(body).encode())

    out = rel.fetch_uuid_values([U_KIK, U_KIK], urlopen=fake_urlopen, pause=0)
    assert out == {U_KIK: ["C-361/01 P"]}
    assert len(seen) == 1 and "dossier_identifier" in seen[0]


@needs_db
def test_extract_never_calls_the_network_and_loads(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    from data_loading.link_loader import load_artifact

    def no_network(*args, **kwargs):
        raise AssertionError("extract must not call Cellar")

    monkeypatch.setattr(rel, "fetch_uuid_values", no_network)
    conn = scratch_db
    gc = add_case(conn, "ECLI:EU:T:2001:184", "61999TJ0120", date(2001, 7, 12))
    appeal = add_case(conn, "ECLI:EU:C:2003:452", "62001CJ0361", date(2003, 9, 9))
    add_identifier(conn, appeal, "cjeu_case_number", "C-361/01 P", "C-361/01")
    national = add_case(conn, None, "82018AT0228(51)", date(2018, 2, 28))
    add_case(conn, "ECLI:EU:C:2022:879", "62020CJ0646", date(2022, 11, 10))
    execute(
        conn,
        """INSERT INTO cle_v2.case_citation (source_case_id, target_celex_raw, relation_type,
                                             source_dataset)
           VALUES (%s, %s, 'subject_to_appeal', 'cellar_sparql'),
                  (%s, %s, 'referred_for_preliminary_ruling', 'cellar_sparql'),
                  (%s, 'C-1/99', 'cites', 'cellar_sparql')""",
        (gc, U_KIK, national, U_WORK, gc),
    )
    before = execute(conn, "SELECT * FROM cle_v2.case_citation ORDER BY id")

    out = tmp_path / "cellar_relation_resolved.jsonl"
    idents = tmp_path / "identifiers.jsonl"
    written, stats = rel.extract(
        conn,
        out_path=out,
        uuid_dossier={"8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1": ["C-361/01 P"]},
        uuid_celex={"05a39798-64c7-11ed-92ed-01aa75ed71a1": ["62020CJ0646"]},
        identifiers_out=idents,
        batch_size=1,
    )
    assert written == 2 and stats["dossier_identifiers"] == 1
    records = {r.relation_type: r for r in read_jsonl(out)}
    assert records["appeal_of"].source.ecli == "ECLI:EU:C:2003:452"
    assert records["appeal_of"].target.ecli == "ECLI:EU:T:2001:184"
    assert records["preliminary_reference"].target.ecli == "ECLI:EU:C:2022:879"
    assert json.loads(idents.read_text())["case"] == {"ecli": "ECLI:EU:C:2003:452"}

    counts = load_artifact(conn, out)
    assert counts == {
        "cellar_relation_resolved": {
            "inserted": 2,
            "mentions_inserted": 2,
        }
    }
    # the old rows are untouched
    assert (
        execute(
            conn,
            "SELECT * FROM cle_v2.case_citation WHERE source_dataset = 'cellar_sparql' ORDER BY id",
        )
        == before
    )
    # R2.7: both corpora are CJEU -> not cross-jurisdiction
    assert (
        execute(
            conn,
            """SELECT relation_type, is_cross_jurisdiction FROM cle_v2.case_citation
            WHERE source_dataset = 'cellar_relation_resolved' ORDER BY 1""",
        )
        == [("appeal_of", False), ("preliminary_reference", False)]
    )


@needs_db
def test_weekly_run_of_the_appeal_links_the_earlier_decision(scratch_db, tmp_path):  # noqa: F811
    """Finding 4: the General Court decision (with its subject_to_appeal row)
    and the national decision (referred_for_preliminary_ruling) are loaded
    first; the runs that load the appeal and the ruling pass only those case
    ids and still write appeal_of and preliminary_reference."""
    from data_loading.link_loader import load_artifact

    conn = scratch_db
    gc = add_case(conn, "ECLI:EU:T:2001:184", "61999TJ0120", date(2001, 7, 12))
    national = add_case(conn, None, "82018AT0228(51)", date(2018, 2, 28))
    unrelated = add_case(conn, "ECLI:EU:T:2005:1", "62003TJ0001", date(2005, 1, 1))
    execute(
        conn,
        """INSERT INTO cle_v2.case_citation (source_case_id, target_celex_raw, relation_type,
                                             source_dataset)
           VALUES (%s, %s, 'subject_to_appeal', 'cellar_sparql'),
                  (%s, %s, 'referred_for_preliminary_ruling', 'cellar_sparql'),
                  (%s, 'C-9/06 P', 'subject_to_appeal', 'cellar_sparql')""",
        (gc, U_KIK, national, U_WORK, unrelated),
    )
    maps = {
        "uuid_dossier": {"8e630f9b-8e2b-11f0-bfe2-01aa75ed71a1": ["C-361/01 P"]},
        "uuid_celex": {"05a39798-64c7-11ed-92ed-01aa75ed71a1": ["62020CJ0646"]},
    }
    first = tmp_path / "first.jsonl"
    written, _stats = rel.extract(conn, case_ids=[gc, national, unrelated], out_path=first, **maps)
    assert written == 0

    appeal = add_case(conn, "ECLI:EU:C:2003:452", "62001CJ0361", date(2003, 9, 9))
    add_identifier(conn, appeal, "cjeu_case_number", "C-361/01 P", "C-361/01")
    ruling = add_case(conn, "ECLI:EU:C:2022:879", "62020CJ0646", date(2022, 11, 10))
    later = tmp_path / "later.jsonl"
    written, stats = rel.extract(conn, case_ids=[appeal, ruling], out_path=later, **maps)
    assert written == 2
    assert stats["rows_subject_to_appeal"] == 1  # the unrelated decision is not revisited
    assert {(r.source.ecli or r.source.celex, r.target.ecli, r.relation_type)
            for r in read_jsonl(later)} == {
        ("ECLI:EU:C:2003:452", "ECLI:EU:T:2001:184", "appeal_of"),
        ("82018AT0228(51)", "ECLI:EU:C:2022:879", "preliminary_reference"),
    }  # fmt: skip
    counts = load_artifact(conn, later)
    assert counts == {"cellar_relation_resolved": {"inserted": 2, "mentions_inserted": 2}}
