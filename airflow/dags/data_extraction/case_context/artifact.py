"""
The case-context artifact: what the outcome and status extractors write and
data_loading/outcome_loader.py reads (roadmap R5.1, R5.2).

One JSON object per line, cases named by natural keys only (ECLI, else CELEX,
else item_id; linking.artifact.CaseKey), never by database ids, so the same
file loads into db-dev and, after verification, into production, exactly like
the link artifacts.

Outcome (a case_outcome row):

    {"kind": "outcome",
     "case": {"ecli": "ECLI:EU:C:2013:720"},
     "scope": "overall",                  # overall | article
     "article": null,                     # ECtHR: '3', '8', 'P1-1' (scope article only)
     "outcome": "unfounded",              # OUTCOMES
     "raw_value": "Action for annulment - unfounded",   # the source value, untouched
     "confidence": 0.99,
     "rule": "proc_type_suffix",          # which extractor rule; not stored
     "source_dataset": "cjeu_proc_type",
     "extractor_version": "cjeu_outcomes/1.0.0"}

Status (a case_status row):

    {"kind": "status",
     "case": {"ecli": "ECLI:CE:ECHR:2014:0626JUD007139812"},
     "status": "referred_to_grand_chamber",   # STATUSES
     "status_date": null,                     # ISO date or null
     "related": {"ecli": "ECLI:CE:ECHR:2015:0408JUD007139812"},   # or null
     "raw_value": "...", "confidence": 0.9, "rule": "...",
     "source_dataset": "echr_status", "extractor_version": "case_status/1.0.0"}

The files are written with linking.artifact.ArtifactWriter (sorted per batch,
.tmp + rename), so they hash the same for the same input.
"""

import json
from dataclasses import dataclass
from datetime import date
from typing import Iterator, Optional, Union

from data_extraction.linking.artifact import ArtifactError, CaseKey

OUTCOME_DATASETS = ("cjeu_proc_type", "echr_conclusion", "rs_dictum")
STATUS_DATASETS = ("echr_status", "cjeu_appeal_status", "rs_appeal_status")
DATASETS = OUTCOME_DATASETS + STATUS_DATASETS

SCOPES = ("overall", "article")
OUTCOMES = (
    # CJEU (issue #83: the suffix of Cellar's type_procedure)
    "successful",
    "unfounded",
    "inadmissible",
    "decision_unnecessary",
    "amicable_settlement",
    "agreement_compatible",
    "agreement_incompatible",
    "interlocutory",
    # ECtHR, per article; overall inadmissible (above) and struck_out
    "violation",
    "no_violation",
    "struck_out",
    # Dutch dictum
    "dismissed",  # the (cassation) appeal or objection is rejected; the decision stands
    "upheld",  # the appeal or objection is well founded ("gegrond")
    "quashed",  # the decision under appeal is set aside ("vernietigt")
)
STATUSES = ("struck_out", "referred_to_grand_chamber", "final", "overturned")


def _case(value, name):
    key = CaseKey.from_dict(value)
    if key is None:
        raise ArtifactError(f"record needs {name}")
    return key


def _check_common(record):
    if record.source_dataset not in DATASETS:
        raise ArtifactError(f"unknown source_dataset {record.source_dataset!r}")
    if not record.extractor_version:
        raise ArtifactError("record needs extractor_version")
    if record.confidence is not None and not 0 <= record.confidence <= 1:
        raise ArtifactError(f"confidence must be between 0 and 1, got {record.confidence}")


