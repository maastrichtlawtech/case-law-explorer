"""
Outcome and status parsing (roadmap R5.1, R5.2), without a database.

Test data:
  * CJEU: the 15 type_procedure values listed in case-law-explorer issue #83,
    with their counts in its 3,552-case sample of the live API. These are real
    field values (the precision sample for cjeu_outcomes).
  * ECtHR: the research files (cjeu-migration migration/verify/
    research-2026-11-24) hold no HUDOC conclusion or violation values, so the
    strings marked ILLUSTRATIVE follow HUDOC's documented field layout but are
    written for the test, not copied from a case.
  * Rechtspraak: the research files hold no judgment text; every dictum string
    is ILLUSTRATIVE, written for the test (the module stays behind
    RS_DICTUM_ENABLED until a db-dev sample is checked).
"""

from datetime import date

import pytest

from data_extraction.case_context import (
    artifact,
    case_status,
    cjeu_outcomes,
    echr_outcomes,
    rs_dictum,
)
from data_extraction.linking.artifact import ArtifactError, CaseKey

# ---------------------------------------------------------------------------
# CJEU: the issue #83 sample (real values)
# ---------------------------------------------------------------------------

ISSUE_83_SAMPLE = [
    # (count in the sample, proc_type, expected outcome, expected reason)
    (1047, "Reference for a preliminary ruling", None, "no_suffix"),
    (779, "", None, "empty"),
    (608, "Action for annulment - unfounded", "unfounded", "ok"),
    (238, "Action for annulment", None, "no_suffix"),
    (178, "Action for failure to fulfil obligations - successful", "successful", "ok"),
    (140, "Action for annulment - successful", "successful", "ok"),
    (119, "Staff cases - unfounded", "unfounded", "ok"),
    (88, "Action for annulment - inadmissible", "inadmissible", "ok"),
    (60, "Appeal - unfounded", "unfounded", "ok"),
    (30, "Reference for a preliminary ruling - inadmissible", "inadmissible", "ok"),
    (14, "Preliminary reference - urgent procedure", None, "procedure_variant"),
    (7, "Action for annulment - decision unnecessary", "decision_unnecessary", "ok"),
    (
        6,
        "Staff cases - amicable settlement made between the parties",
        "amicable_settlement",
        "ok",
    ),
    (1, "Request for an Opinion - agreement compatible", "agreement_compatible", "ok"),
    (1, "Action for annulment - interlocutory judgment", "interlocutory", "ok"),
]


@pytest.mark.parametrize("count, value, outcome, reason", ISSUE_83_SAMPLE)
def test_cjeu_issue_83_values(count, value, outcome, reason):
    assert cjeu_outcomes.parse_proc_type(value) == (outcome, reason)


def test_cjeu_issue_83_sample_totals():
    # 15 distinct values, 3,316 of the 3,552 sampled cases; 1,238 of them get
    # an outcome row, 2,078 none (no suffix, empty, a procedure variant).
    assert len(ISSUE_83_SAMPLE) == 15
    assert sum(c for c, *_ in ISSUE_83_SAMPLE) == 3316
    assert sum(c for c, _, o, _ in ISSUE_83_SAMPLE if o) == 1238
    assert sum(c for c, _, o, _ in ISSUE_83_SAMPLE if not o) == 2078


def test_cjeu_split_keeps_the_procedure_and_splits_on_the_last_separator():
    assert cjeu_outcomes.split_proc_type("Action for annulment - unfounded") == (
        "Action for annulment",
        "unfounded",
    )
    # ILLUSTRATIVE: a procedure containing ' - ' itself
    assert cjeu_outcomes.split_proc_type("A - B - successful") == ("A - B", "successful")
    assert cjeu_outcomes.split_proc_type("  Appeal  -  unfounded ") == ("Appeal", "unfounded")
    assert cjeu_outcomes.split_proc_type(None) == (None, None)


