"""
Scorer for the cross-dataset linking evaluation set (roadmap R0.3).

The fixture (fixtures/linking_evaluation.json) lists positive links that an
extractor must find and negative pairs it must not produce. ``score`` takes the
links an extractor predicted and returns exact TP/FP/FN counts, precision and
recall (as ``fractions.Fraction``) per category, per tag and overall, plus the
list of misses. See fixtures/README_linking_evaluation.md for the categories.

A prediction is a mapping with ``source``, ``target`` and ``relation_type``.
Endpoints are mappings of identifiers (``ecli``, ``celex``, ``case_id``,
``case_number``, ``appno``) or a bare identifier string, whose kind is inferred.
"""

import json
import re
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "linking_evaluation.json"

# A predicted endpoint matches a fixture endpoint on the first identifier both carry.
ID_ORDER = ("ecli", "celex", "case_id", "case_number", "appno")
LABELS = ("positive", "negative")
TEXT_FIELDS = ("fulltext", "summary", "national_judgement_xml", "metadata")
MODES = ("document", "excerpt")
REQUIRED_FIELDS = (
    "id",
    "category",
    "label",
    "source",
    "target",
    "relation_type",
    "text_field",
    "text_owner",
    "text",
    "requires_db",
    "document_level",
    "tags",
    "provenance",
)

_HYPHENS = re.compile(r"[‐‑‒–—−­]")
_CASE_NUMBER = re.compile(r"^([CTF])\s*-?\s*0*(\d{1,4})/(\d{2})(?:\s*(?:PPU|P|R|DEP|REC))?$", re.I)
_CELEX = re.compile(r"^[0-9E][0-9]{4}[A-Z]{1,2}[0-9]{4}")
_APPNO = re.compile(r"^\d{1,6}/\d{2}$")


