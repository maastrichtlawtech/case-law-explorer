"""Unit tests for the R6.1 ECtHR scl -> ECtHR case link extractor (echr_edge_v2)."""

import datetime as dt

from data_extraction.linking import echr_edge_v2 as mod
from data_extraction.linking.artifact import read_jsonl


def _cand(
    case_id: int,
    ecli: str = None,
    item_id: str = None,
    date_decision: dt.date = None,
    kind: str = "judgment",
    branch: str = "CHAMBER",
    secondary_kind: str = None,
) -> mod.TargetCandidate:
    return mod.TargetCandidate(
        case_id=case_id,
        ecli=ecli,
        item_id=item_id or f"001-{case_id}",
        date_decision=date_decision,
        kind=kind,
        branch=branch,
        secondary_kind=secondary_kind,
    )


def test_parse_scl_entry_extracts_appnos_dates_and_cues():
    e1 = mod.parse_scl_entry(
        "Öcalan v. Turkey [GC], no. 46221/99, § 91, ECHR 2005-IV"
    )
    assert e1.appnos == ("46221/99",)
    assert e1.grand_chamber is True
    assert e1.decision_cue is False
    assert e1.cited_year == 2005
    assert e1.secondary_cue is None

    e2 = mod.parse_scl_entry(
        "Bosphorus Hava Yolları Turizm ve Ticaret Anonim Şirketi v. Ireland (dec.), no. 45036/98, 13 September 2001"
    )
    assert e2.appnos == ("45036/98",)
    assert e2.decision_cue is True
    assert e2.cited_date == dt.date(2001, 9, 13)
    assert e2.cited_year == 2001

    e3 = mod.parse_scl_entry(
        "Papamichalopoulos and Others v. Greece (Article 50), 31 October 1995, Series A no. 330-B, no. 14556/89"
    )
    assert e3.secondary_cue == "just_satisfaction"
    assert e3.cited_date == dt.date(1995, 10, 31)

    e4 = mod.parse_scl_entry(
        "No. 14063/88, déc. 7.1.91, D.R. 68, p. 177"
    )
    assert e4.appnos == ("14063/88",)
    assert e4.decision_cue is True
    assert e4.cited_date == dt.date(1991, 1, 7)


def test_split_scl_handles_missing_semicolons_and_commas():
    joined = (
        "Castell c. France (déc.), n° 38783/97, 27.4.1999, "
        "Delgardo c. France (déc.), n° 38437/97, 29.6.1999, "
        "Périé c. France (déc.), n° 38701/97, 11.1.2000"
    )
    parts = mod.split_scl(joined)
    assert len(parts) == 3
    assert "38783/97" in parts[0]
    assert "38437/97" in parts[1]
    assert "38701/97" in parts[2]

    glued = (
        "Altay v. Turkey, no. 22279/93, § 50, 22 May 2001"
        "Berktay v. Turkey, no. 22493/93, § 167, 1 March 2001"
    )
    assert len(mod.split_scl(glued)) == 2

    dr_joined = "No. 11111/84, déc. 1.2.88, D.R. 55, p. 12 No. 22222/85, déc. 3.4.89, D.R. 60, p. 34"
    dr_parts = mod.split_scl(dr_joined)
    assert len(dr_parts) == 2
    assert "11111/84" in dr_parts[0]
    assert "22222/85" in dr_parts[1]


def test_excludes_self_loop_communicated_and_future_targets():
    appno_index = {
        "100/99": [
            _cand(1, date_decision=dt.date(2000, 1, 1)),  # self
            _cand(2, date_decision=dt.date(2001, 1, 1), kind="communicated"),
            _cand(3, date_decision=dt.date(2020, 1, 1)),  # future
        ]
    }
    parsed = mod.parse_scl_entry("Foo v. Bar, no. 100/99, 2005")
    assert mod.choose_target_for_entry(parsed, 1, dt.date(2010, 1, 1), appno_index) is None


def test_decision_cue_prefers_decision_over_judgment():
    dec = _cand(10, date_decision=dt.date(2001, 9, 13), kind="decision")
    jud = _cand(11, date_decision=dt.date(2005, 6, 30), kind="judgment", branch="GRANDCHAMBER")
    appno_index = {"45036/98": [dec, jud]}

    p_dec = mod.parse_scl_entry("Bosphorus v. Ireland (dec.), no. 45036/98, 13 September 2001")
    chosen, ap, rule = mod.choose_target_for_entry(p_dec, 999, dt.date(2020, 1, 1), appno_index)
    assert chosen.case_id == 10
    assert ap == "45036/98"
    assert rule.startswith("scl_decision_cue")

    p_jud = mod.parse_scl_entry("Bosphorus v. Ireland [GC], no. 45036/98, ECHR 2005-VI")
    chosen2, _ap2, rule2 = mod.choose_target_for_entry(p_jud, 999, dt.date(2020, 1, 1), appno_index)
    assert chosen2.case_id == 11
    assert rule2.startswith("scl_judgment")