def test_cjeu_unknown_suffix_is_not_guessed():
    # ILLUSTRATIVE suffix not in issue #83's list
    assert cjeu_outcomes.parse_proc_type("Action for annulment - partly founded") == (
        None,
        "unrecognised_suffix",
    )


def test_cjeu_only_decisions_get_a_row():
    from collections import Counter

    stats = Counter()
    value = "Action for annulment - unfounded"
    record = cjeu_outcomes.outcome_record(None, "62019TJ0001", value, stats)
    assert record.outcome == "unfounded" and record.raw_value == value
    assert record.case == CaseKey(celex="62019TJ0001") and record.scope == "overall"
    assert cjeu_outcomes.outcome_record("ECLI:EU:C:2020:1", "62019CC0001", value, stats) is None
    assert cjeu_outcomes.outcome_record(None, "62019CN0001", value, stats) is None
    assert stats["not_a_decision"] == 2
    assert cjeu_outcomes.is_decision_celex("61991CV0001")  # Opinion 1/91 of the Court
    assert cjeu_outcomes.is_decision_celex("62012CO0005")


# ---------------------------------------------------------------------------
# ECtHR (ILLUSTRATIVE strings in HUDOC's layout)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "item, expected",
    [
        (
            "Violation of Article 3 - Prohibition of torture (Article 3 - Effective investigation) "
            "(Procedural aspect)",
            ("violation", "3"),
        ),
        (
            "No violation of Article 8 - Right to respect for private and family life",
            ("no_violation", "8"),
        ),
        (
            "Violation of Article 6 - Right to a fair trial (Article 6 - Criminal proceedings; "
            "Article 6-1 - Fair hearing)",
            ("violation", "6"),
        ),
        (
            "Violation of Article 1 of Protocol No. 1 - Protection of property",
            ("violation", "P1-1"),
        ),
        ("Violation of P1-1", ("violation", "P1-1")),
        ("No-violation of Art. 6-1", ("no_violation", "6")),
        ("Violation of Article 14+8 - Prohibition of discrimination", ("violation", "14")),
        # ILLUSTRATIVE (review 2026-11-24): the lead article, not the protocol one
        ("Violation of Article 14+P1-1 - Prohibition of discrimination", ("violation", "14")),
        (
            "Violation of Article 14 taken in conjunction with Article 1 of Protocol No. 1",
            ("violation", "14"),
        ),
        ("Violation of Article 14 in conjunction with Article 8", ("violation", "14")),
        (
            "Violation of Article 1 of Protocol No. 1 taken in conjunction with Article 14",
            ("violation", "P1-1"),
        ),
        ("Violation of P1-1+14", ("violation", "P1-1")),
        ("Inadmissible", ("inadmissible", None)),
        ("Struck out of the list", ("struck_out", None)),
        ("Struck out of the list (Friendly settlement)", ("struck_out", None)),
        ("Remainder inadmissible", (None, None)),
        ("Partly inadmissible", (None, None)),
        ("Non-pecuniary damage - award", (None, None)),
        (
            "Preliminary objection dismissed (Article 35-1 - Exhaustion of domestic remedies)",
            (None, None),
        ),
        ("Violation de l'article 3", ("violation", "3")),
        ("Non-violation de l'article 8", ("no_violation", "8")),
        ("Pas de violation de l'article 1 du Protocole n° 1", ("no_violation", "P1-1")),
        ("Violation de l'art. 14 combiné avec l'art. 8", ("violation", "14")),
        ("Irrecevable", ("inadmissible", None)),
        ("Radiation du rôle", ("struck_out", None)),
        ("Rayée du rôle", ("struck_out", None)),
        ("Partiellement irrecevable", (None, None)),
    ],
)
def test_echr_conclusion_items(item, expected):
    outcome, article, _ = echr_outcomes.parse_conclusion_item(item)
    assert (outcome, article) == expected


def test_echr_violation_without_a_readable_article_is_not_guessed():
    assert echr_outcomes.parse_conclusion_item("Violation of the Convention") == (
        None,
        None,
        "unreadable_article",
    )