@dataclass(frozen=True)
class OutcomeRecord:
    case: CaseKey
    outcome: str
    source_dataset: str
    extractor_version: str
    scope: str = "overall"
    article: Optional[str] = None
    raw_value: Optional[str] = None
    confidence: Optional[float] = None
    rule: Optional[str] = None

    def validate(self):
        _check_common(self)
        if self.source_dataset not in OUTCOME_DATASETS:
            raise ArtifactError(f"{self.source_dataset!r} is not an outcome dataset")
        if self.outcome not in OUTCOMES:
            raise ArtifactError(f"unknown outcome {self.outcome!r}")
        if self.scope not in SCOPES:
            raise ArtifactError(f"unknown scope {self.scope!r}")
        if (self.scope == "article") != bool(self.article):
            raise ArtifactError("scope 'article' goes with an article, 'overall' without")
        return self

    @classmethod
    def from_dict(cls, value):
        return cls(
            case=_case(value.get("case"), "case"),
            outcome=value.get("outcome"),
            source_dataset=value.get("source_dataset"),
            extractor_version=value.get("extractor_version"),
            scope=value.get("scope") or "overall",
            article=value.get("article") or None,
            raw_value=value.get("raw_value"),
            confidence=value.get("confidence"),
            rule=value.get("rule"),
        ).validate()

    def to_dict(self):
        out = {
            "kind": "outcome",
            "case": self.case.to_dict(),
            "scope": self.scope,
            "article": self.article,
            "outcome": self.outcome,
            "source_dataset": self.source_dataset,
            "extractor_version": self.extractor_version,
        }
        for name in ("raw_value", "confidence", "rule"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        return out


@dataclass(frozen=True)
class StatusRecord:
    case: CaseKey
    status: str
    source_dataset: str
    extractor_version: str
    status_date: Optional[date] = None
    related: Optional[CaseKey] = None
    raw_value: Optional[str] = None
    confidence: Optional[float] = None
    rule: Optional[str] = None

    def validate(self):
        _check_common(self)
        if self.source_dataset not in STATUS_DATASETS:
            raise ArtifactError(f"{self.source_dataset!r} is not a status dataset")
        if self.status not in STATUSES:
            raise ArtifactError(f"unknown status {self.status!r}")
        if self.related is not None and self.related == self.case:
            raise ArtifactError("a case is not its own related case")
        return self

    @classmethod
    def from_dict(cls, value):
        raw_date = value.get("status_date")
        try:
            status_date = date.fromisoformat(raw_date) if raw_date else None
        except (TypeError, ValueError):
            raise ArtifactError(f"bad status_date {raw_date!r}") from None
        return cls(
            case=_case(value.get("case"), "case"),
            status=value.get("status"),
            source_dataset=value.get("source_dataset"),
            extractor_version=value.get("extractor_version"),
            status_date=status_date,
            related=CaseKey.from_dict(value.get("related")),
            raw_value=value.get("raw_value"),
            confidence=value.get("confidence"),
            rule=value.get("rule"),
        ).validate()

    def to_dict(self):
        out = {
            "kind": "status",
            "case": self.case.to_dict(),
            "status": self.status,
            "status_date": self.status_date.isoformat() if self.status_date else None,
            "related": self.related.to_dict() if self.related else None,
            "source_dataset": self.source_dataset,
            "extractor_version": self.extractor_version,
        }
        for name in ("raw_value", "confidence", "rule"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        return out


Record = Union[OutcomeRecord, StatusRecord]


def record_from_dict(value) -> Record:
    if not isinstance(value, dict):
        raise ArtifactError("record must be an object")
    kind = value.get("kind")
    if kind == "outcome":
        return OutcomeRecord.from_dict(value)
    if kind == "status":
        return StatusRecord.from_dict(value)
    raise ArtifactError(f"unknown record kind {kind!r}")


def read_jsonl(path) -> Iterator[Record]:
    """Read and validate records; ArtifactError names the bad line."""
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield record_from_dict(json.loads(line))
            except (ArtifactError, json.JSONDecodeError) as exc:
                raise ArtifactError(f"{path}:{number}: {exc}") from None


def case_key(ecli=None, celex=None, item_id=None) -> Optional[CaseKey]:
    """The natural key of a case: ECLI, else CELEX, else item_id."""
    if ecli:
        return CaseKey(ecli=ecli)
    if celex:
        return CaseKey(celex=celex)
    if item_id:
        return CaseKey(item_id=item_id)
    return None
