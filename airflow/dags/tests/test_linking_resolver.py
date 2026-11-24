from datetime import date

from data_extraction.linking import resolver as r


def cjeu(case_id, celex, decided):
    return r.Candidate(case_id, None, celex, None, decided, r.cjeu_kind(celex), "C-1/20")


def echr(case_id, kind, decided):
    return r.Candidate(case_id, None, None, f"001-{case_id}", decided, kind, "17341/03")


def test_cjeu_kind():
    assert r.cjeu_kind("62017CJ0221") == "judgment"
    assert r.cjeu_kind("62019CO0001(01)") == "order"
    assert r.cjeu_kind("62012CC0199") == "opinion"
    assert r.cjeu_kind("62005TJ0123") == "judgment"
    assert r.cjeu_kind("32016R0679") == "other"
    assert r.cjeu_kind(None) == "other"


def test_echr_kind():
    assert r.echr_kind("HEJUD") == "judgment"
    assert r.echr_kind("hfdec") == "decision"
    assert r.echr_kind("HECOM") == "communicated"
    assert r.echr_kind(None) == "other"


def test_cjeu_prefers_judgment_over_order_and_opinion():
    pool = [
        cjeu(1, "62017CC0221", date(2018, 7, 12)),
        cjeu(2, "62017CJ0221", date(2019, 3, 12)),
        cjeu(3, "62017CO0221", date(2017, 9, 1)),
    ]
    choice = r.choose_cjeu(pool, date(2020, 2, 12))
    assert (choice.candidate.case_id, choice.rule, choice.confidence) == (2, "cjeu_judgment", 0.95)


def test_cjeu_opinion_only_with_cue():
    pool = [cjeu(1, "62012CC0199", date(2013, 7, 17)), cjeu(2, "62012CJ0199", date(2013, 11, 7))]
    assert r.choose_cjeu(pool, date(2014, 1, 1), opinion_cue=True).candidate.case_id == 1
    assert r.choose_cjeu(pool, date(2014, 1, 1), opinion_cue=False).candidate.case_id == 2


def test_cjeu_falls_back_to_order():
    choice = r.choose_cjeu([cjeu(3, "62017CO0010", date(2017, 5, 1))], date(2020, 1, 1))
    assert (choice.candidate.case_id, choice.rule) == (3, "cjeu_order")


def test_cjeu_never_later_than_source():
    pool = [cjeu(2, "62017CJ0221", date(2019, 3, 12))]
    assert r.choose_cjeu(pool, date(2018, 1, 1)) is None


def test_cjeu_earliest_of_several_judgments_has_lower_confidence():
    pool = [cjeu(5, "62019CJ0001(01)", date(2021, 1, 1)), cjeu(4, "62019CJ0001", date(2020, 1, 1))]
    choice = r.choose_cjeu(pool, None)
    assert (choice.candidate.case_id, choice.rule, choice.confidence) == (
        4,
        "cjeu_judgment_earliest_of_several",
        0.8,
    )


def test_echr_judgment_by_default_decision_with_cue():
    pool = [echr(1, "decision", date(2002, 1, 1)), echr(2, "judgment", date(2004, 6, 22))]
    assert r.choose_echr(pool, date(2010, 1, 1)).candidate.case_id == 2
    assert r.choose_echr(pool, date(2010, 1, 1), decision_cue=True).candidate.case_id == 1


def test_echr_decision_when_no_judgment_and_never_communicated():
    pool = [echr(1, "communicated", date(2001, 1, 1)), echr(2, "decision", date(2002, 1, 1))]
    choice = r.choose_echr(pool, None)
    assert (choice.candidate.case_id, choice.rule) == (2, "echr_decision_no_judgment")
    assert r.choose_echr([echr(1, "communicated", date(2001, 1, 1))], None) is None


def test_echr_several_judgments_by_date_then_year_then_earliest():
    pool = [
        echr(1, "judgment", date(2000, 5, 1)),
        echr(2, "judgment", date(2002, 3, 4)),
        echr(3, "judgment", date(2003, 1, 1)),
    ]
    assert r.choose_echr(pool, None, cited_date=date(2002, 3, 4)).rule == "echr_judgment_cited_date"
    assert r.choose_echr(pool, None, cited_year=2003).candidate.case_id == 3
    earliest = r.choose_echr(pool, None)
    assert (earliest.candidate.case_id, earliest.confidence) == (1, 0.75)


def test_candidate_key_prefers_ecli():
    c = r.Candidate(1, "ECLI:EU:C:2019:189", "62017CJ0221", None, None, "judgment", "C-221/17")
    assert c.key() == {"ecli": "ECLI:EU:C:2019:189"}
    assert r.Candidate(1, None, "62017CJ0221", None, None, "judgment", "x").key() == {
        "celex": "62017CJ0221"
    }