def test_echr_split_items_ignores_semicolons_inside_parentheses():
    conclusion = (  # ILLUSTRATIVE
        "Violation of Article 6 - Right to a fair trial (Article 6 - Criminal proceedings; "
        "Article 6-1 - Fair hearing);No violation of Article 13;Non-pecuniary damage - award"
    )
    assert len(echr_outcomes.split_items(conclusion)) == 3


@pytest.mark.parametrize(
    "token, article",
    [
        ("3", "3"),
        ("6-1", "6"),
        ("6-3-c", "6"),
        ("P1-1", "P1-1"),
        ("P4-2", "P4-2"),
        ("14+8", "14"),
        ("14+P1-1", "14"),
        ("P1-1-1", "P1-1"),
        ("x", None),
    ],
)
def test_echr_field_tokens(token, article):
    assert echr_outcomes.article_from_token(token) == article


def test_echr_case_outcomes_merge_fields_and_conclusion():
    from collections import Counter

    key = CaseKey(ecli="ECLI:CE:ECHR:2014:0626JUD007139812")
    documents = [  # ILLUSTRATIVE values; two language versions of one judgment
        (
            "Violation of Article 3 - Prohibition of torture;No violation of Article 8 - Right to "
            "respect for private and family life;Remainder inadmissible",
            "3",
            "",
            [],
        ),
        (None, "3", None, [("violation", "3"), ("nonviolation", "8")]),
    ]
    records = echr_outcomes.outcomes_for_documents(key, documents, Counter())
    got = {(r.scope, r.article, r.outcome): r for r in records}
    assert set(got) == {("article", "3", "violation"), ("article", "8", "no_violation")}
    violation = got[("article", "3", "violation")]
    assert violation.confidence == echr_outcomes.CONFIDENCE_FIELD
    assert violation.raw_value == (
        "conclusion: Violation of Article 3 - Prohibition of torture | "
        "echr_document_article: 3 | violation: 3"
    )


def test_echr_both_limbs_of_an_article():
    from collections import Counter

    key = CaseKey(ecli="ECLI:CE:ECHR:2000:0101JUD000000100")  # ILLUSTRATIVE
    records = echr_outcomes.outcomes_for_documents(
        key,
        [
            (
                "Violation of Article 2 - Right to life (Procedural aspect);"
                "No violation of Article 2 - Right to life (Substantive aspect)",
                None,
                None,
                [],
            )
        ],
        Counter(),
    )
    assert {(r.article, r.outcome) for r in records} == {("2", "violation"), ("2", "no_violation")}
    assert all(r.confidence == echr_outcomes.CONFIDENCE_CONCLUSION for r in records)


# ---------------------------------------------------------------------------
# Rechtspraak dictum (ILLUSTRATIVE texts)
# ---------------------------------------------------------------------------

HR_DISMISSED = """... overwegingen ...
5 Beslissing
De Hoge Raad:
- verwerpt het beroep;
- veroordeelt de eiser in de kosten van het geding in cassatie.
Dit arrest is gewezen door de vice-president ..."""

HR_QUASHED = """... overwegingen ...
4. Beslissing
De Hoge Raad:
- vernietigt het arrest van het gerechtshof Amsterdam van 1 januari 2020;
- verwijst het geding naar het gerechtshof Den Haag ter verdere behandeling en beslissing.
Dit arrest is gewezen door ..."""

RVS_UPHELD = """Beslissing
De Afdeling bestuursrechtspraak van de Raad van State:
I. verklaart het hoger beroep gegrond;
II. vernietigt de uitspraak van de rechtbank;
III. verklaart het beroep tegen het besluit ongegrond.
Aldus vastgesteld door ..."""

RVS_DISMISSED = """Beslissing
De Afdeling bestuursrechtspraak van de Raad van State:
verklaart het hoger beroep ongegrond;
bevestigt de aangevallen uitspraak.
Aldus vastgesteld door ..."""