def load_fixture(path=FIXTURE_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def normalize(kind, value):
    """Normalize one identifier so that spelling variants compare equal."""
    if value is None:
        return None
    text = _HYPHENS.sub("-", str(value)).strip()
    if kind == "ecli":
        text = text.upper()
        return text if text.startswith("ECLI:") else "ECLI:" + text
    if kind == "case_number":
        match = _CASE_NUMBER.match(text)
        if match:
            return f"{match.group(1).upper()}-{int(match.group(2))}/{match.group(3)}"
        return re.sub(r"\s+", "", text).upper()
    if kind == "case_id":
        return str(int(text))
    return text.upper()


def _infer_kind(value):
    text = _HYPHENS.sub("-", str(value)).strip()
    upper = text.upper()
    if upper.startswith("ECLI:") or re.match(r"^(EU|CE|NL):", upper):
        return "ecli"
    if _CELEX.match(upper):
        return "celex"
    if _CASE_NUMBER.match(text):
        return "case_number"
    if _APPNO.match(text):
        return "appno"
    if text.isdigit():
        return "case_id"
    raise ValueError(f"cannot infer the identifier kind of {value!r}")


def as_endpoint(value):
    """Turn a prediction endpoint (mapping or bare identifier) into an identifier mapping."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: value[k] for k in ID_ORDER if value.get(k) not in (None, "")}
    return {_infer_kind(value): value}


def endpoint_matches(predicted, reference):
    """True when ``predicted`` names the same document as fixture endpoint ``reference``.

    A ``None`` reference is a wildcard (a negative that forbids the link from any source).
    """
    if reference is None:
        return True
    predicted = as_endpoint(predicted) or {}
    reference = as_endpoint(reference)
    for kind in ID_ORDER:
        if kind in predicted and kind in reference:
            return normalize(kind, predicted[kind]) == normalize(kind, reference[kind])
    return False


def _relation_matches(expected, predicted):
    allowed = expected if isinstance(expected, list) else [expected]
    return predicted in allowed


def _link_matches(source, target, relation_type, prediction):
    if not _relation_matches(relation_type, prediction.get("relation_type")):
        return False
    return endpoint_matches(prediction.get("source"), source) and endpoint_matches(
        prediction.get("target"), target
    )


def entry_matches(entry, prediction):
    """True when ``prediction`` is the expected link (positive) or a forbidden one (negative)."""
    if entry["label"] == "positive":
        return _link_matches(entry["source"], entry["target"], entry["relation_type"], prediction)
    for forbidden in entry["must_not_link"]:
        if _link_matches(entry["source"], forbidden, entry["relation_type"], prediction):
            return True
        if entry.get("direction") == "either" and _link_matches(
            forbidden, entry["source"], entry["relation_type"], prediction
        ):
            return True
    return False


def _common_problems(entry):
    checks = [
        (entry["label"] in LABELS, f"label must be one of {LABELS}"),
        (entry["text_field"] in TEXT_FIELDS, f"text_field must be one of {TEXT_FIELDS}"),
        (entry["text_owner"] in ("source", "target"), "text_owner must be source or target"),
        (bool(entry["provenance"]), "provenance is empty"),
        (
            entry["text"] is not None or entry["requires_db"],
            "no excerpt, so requires_db must be true",
        ),
        (entry["text"] is None or bool(entry["text"].strip()), "empty excerpt"),
        (
            entry["document_level"] or entry["text"] is not None,
            "an excerpt-only entry needs an excerpt",
        ),
    ]
    return [message for ok, message in checks if not ok]


def _label_problems(entry):
    if entry["label"] == "positive":
        checks = [
            (
                bool(as_endpoint(entry["source"]) and as_endpoint(entry["target"])),
                "a positive needs identified source and target",
            ),
            (isinstance(entry["relation_type"], str), "a positive has exactly one relation_type"),
        ]
    else:
        forbidden = entry.get("must_not_link") or []
        checks = [
            (entry["target"] is None, "a negative has target null"),
            (bool(entry.get("reason")), "a negative needs a reason"),
            (
                bool(forbidden) and all(as_endpoint(item) for item in forbidden),
                "a negative needs identified must_not_link targets",
            ),
        ]
    return [message for ok, message in checks if not ok]


def validate_fixture(fixture):
    """Return a list of problems (empty when the fixture is well formed)."""
    errors = []
    if not isinstance(fixture.get("schema_version"), int):
        errors.append("schema_version must be an integer")
    seen = set()
    for index, entry in enumerate(fixture.get("entries", [])):
        name = entry.get("id", f"#{index}")
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            errors.append(f"{name}: missing {', '.join(missing)}")
            continue
        if name in seen:
            errors.append(f"{name}: duplicate id")
        seen.add(name)
        problems = _common_problems(entry) + _label_problems(entry)
        errors.extend(f"{name}: {problem}" for problem in problems)
    return errors


def _ratio(numerator, denominator):
    return Fraction(numerator, denominator) if denominator else None


def _bucket():
    return {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "entries": 0}


def _finish(bucket):
    bucket["precision"] = _ratio(bucket["tp"], bucket["tp"] + bucket["fp"])
    bucket["recall"] = _ratio(bucket["tp"], bucket["tp"] + bucket["fn"])
    return bucket


def select_entries(fixture, mode="document"):
    """Entries scored in ``mode``: 'document' (whole-document runs) or 'excerpt' (text tests)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode == "document":
        return [e for e in fixture["entries"] if e["document_level"]]
    return [e for e in fixture["entries"] if e["text"] is not None]


def score(predictions, fixture=None, mode="document", categories=None):
    """Score predicted links against the fixture.

    Positive entry: TP when a matching prediction exists, else FN.
    Negative entry: FP when a forbidden link was predicted, else TN.
    Predictions from a fixture source that no entry judges are returned as
    ``unjudged`` (the fixture is not exhaustive, so they are not counted as FP).
    """
    fixture = load_fixture() if fixture is None else fixture
    predictions = list(predictions)
    entries = select_entries(fixture, mode)
    if categories is not None:
        entries = [e for e in entries if e["category"] in categories]

    overall = _bucket()
    by_category = defaultdict(_bucket)
    by_tag = defaultdict(_bucket)
    misses = []
    judged = set()

    for entry in entries:
        matched = [i for i, p in enumerate(predictions) if entry_matches(entry, p)]
        judged.update(matched)
        if entry["label"] == "positive":
            outcome = "tp" if matched else "fn"
        else:
            outcome = "fp" if matched else "tn"
        for bucket in [overall, by_category[entry["category"]]] + [
            by_tag[tag] for tag in entry["tags"]
        ]:
            bucket[outcome] += 1
            bucket["entries"] += 1
        if outcome in ("fn", "fp"):
            misses.append(
                {
                    "id": entry["id"],
                    "category": entry["category"],
                    "kind": "false_negative" if outcome == "fn" else "false_positive",
                    "predictions": [predictions[i] for i in matched],
                }
            )

    sources = [e["source"] for e in entries if e["source"] is not None]
    unjudged = [
        p
        for i, p in enumerate(predictions)
        if i not in judged and any(endpoint_matches(p.get("source"), s) for s in sources)
    ]
    return {
        "mode": mode,
        "overall": _finish(overall),
        "by_category": {k: _finish(v) for k, v in sorted(by_category.items())},
        "by_tag": {k: _finish(v) for k, v in sorted(by_tag.items())},
        "misses": misses,
        "unjudged": unjudged,
    }
