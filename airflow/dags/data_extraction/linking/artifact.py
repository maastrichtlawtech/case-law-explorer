"""
The link artifact: what an extractor writes and the link loader reads.

One JSON object per line. Cases are named by natural keys only (ECLI, else
CELEX, else item_id), never by database ids, so the same file loads into
db-dev and, after verification, into production (cjeu-migration
docs/LINKING_DESIGN.md, "Data path").

    {"source": {"ecli": "ECLI:NL:RVS:2020:423"},
     "target": {"ecli": "ECLI:EU:C:2019:189"},        # or null when unresolved
     "target_ref_raw": "C-221/17",                     # normalised; optional
     "target_ref_scheme": "cjeu_case_number",          # required with target_ref_raw
     "relation_type": "cites",
     "source_dataset": "rs_text_cjeu_casenum",
     "extractor_version": "rs_text/1.0.0",
     "match_method": "case_number",
     "confidence": 0.95,
     "mentions": [{"text_field": "fulltext", "language": "nl",
                   "text_source": "RECHTSPRAAK", "char_start": 10234,
                   "char_end": 10242, "raw_text": "C-221/17",
                   "context": "...", "section": null, "segment_hash": null}]}
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Iterator, Optional

CASE_KEYS = ("ecli", "celex", "item_id")
REF_SCHEMES = ("cjeu_case_number", "echr_appno", "nl_zaaknummer", "ljn", "name_date")
TEXT_FIELDS = ("fulltext", "summary", "national_judgement_xml", "metadata")


class ArtifactError(ValueError):
    """A link record that must not be loaded."""


@dataclass(frozen=True)
class CaseKey:
    ecli: Optional[str] = None
    celex: Optional[str] = None
    item_id: Optional[str] = None

    @classmethod
    def from_dict(cls, value):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ArtifactError(f"case key must be an object, got {value!r}")
        unknown = set(value) - set(CASE_KEYS)
        if unknown:
            raise ArtifactError(f"unknown case key field(s): {sorted(unknown)}")
        key = cls(**{k: value.get(k) or None for k in CASE_KEYS})
        if not (key.ecli or key.celex or key.item_id):
            raise ArtifactError("case key needs an ecli, celex or item_id")
        return key

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass(frozen=True)
class Mention:
    text_field: str
    raw_text: str
    language: Optional[str] = None
    text_source: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    context: Optional[str] = None
    section: Optional[str] = None
    segment_hash: Optional[str] = None

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError(f"mention must be an object, got {value!r}")
        try:
            mention = cls(**value)
        except TypeError as exc:
            raise ArtifactError(f"bad mention {value!r}: {exc}") from None
        if mention.text_field not in TEXT_FIELDS:
            raise ArtifactError(f"unknown text_field {mention.text_field!r}")
        if not mention.raw_text:
            raise ArtifactError("mention needs raw_text")
        if (mention.char_start is None) != (mention.char_end is None):
            raise ArtifactError("char_start and char_end go together")
        if mention.char_start is not None and not 0 <= mention.char_start <= mention.char_end:
            raise ArtifactError(f"bad offsets {mention.char_start}..{mention.char_end}")
        return mention


@dataclass(frozen=True)
class LinkRecord:
    source: CaseKey
    relation_type: str
    source_dataset: str
    extractor_version: str
    target: Optional[CaseKey] = None
    target_ref_raw: Optional[str] = None
    target_ref_scheme: Optional[str] = None
    match_method: Optional[str] = None
    confidence: Optional[float] = None
    mentions: tuple = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError("record must be an object")
        for required in ("source", "relation_type", "source_dataset", "extractor_version"):
            if not value.get(required):
                raise ArtifactError(f"record needs {required}")
        record = cls(
            source=CaseKey.from_dict(value["source"]),
            target=CaseKey.from_dict(value.get("target")),
            target_ref_raw=value.get("target_ref_raw") or None,
            target_ref_scheme=value.get("target_ref_scheme") or None,
            relation_type=value["relation_type"],
            source_dataset=value["source_dataset"],
            extractor_version=value["extractor_version"],
            match_method=value.get("match_method") or None,
            confidence=value.get("confidence"),
            mentions=tuple(Mention.from_dict(m) for m in value.get("mentions") or ()),
        )
        record.validate()
        return record

    def validate(self):
        if self.target is None and self.target_ref_raw is None:
            raise ArtifactError("record needs a target or a target_ref_raw")
        if self.target_ref_raw is not None and self.target_ref_scheme not in REF_SCHEMES:
            raise ArtifactError(
                f"target_ref_raw needs a known scheme, got {self.target_ref_scheme!r}"
            )
        if self.target_ref_raw is None and self.target_ref_scheme is not None:
            raise ArtifactError("target_ref_scheme without target_ref_raw")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ArtifactError(f"confidence must be between 0 and 1, got {self.confidence}")
        if self.target is not None and self.target == self.source:
            raise ArtifactError("a case does not link to itself")

    def to_dict(self):
        out = {
            "source": self.source.to_dict(),
            "target": self.target.to_dict() if self.target else None,
            "relation_type": self.relation_type,
            "source_dataset": self.source_dataset,
            "extractor_version": self.extractor_version,
        }
        for name in ("target_ref_raw", "target_ref_scheme", "match_method", "confidence"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if self.mentions:
            out["mentions"] = [
                {k: v for k, v in asdict(m).items() if v is not None} for m in self.mentions
            ]
        return out


def write_jsonl(records: Iterable[LinkRecord], path) -> int:
    """Write records, one per line, sorted for a stable hash; returns the count."""
    lines = sorted(json.dumps(r.to_dict(), ensure_ascii=False, sort_keys=True) for r in records)
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")
    return len(lines)


def read_jsonl(path) -> Iterator[LinkRecord]:
    """Read and validate records; ArtifactError names the bad line."""
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield LinkRecord.from_dict(json.loads(line))
            except (ArtifactError, json.JSONDecodeError) as exc:
                raise ArtifactError(f"{path}:{number}: {exc}") from None