HOF_AFFIRMED = """6 De beslissing
Het hof:
bekrachtigt het vonnis waarvan beroep;
veroordeelt appellant in de kosten van het hoger beroep.
Dit arrest is gewezen door ..."""

HOF_PARTIAL = """7 De beslissing
Het hof:
vernietigt het vonnis waarvan beroep, voor zover daarbij de vordering is afgewezen;
bekrachtigt het vonnis voor het overige.
Dit arrest is gewezen door ..."""

HOF_CONFLICT = """De beslissing
Het hof:
vernietigt het tussenvonnis van 1 maart 2019;
bekrachtigt het eindvonnis van 1 juni 2019.
Dit arrest is gewezen door ..."""

ANNULS_ADMIN_DECISION = """Beslissing
De rechtbank:
- vernietigt het bestreden besluit;
- draagt verweerder op een nieuw besluit te nemen.
Deze uitspraak is gedaan door ..."""

NO_HEADING = "De rechtbank verwerpt het beroep van eiser, zoals hiervoor overwogen."

QUOTED_LOWER_COURT = """2 De beslissing van de rechtbank
De rechtbank heeft het beroep ongegrond verklaard.
Beslissing
De Afdeling bestuursrechtspraak van de Raad van State:
verklaart het hoger beroep gegrond;
vernietigt de aangevallen uitspraak.
Aldus vastgesteld door ..."""


@pytest.mark.parametrize(
    "text, outcomes, reason",
    [
        (HR_DISMISSED, {"dismissed"}, "ok"),
        (HR_QUASHED, {"quashed"}, "ok"),
        (RVS_UPHELD, {"upheld", "quashed"}, "ok"),
        (RVS_DISMISSED, {"dismissed"}, "ok"),
        (HOF_AFFIRMED, {"dismissed"}, "ok"),
        (HOF_PARTIAL, set(), "partial"),
        (HOF_CONFLICT, set(), "conflict"),
        (ANNULS_ADMIN_DECISION, set(), "no_phrase"),
        (NO_HEADING, set(), "no_operative_part"),
        (QUOTED_LOWER_COURT, {"upheld", "quashed"}, "ok"),
        (None, set(), "no_operative_part"),
    ],
)
def test_rs_dictum(text, outcomes, reason):
    found, got_reason = rs_dictum.parse_dictum(text)
    assert ({f[0] for f in found}, got_reason) == (outcomes, reason)


def test_rs_operative_part_ends_at_the_signature():
    part = rs_dictum.operative_part(HR_DISMISSED)
    assert part.startswith("De Hoge Raad:") and "gewezen" not in part


def test_rs_dictum_records_keep_the_phrases_as_raw_value():
    from collections import Counter

    key = CaseKey(ecli="ECLI:NL:RVS:2000:1")  # ILLUSTRATIVE
    records = rs_dictum.outcome_records(key, RVS_DISMISSED, Counter())
    assert len(records) == 1
    assert records[0].outcome == "dismissed"
    assert records[0].raw_value == (
        "bevestigt de aangevallen uitspraak | verklaart het hoger beroep ongegrond"
    )
    assert records[0].confidence == 0.9


def test_rs_dictum_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("RS_DICTUM_ENABLED", raising=False)
    assert not rs_dictum.enabled()
    monkeypatch.setenv("RS_DICTUM_ENABLED", "true")
    assert rs_dictum.enabled()


# ---------------------------------------------------------------------------
# statuses without a database
# ---------------------------------------------------------------------------


def _doc(case_id, ecli, item, doctype, branch, decided, conclusion=None, docname=None):
    return case_status.EchrDocument(
        case_id, ecli, item, item, doctype, branch, docname, decided, conclusion
    )


ME_CHAMBER = "ECLI:CE:ECHR:2014:0626JUD007139812"  # M.E. v. Sweden, Chamber, 26 June 2014
ME_GC = "ECLI:CE:ECHR:2015:0408JUD007139812"  # M.E. v. Sweden [GC], 8 April 2015


