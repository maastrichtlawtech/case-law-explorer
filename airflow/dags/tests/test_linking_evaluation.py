from collections import Counter
from fractions import Fraction

import pytest
from tests.linking_evaluation import (
    endpoint_matches,
    load_fixture,
    normalize,
    score,
    validate_fixture,
)

GOLD_SOURCES = {
    ("ECLI:NL:RVS:2017:1098", "preliminary_reference"),
    ("ECLI:NL:RVS:2020:423", "cites"),
    ("ECLI:NL:HR:2020:593", "cites"),
    ("ECLI:NL:HR:2022:637", "cites"),
    ("ECLI:CE:ECHR:2020:0625JUD005227316", "cites"),
    ("ECLI:NL:RVS:2012:BW3078", "preliminary_reference"),
    ("ECLI:NL:RVS:2012:BW3077", "preliminary_reference"),
    ("ECLI:NL:RVS:2012:BW3076", "preliminary_reference"),
    ("ECLI:NL:RVS:2013:2423", "cites"),
    ("ECLI:NL:RVS:2013:2424", "cites"),
    ("ECLI:NL:RVS:2013:2422", "cites"),
    ("ECLI:NL:RVS:2015:2170", "cites"),
    ("ECLI:NL:RVS:2015:4062", "cites"),
    ("ECLI:CE:ECHR:2014:0626JUD007139812", "cites"),
    ("ECLI:CE:ECHR:2017:1219DEC002141717", "cites"),
    ("ECLI:CE:ECHR:2020:1117JUD000088919", "cites"),
    ("62012CC0199", "cites"),
}


@pytest.fixture(scope="module")
def fixture():
    return load_fixture()


def _entry(entry_id, category, label, source, target, relation="cites", **extra):
    entry = {
        "id": entry_id,
        "category": category,
        "label": label,
        "source": source,
        "target": target if label == "positive" else None,
        "relation_type": relation,
        "text_field": "fulltext",
        "text_owner": "source",
        "text": extra.pop("text", None),
        "requires_db": True,
        "document_level": True,
        "tags": extra.pop("tags", []),
        "provenance": "synthetic",
        "reason": extra.pop("reason", "synthetic negative" if label == "negative" else None),
    }
    if label == "negative":
        entry["must_not_link"] = [target]
    entry.update(extra)
    return entry


def test_fixture_validates(fixture):
    assert validate_fixture(fixture) == []
    assert fixture["schema_version"] == 1


def test_fixture_ids_are_unique(fixture):
    ids = Counter(e["id"] for e in fixture["entries"])
    assert [i for i, n in ids.items() if n > 1] == []


def test_seventeen_gold_citations_present(fixture):
    gold = [e for e in fixture["entries"] if e["category"] == "goldset_citation"]
    assert len(gold) == 17
    assert all(e["label"] == "positive" for e in gold)
    found = {
        (e["source"].get("ecli") or e["source"].get("celex"), e["relation_type"]) for e in gold
    }
    assert found == GOLD_SOURCES
    targets = {e["target"].get("ecli") for e in gold}
    assert targets == {
        "ECLI:EU:C:2019:189",
        "ECLI:EU:C:2013:720",
        "ECLI:CE:ECHR:2004:0622DEC001734103",
    }


def test_gold_non_citations_are_negatives(fixture):
    negatives = [e for e in fixture["entries"] if e["category"] == "goldset_non_citation"]
    assert sorted(e["source"]["ecli"] for e in negatives) == [
        "ECLI:CE:ECHR:2016:0621JUD007613612",
        "ECLI:CE:ECHR:2017:0207DEC004238713",
        "ECLI:CE:ECHR:2020:1222JUD004393618",
    ]
    assert all(e["label"] == "negative" and e["direction"] == "either" for e in negatives)


def test_every_negative_has_a_reason_and_forbidden_target(fixture):
    for entry in fixture["entries"]:
        if entry["label"] == "negative":
            assert entry["reason"], entry["id"]
            assert entry["must_not_link"], entry["id"]


def test_summary_only_citation_points_at_summary(fixture):
    entry = next(e for e in fixture["entries"] if e["id"] == "gold-04")
    assert entry["source"]["ecli"] == "ECLI:NL:HR:2022:637"
    assert entry["text_field"] == "summary"


def test_positive_predictions_never_trip_a_negative(fixture):
    predictions = [
        {"source": e["source"], "target": e["target"], "relation_type": e["relation_type"]}
        for e in fixture["entries"]
        if e["label"] == "positive"
    ]
    for mode in ("document", "excerpt"):
        result = score(predictions, fixture, mode=mode)
        assert result["overall"]["fp"] == 0
        assert result["overall"]["fn"] == 0
        assert result["misses"] == []


def test_normalize_case_number_variants():
    assert normalize("case_number", "C‑199/12") == "C-199/12"
    assert normalize("case_number", "C 199/12") == "C-199/12"
    assert normalize("case_number", "C ‑ 520/18") == "C-520/18"
    assert normalize("case_number", "C-04/19") == "C-4/19"
    assert normalize("case_number", "C-354/20 PPU") == "C-354/20"
    assert normalize("ecli", "EU:C:2013:720") == "ECLI:EU:C:2013:720"