def test_tie_breaks_gc_principal_and_ecli_primary_appno():
    # Grand Chamber vs Chamber
    chamber = _cand(20, date_decision=dt.date(2003, 3, 12), branch="CHAMBER")
    gc = _cand(21, date_decision=dt.date(2005, 5, 12), branch="GRANDCHAMBER")
    res = mod.choose_target_for_entry(
        mod.parse_scl_entry("Öcalan v. Turkey [GC], no. 46221/99"),
        999,
        dt.date(2020, 1, 1),
        {"46221/99": [chamber, gc]},
    )
    assert res[0].case_id == 21
    assert "_gc" in res[2]

    # Principal vs just satisfaction follow-up
    principal = _cand(30, date_decision=dt.date(1993, 6, 24), secondary_kind=None)
    js = _cand(31, date_decision=dt.date(1995, 10, 31), secondary_kind="just_satisfaction")
    res_p = mod.choose_target_for_entry(
        mod.parse_scl_entry("Papamichalopoulos v. Greece, no. 14556/89"),
        999,
        dt.date(2020, 1, 1),
        {"14556/89": [js, principal]},
    )
    assert res_p[0].case_id == 30
    assert "_principal" in res_p[2]

    res_js = mod.choose_target_for_entry(
        mod.parse_scl_entry("Papamichalopoulos v. Greece (Article 50), no. 14556/89"),
        999,
        dt.date(2020, 1, 1),
        {"14556/89": [js, principal]},
    )
    assert res_js[0].case_id == 31
    assert "_just_satisfaction" in res_js[2]

    # Same-day companion cases disambiguated by ECLI primary appno
    t_uk = _cand(40, ecli="ECLI:CE:ECHR:1999:1216JUD002472494", date_decision=dt.date(1999, 12, 16))
    v_uk = _cand(41, ecli="ECLI:CE:ECHR:1999:1216JUD002488894", date_decision=dt.date(1999, 12, 16))
    res_v = mod.choose_target_for_entry(
        mod.parse_scl_entry("V. v. the United Kingdom [GC], no. 24888/94, ECHR 1999-IX"),
        999,
        dt.date(2020, 1, 1),
        {"24888/94": [t_uk, v_uk]},
    )
    assert res_v[0].case_id == 41
    assert "_ecli_appno" in res_v[2]


def test_classify_secondary_judgment():
    assert mod.classify_secondary_judgment("CASE OF FOO v. BAR (JUST SATISFACTION)", None) == "just_satisfaction"
    assert mod.classify_secondary_judgment("CASE OF FOO v. BAR", "Pecuniary damage - award") == "just_satisfaction"
    assert (
        mod.classify_secondary_judgment(
            "CASE OF FOO v. BAR", "Violation of Art. 6-1;Pecuniary damage - award"
        )
        is None
    )


def test_confidence_for_rule_matches_backfill_tiers():
    assert mod.confidence_for_rule("scl_judgment") == 0.95
    assert mod.confidence_for_rule("scl_judgment_exact_date") == 0.95
    assert mod.confidence_for_rule("scl_judgment_year") == 0.90
    assert mod.confidence_for_rule("scl_decision_no_judgment") == 0.85
    assert mod.confidence_for_rule("scl_judgment_earliest") == 0.80


def test_extract_batch_and_artifact_roundtrip(tmp_path):
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self._rows = []

        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            if "FROM cle_v2.cases c" in sql and "d.scl" in sql:
                self._rows = [
                    (
                        100,
                        "ECLI:CE:ECHR:2026:1101JUD009999924",
                        "001-100",
                        dt.date(2026, 11, 1),
                        "Öcalan v. Turkey [GC], no. 46221/99, ECHR 2005-IV; "
                        "Bosphorus v. Ireland (dec.), no. 45036/98, 13 September 2001",
                    ),
                ]
            elif "WITH matched_cases AS" in sql:
                self._rows = [
                    (
                        200,
                        "ECLI:CE:ECHR:2005:0512JUD004622199",
                        "001-69022",
                        dt.date(2005, 5, 12),
                        True,
                        False,
                        False,
                        True,
                        "CASE OF ÖCALAN v. TURKEY",
                        "Violation of Art. 3",
                        ["46221/99"],
                        ["46221/99"],
                    ),
                    (
                        201,
                        "ECLI:CE:ECHR:2001:0913DEC004503698",
                        "001-22014",
                        dt.date(2001, 9, 13),
                        False,
                        True,
                        False,
                        False,
                        "BOSPHORUS v. IRELAND",
                        "Admissible",
                        ["45036/98"],
                        [],
                    ),
                ]
            else:
                raise AssertionError(f"unexpected SQL: {sql}")

        def fetchall(self):
            return self._rows

    cursor = FakeCursor()
    records = mod.extract_batch(cursor, [100])
    assert len(records) == 2

    out = tmp_path / "echr_edge_v2.jsonl"
    with mod.open_writers(str(out)) as writer:
        writer.write(records)

    loaded = list(read_jsonl(str(out)))
    assert len(loaded) == 2
    by_target = {r.target.ecli: r for r in loaded}

    r_ocalan = by_target["ECLI:CE:ECHR:2005:0512JUD004622199"]
    assert r_ocalan.source.ecli == "ECLI:CE:ECHR:2026:1101JUD009999924"
    assert r_ocalan.source_dataset == "echr_edge_v2"
    assert r_ocalan.relation_type == "cites"
    assert r_ocalan.target_ref_raw == "46221/99"
    assert r_ocalan.target_ref_scheme == "echr_appno"
    assert r_ocalan.match_method == "appno/scl_judgment"
    assert r_ocalan.confidence == 0.95
    assert len(r_ocalan.mentions) == 1
    assert r_ocalan.mentions[0].text_field == "metadata"
    assert "46221/99" in r_ocalan.mentions[0].raw_text

    r_bosph = by_target["ECLI:CE:ECHR:2001:0913DEC004503698"]
    assert r_bosph.match_method == "appno/scl_decision_cue"
    assert r_bosph.confidence == 0.95