def test_me_v_sweden_statuses():
    from collections import Counter

    chamber = _doc(1, ME_CHAMBER, "001-a", "HEJUD", "CHAMBER", date(2014, 6, 26))
    gc = _doc(
        2,
        ME_GC,
        "001-b",
        "HEJUD",
        "GRANDCHAMBER",
        date(2015, 4, 8),
        conclusion="Struck out of the list",  # ILLUSTRATIVE conclusion value
    )
    own = case_status.own_statuses(gc, Counter())
    assert {(r.status, r.status_date) for r in own} == {
        ("struck_out", date(2015, 4, 8)),
        ("final", date(2015, 4, 8)),
    }
    referred = case_status.referral_statuses(
        gc, [chamber], {"001-a": ["71398/12"], "001-b": ["71398/12"]}
    )
    assert len(referred) == 1
    record = referred[0]
    assert record.case == CaseKey(ecli=ME_CHAMBER)
    assert record.related == CaseKey(ecli=ME_GC)
    assert record.status == "referred_to_grand_chamber" and record.status_date is None
    assert "71398/12" in record.raw_value
    # a Chamber judgment is not marked final, and nothing is referred without a shared appno
    assert case_status.own_statuses(chamber, Counter()) == []
    assert (
        case_status.referral_statuses(gc, [chamber], {"001-a": ["1/12"], "001-b": ["71398/12"]})
        == []
    )


def test_referral_needs_an_earlier_chamber_judgment():
    gc = _doc(2, ME_GC, "001-b", "HEJUD", "GRANDCHAMBER", date(2015, 4, 8))
    later = _doc(
        3, "ECLI:CE:ECHR:2016:0101JUD007139812", "001-c", "HEJUD", "CHAMBER", date(2016, 1, 1)
    )
    decision = _doc(
        4, "ECLI:CE:ECHR:2013:0101DEC007139812", "001-d", "HEDEC", "CHAMBER", date(2013, 1, 1)
    )
    appnos = {i: ["71398/12"] for i in ("001-b", "001-c", "001-d")}
    assert case_status.referral_statuses(gc, [later, decision], appnos) == []


def test_formations_and_final():
    from collections import Counter

    gc_by_name = _doc(
        1,
        "ECLI:CE:ECHR:2000:1",
        "i1",
        "HEJUD",
        None,
        date(2000, 1, 1),
        docname="CASE OF X v. Y [GC]",
    )
    assert gc_by_name.formation == "grand_chamber"
    committee = _doc(2, "ECLI:CE:ECHR:2000:2", "i2", "HEJUD", "Committee", date(2000, 1, 1))
    assert [r.status for r in case_status.own_statuses(committee, Counter())] == ["final"]
    inadmissible = _doc(
        3,
        "ECLI:CE:ECHR:2000:3",
        "i3",
        "HEDEC",
        "CHAMBER",
        date(2000, 1, 1),
        conclusion="Inadmissible",
    )
    assert [r.rule for r in case_status.own_statuses(inadmissible, Counter())] == [
        "final_inadmissible"
    ]
    partly = _doc(
        4,
        "ECLI:CE:ECHR:2000:4",
        "i4",
        "HEDEC",
        "CHAMBER",
        date(2000, 1, 1),
        conclusion="Partly inadmissible",
    )
    assert case_status.own_statuses(partly, Counter()) == []


