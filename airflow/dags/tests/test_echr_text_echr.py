"""Unit tests for data_extraction.linking.echr_text_echr."""

from __future__ import annotations

import datetime as dt

from data_extraction.linking import echr_edge_v2, echr_text_echr
from data_extraction.linking.artifact import CaseKey


def test_strip_header_and_appendix_skips_own_header_and_joined_table():
    doc = (
        "FIRST SECTION\n"
        "CASE OF GUIDA v. ITALY\n"
        "(Application no. 37668/23)\n"
        "SUBJECT MATTER OF THE CASE\n"
        "1. The applicant complains (see Ananyev and Others v. Russia, nos. 42525/07 and 60800/08, § 78, 10 January 2012).\n"
        "APPENDIX\n"
        "List of applications: no. 99999/20, no. 88888/20.\n"
    )
    clauses = echr_text_echr.extract_citation_clauses(doc, own_appnos={"37668/23"})
    assert len(clauses) == 1
    assert clauses[0].appnos == ("42525/07", "60800/08")


def test_extract_citation_clauses_rejects_domestic_law_numbers():
    doc = (
        "THE FACTS\n"
        "1. Under section 35 bis of Law no. 354/75 and Decree no. 12/05 the applicant appealed.\n"
        "2. The Court recalls Kudła v. Poland [GC], no. 30210/96, § 152, ECHR 2000-XI.\n"
    )
    clauses = echr_text_echr.extract_citation_clauses(doc, own_appnos={"11111/20"})
    assert len(clauses) == 1
    assert clauses[0].appnos == ("30210/96",)


def test_resolve_case_fulltext_uses_owner_index_and_prevents_self_loops():
    cand_ananyev = echr_edge_v2.TargetCandidate(
        case_id=200,
        ecli="ECLI:CE:ECHR:2012:0110JUD004252507",
        item_id="001-108465",
        date_decision=dt.date(2012, 1, 10),
        kind="judgment",
        branch="CHAMBER",
        secondary_kind=None,
    )
    owner_index = {
        "42525/07": [cand_ananyev],
        "60800/08": [cand_ananyev],
    }
    doc = (
        "THE COURT'S ASSESSMENT\n"
        "21. See Ananyev and Others v. Russia, nos. 42525/07 and 60800/08, § 78, 10 January 2012.\n"
    )
    recs = echr_text_echr.resolve_case_fulltext(
        source_case_id=999,
        source_key=CaseKey(ecli="ECLI:CE:ECHR:2026:1119JUD003766823", item_id="001-999999"),
        source_date=dt.date(2026, 11, 19),
        own_appnos={"37668/23"},
        texts=[("en", doc)],
        owner_by_appno=owner_index,
    )
    assert len(recs) == 1
    assert recs[0].source_dataset == "echr_text_echr"
    assert recs[0].target.ecli == "ECLI:CE:ECHR:2012:0110JUD004252507"
    assert recs[0].relation_type == "cites"
    recs[0].validate()
