"""
AG opinion -> judgment links (R2.4). CELEX numbers and case numbers are real
(research rs/allres_nums.txt, cjeu/cn_map.json, the evaluation set's
ag-link-01: 62012CC0199 -> 62012CJ0199).
"""

from datetime import date

from data_extraction.linking import ag_opinions as ag
from data_extraction.linking import resolver
from data_extraction.linking.artifact import read_jsonl
from tests.linking_db import add_case, add_identifier, execute, needs_db, scratch_db  # noqa: F401

OPINION = ag.Opinion(1, "ECLI:EU:C:2013:474", "62012CC0199", date(2013, 7, 11), ("C-199/12",))
JUDGMENT = ag.Document(2, "ECLI:EU:C:2013:720", "62012CJ0199", date(2013, 11, 7))


def cand(case_id, celex, decided, value="C-199/12"):
    return resolver.Candidate(case_id, None, celex, None, decided, resolver.cjeu_kind(celex), value)


def test_swapped_celex():
    assert ag.swapped_celex("62012CC0199", "CJ") == ["62012CJ0199"]
    assert ag.swapped_celex("62019CC0001(01)", "CO") == ["62019CO0001(01)", "62019CO0001"]
    assert ag.swapped_celex("62012CJ0199", "CJ") == []
    assert ag.swapped_celex(None, "CJ") == []


def test_cc_to_cj():
    resolution, reason = ag.resolve_opinion(OPINION, {"62012CJ0199": JUDGMENT}, {})
    assert reason == "ok"
    assert (resolution.target, resolution.method, resolution.confidence) == (
        JUDGMENT,
        "celex",
        0.98,
    )
    record = ag.record_for(OPINION, resolution)
    assert record.to_dict() == {
        "source": {"ecli": "ECLI:EU:C:2013:474"},
        "target": {"ecli": "ECLI:EU:C:2013:720"},
        "relation_type": "opinion_of",
        "source_dataset": "cjeu_ag_link",
        "extractor_version": "ag_opinions/1.0.0",
        "match_method": "celex",
        "confidence": 0.98,
    }


def test_cc_to_co_when_there_is_no_judgment():
    # C-10/17 has only an order (cn_map.json: 62017CO0010)
    opinion = ag.Opinion(1, None, "62017CC0010", date(2018, 1, 1), ("C-10/17",))
    order = ag.Document(3, None, "62017CO0010", date(2018, 5, 1))
    resolution, _ = ag.resolve_opinion(opinion, {"62017CO0010": order}, {})
    assert (resolution.target.celex, resolution.rule, resolution.confidence) == (
        "62017CO0010",
        "celex_co",
        0.8,
    )
    assert ag.record_for(opinion, resolution).source.celex == "62017CC0010"


def test_joined_judgment_beats_an_order_sharing_the_number():
    """Aalborg Portland (research rs/allres_nums.txt): the opinion 62000CC0205
    has a CO with its number, but the judgment is filed under C-204/00 P,
    which case_identifier lists for C-205/00 as a joined member."""
    opinion = ag.Opinion(1, None, "62000CC0205", date(2003, 2, 11), ("C-205/00",))
    order = ag.Document(3, None, "62000CO0205", date(2004, 1, 7))
    joined = {"C-205/00": [cand(4, "62000CJ0204", date(2004, 1, 7), "C-205/00 P")]}
    resolution, _ = ag.resolve_opinion(opinion, {"62000CO0205": order}, joined)
    assert (resolution.target.celex, resolution.method) == ("62000CJ0204", "case_number")
    # without the joined judgment, the order is the last resort
    resolution, _ = ag.resolve_opinion(opinion, {"62000CO0205": order}, {})
    assert resolution.rule == "celex_co"


def test_target_before_the_opinion_is_refused():
    early_order = ag.Document(3, None, "62012CO0199", date(2012, 6, 1))  # e.g. an interim order
    resolution, reason = ag.resolve_opinion(OPINION, {"62012CO0199": early_order}, {})
    assert resolution is None and reason == "dated_before_opinion"