def test_cjeu_appeal_status():
    from collections import Counter

    stats = Counter()
    appeal = ("ECLI:EU:C:2020:10", "62019CJ0010", date(2020, 1, 10), "Appeal - successful")
    record = case_status.appeal_status(appeal, ("ECLI:EU:T:2018:5", "62016TJ0005"), stats)
    assert record.status == "overturned" and record.case == CaseKey(ecli="ECLI:EU:T:2018:5")
    assert record.related == CaseKey(ecli="ECLI:EU:C:2020:10")
    assert record.raw_value == "Appeal - successful" and record.status_date == date(2020, 1, 10)
    dismissed = appeal[:3] + ("Appeal - unfounded",)
    assert case_status.appeal_status(dismissed, ("ECLI:EU:T:2018:5", None), stats) is None
    not_appeal = appeal[:3] + ("Action for annulment - successful",)
    assert case_status.appeal_status(not_appeal, ("ECLI:EU:T:2018:5", None), stats) is None
    assert stats["appeal_unfounded"] == 1 and stats["not_an_appeal_procedure"] == 1


# ---------------------------------------------------------------------------
# artifact
# ---------------------------------------------------------------------------


def test_artifact_round_trip_and_validation():
    outcome = artifact.OutcomeRecord(
        case=CaseKey(ecli="ECLI:CE:ECHR:2014:0626JUD007139812"),
        scope="article",
        article="3",
        outcome="violation",
        source_dataset="echr_conclusion",
        extractor_version="v",
        confidence=0.9,
    )
    assert artifact.record_from_dict(outcome.to_dict()) == outcome
    status = artifact.StatusRecord(
        case=CaseKey(ecli="A"),
        status="final",
        status_date=date(2015, 4, 8),
        source_dataset="echr_status",
        extractor_version="v",
    )
    assert artifact.record_from_dict(status.to_dict()) == status
    bad = [
        dict(outcome.to_dict(), outcome="won"),
        dict(outcome.to_dict(), scope="overall"),  # article without scope article
        dict(outcome.to_dict(), source_dataset="echr_status"),
        dict(outcome.to_dict(), confidence=1.5),
        dict(status.to_dict(), status="pending_forever"),
        dict(status.to_dict(), related={"ecli": "A"}),
        dict(status.to_dict(), status_date="2015-13-01"),
        dict(status.to_dict(), kind="link"),
        dict(status.to_dict(), case=None),
    ]
    for value in bad:
        with pytest.raises(ArtifactError):
            artifact.record_from_dict(value)


def test_echr_partial_inadmissibility_on_a_judgment_is_no_overall_outcome():
    from collections import Counter

    key = CaseKey(ecli="ECLI:CE:ECHR:2000:0101JUD000000100")  # ILLUSTRATIVE
    stats = Counter()
    records = echr_outcomes.outcomes_for_documents(
        key,
        [
            (
                "Inadmissible (Article 6);Violation of Article 3 - Prohibition of torture;"
                "Struck out of the list (Article 37-1-b)",
                None,
                None,
                [],
                "HEJUD",
            )
        ],
        stats,
    )
    assert {(r.scope, r.article, r.outcome) for r in records} == {("article", "3", "violation")}
    assert stats["overall_suppressed"] == 2


def test_echr_inadmissible_from_a_judgment_alone_is_not_overall():
    from collections import Counter

    key = CaseKey(ecli="ECLI:CE:ECHR:2000:0101JUD000000100")  # ILLUSTRATIVE
    records = echr_outcomes.outcomes_for_documents(
        key, [("Inadmissible", None, None, [], "HEJUD")], Counter()
    )
    assert records == []


def test_echr_decision_overall_outcomes_are_kept():
    from collections import Counter

    key = CaseKey(ecli="ECLI:CE:ECHR:2000:0101DEC000000100")  # ILLUSTRATIVE
    for doctype in ("HEDEC", None):
        records = echr_outcomes.outcomes_for_documents(
            key, [("Inadmissible", None, None, [], doctype)], Counter()
        )
        assert [(r.scope, r.outcome) for r in records] == [("overall", "inadmissible")]
    records = echr_outcomes.outcomes_for_documents(
        key, [("Struck out of the list (Friendly settlement)", None, None, [], "HEJUD")], Counter()
    )
    assert [(r.scope, r.outcome) for r in records] == [("overall", "struck_out")]