def test_endpoint_matching_uses_strongest_shared_identifier():
    judgment = {"celex": "62012CJ0199", "case_number": "C-199/12"}
    opinion = {"celex": "62012CC0199", "case_number": "C-199/12"}
    assert not endpoint_matches(opinion, judgment)
    assert endpoint_matches({"case_number": "C 199/12"}, judgment)
    assert endpoint_matches("62012CJ0199", judgment)
    assert endpoint_matches("anything", None)


def test_score_counts_on_synthetic_predictions():
    fixture = {
        "schema_version": 1,
        "entries": [
            _entry("p1", "a", "positive", {"ecli": "ECLI:NL:X:1"}, {"celex": "62012CJ0199"}),
            _entry("p2", "a", "positive", {"ecli": "ECLI:NL:X:2"}, {"ecli": "EU:C:2019:189"}),
            _entry(
                "p3",
                "b",
                "positive",
                {"ecli": "ECLI:NL:X:3"},
                {"case_number": "C-684/16"},
                tags=["t"],
            ),
            _entry("n1", "b", "negative", {"ecli": "ECLI:NL:X:3"}, {"celex": "62012CC0199"}),
            _entry(
                "n2",
                "c",
                "negative",
                None,
                {"celex": "62000CJ0153"},
                relation=["preliminary_reference", "national_follow_up"],
                tags=["t"],
            ),
            _entry(
                "n3",
                "c",
                "negative",
                {"ecli": "ECLI:CE:ECHR:1"},
                {"ecli": "ECLI:EU:C:2019:189"},
                direction="either",
            ),
        ],
    }
    assert validate_fixture(fixture) == []
    predictions = [
        {"source": "ECLI:NL:X:1", "target": "62012CJ0199", "relation_type": "cites"},  # p1 TP
        {"source": "ECLI:NL:X:2", "target": "62017CJ0221", "relation_type": "cites"},  # unjudged
        {"source": "ECLI:NL:X:3", "target": "C‑684/16", "relation_type": "cites"},  # p3 TP
        {"source": "ECLI:NL:X:3", "target": "62012CC0199", "relation_type": "cites"},  # n1 FP
        {"source": "ECLI:NL:Y:9", "target": "62000CJ0153", "relation_type": "cites"},  # not n2
        {"source": "ECLI:EU:C:2019:189", "target": "ECLI:CE:ECHR:1", "relation_type": "cites"},
    ]
    result = score(predictions, fixture)

    overall = result["overall"]
    assert (overall["tp"], overall["fp"], overall["fn"], overall["tn"]) == (2, 2, 1, 1)
    assert overall["precision"] == Fraction(1, 2)
    assert overall["recall"] == Fraction(2, 3)

    a, b, c = (result["by_category"][k] for k in "abc")
    assert (a["tp"], a["fp"], a["fn"], a["tn"]) == (1, 0, 1, 0)
    assert a["precision"] == Fraction(1, 1) and a["recall"] == Fraction(1, 2)
    assert (b["tp"], b["fp"], b["fn"], b["tn"]) == (1, 1, 0, 0)
    assert b["precision"] == Fraction(1, 2) and b["recall"] == Fraction(1, 1)
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (0, 1, 0, 1)
    assert c["precision"] == Fraction(0, 1) and c["recall"] is None

    assert result["by_tag"]["t"]["tp"] == 1 and result["by_tag"]["t"]["tn"] == 1
    assert {(m["id"], m["kind"]) for m in result["misses"]} == {
        ("p2", "false_negative"),
        ("n1", "false_positive"),
        ("n3", "false_positive"),
    }
    assert result["unjudged"] == [predictions[1]]


def test_wildcard_negative_catches_referral_from_any_source():
    fixture = {
        "schema_version": 1,
        "entries": [
            _entry(
                "n",
                "c",
                "negative",
                None,
                {"celex": "62000CJ0153"},
                relation=["preliminary_reference"],
            )
        ],
    }
    result = score(
        [
            {
                "source": "ECLI:NL:RBX:1",
                "target": "62000CJ0153",
                "relation_type": "preliminary_reference",
            }
        ],
        fixture,
    )
    assert result["overall"]["fp"] == 1
    assert result["overall"]["precision"] == Fraction(0, 1)
    assert result["overall"]["recall"] is None


def test_excerpt_only_entries_are_skipped_in_document_mode():
    entry = _entry(
        "x",
        "a",
        "negative",
        {"case_id": 1},
        {"celex": "62005CC0013"},
        text="judgment of 11 July 2006, C-13/05",
        document_level=False,
    )
    fixture = {"schema_version": 1, "entries": [entry]}
    prediction = [{"source": {"case_id": 1}, "target": "62005CC0013", "relation_type": "cites"}]
    assert score(prediction, fixture, mode="document")["overall"]["entries"] == 0
    assert score(prediction, fixture, mode="excerpt")["overall"]["fp"] == 1


def test_validate_reports_problems():
    bad = _entry("n", "c", "negative", {"ecli": "ECLI:NL:X:1"}, {"celex": "1"}, reason="")
    dup = _entry("n", "c", "positive", {"ecli": "ECLI:NL:X:1"}, {"celex": "62012CJ0199"})
    errors = validate_fixture({"schema_version": 1, "entries": [bad, dup, {"id": "z"}]})
    assert "n: a negative needs a reason" in errors
    assert "n: duplicate id" in errors
    assert any(e.startswith("z: missing") for e in errors)