def test_case_number_fallback_first_judgment_on_or_after_the_opinion():
    # the opinion lost its CELEX in loading; only its case number is known
    opinion = ag.Opinion(1, "ECLI:EU:C:2013:474", None, date(2013, 7, 11), ("C-199/12",))
    candidates = {
        "C-199/12": [
            cand(1, None, date(2013, 7, 11)),  # the opinion itself (no CELEX, kind other)
            cand(5, "62012CJ0199", date(2013, 11, 7)),
            cand(6, "62012CJ0199(01)", date(2014, 2, 1)),  # a later judgment-kind document
            cand(7, "62012CO0199", date(2012, 1, 1)),
        ]
    }
    resolution, reason = ag.resolve_opinion(opinion, {}, candidates)
    assert reason == "ok"
    assert (resolution.target.case_id, resolution.method) == (5, "case_number")


def test_case_number_fallback_refuses_ties_and_disagreement():
    opinion = ag.Opinion(1, None, None, date(2013, 1, 1), ("C-1/12", "C-2/12"))
    same_day = {
        "C-1/12": [
            cand(5, "62012CJ0001", date(2013, 5, 1), "C-1/12"),
            cand(6, "62012CJ0001(01)", date(2013, 5, 1), "C-1/12"),
        ]
    }
    assert ag.resolve_opinion(opinion, {}, same_day) == (None, "several_judgments_same_day")
    disagree = {
        "C-1/12": [cand(5, "62012CJ0001", date(2013, 5, 1), "C-1/12")],
        "C-2/12": [cand(6, "62012CJ0002", date(2013, 6, 1), "C-2/12")],
    }
    assert ag.resolve_opinion(opinion, {}, disagree) == (None, "case_numbers_disagree")
    undated = ag.Opinion(1, None, None, None, ("C-1/12",))
    assert ag.resolve_opinion(undated, {}, disagree) == (None, "no_opinion_date")


@needs_db
def test_extract_and_load(scratch_db, tmp_path):  # noqa: F811
    from data_loading.link_loader import load_artifact

    conn = scratch_db
    opinion = add_case(conn, "ECLI:EU:C:2013:474", "62012CC0199", date(2013, 7, 11))
    execute(conn, "INSERT INTO cle_v2.cjeu_ag_opinion (case_id) VALUES (%s)", (opinion,))
    add_case(conn, "ECLI:EU:C:2013:720", "62012CJ0199", date(2013, 11, 7))
    # an opinion without CELEX, resolved through its case number
    lost = add_case(conn, "ECLI:EU:C:2019:1", None, date(2019, 1, 10))
    execute(conn, "INSERT INTO cle_v2.cjeu_ag_opinion (case_id) VALUES (%s)", (lost,))
    add_identifier(conn, lost, "cjeu_case_number", "C-5/18", "C-5/18")
    judgment = add_case(conn, "ECLI:EU:C:2019:300", "62018CJ0005", date(2019, 4, 10))
    add_identifier(conn, judgment, "cjeu_case_number", "C-5/18", "C-5/18")
    # an opinion with nothing to link to
    add_case(conn, "ECLI:EU:C:2020:9", "62020CC0009", date(2020, 2, 1))

    out = tmp_path / "cjeu_ag_link.jsonl"
    written, stats = ag.extract(conn, out_path=out, batch_size=2)
    assert written == 2
    assert stats["opinions"] == 3 and stats["no_case_number"] == 1
    assert {(r.source.ecli, r.target.ecli, r.match_method) for r in read_jsonl(out)} == {
        ("ECLI:EU:C:2013:474", "ECLI:EU:C:2013:720", "celex"),
        ("ECLI:EU:C:2019:1", "ECLI:EU:C:2019:300", "case_number"),
    }
    counts = load_artifact(conn, out)
    assert counts == {"cjeu_ag_link": {"inserted": 2}}
    # R2.7: opinion -> judgment stays within the CJEU corpus
    assert execute(
        conn, "SELECT DISTINCT relation_type, is_cross_jurisdiction FROM cle_v2.case_citation"
    ) == [("opinion_of", False)]
    # parent_case_id is not touched
    assert execute(
        conn, "SELECT count(*) FROM cle_v2.cjeu_ag_opinion WHERE parent_case_id IS NOT NULL"
    ) == [(0,)]
