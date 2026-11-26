"""
The authority artifact: what the Phase 4 extractors write and the authority
loader (data_loading/authority_loader.py) reads (roadmap R4.1-R4.6).

One JSON object per line, one line per reference (an occurrence in a text, or
one metadata entry). The citing case is named by natural keys only (ECLI,
else CELEX, else item_id); the cited document by its natural key
(kind, identifier_scheme, identifier) plus its attributes. No database ids, so
the same file loads into db-dev and, after verification, into production.

    {"source": {"ecli": "ECLI:NL:RVS:2020:423"},
     "authority": {"kind": "nl_parliamentary_paper",
                   "identifier_scheme": "officielebekendmakingen",
                   "identifier": "kst-34356-3",
                   "title": "Kamerstuk 34356, nr. 3", "issuer": null,
                   "date": null,
                   "url": "https://zoek.officielebekendmakingen.nl/kst-34356-3.html"},
     "raw_reference": "Kamerstukken II 2015/16, 34 356, nr. 3, p. 12",
     "pinpoint": "p. 12",
     "source_dataset": "rs_text_authority",
     "extractor_version": "authority_text/1.0.0",
     "match_method": "nl_kamerstuk", "confidence": 0.95,
     "mention": {"text_field": "fulltext", "language": "nl",
                 "text_source": "RECHTSPRAAK", "char_start": 10234,
                 "char_end": 10279, "context": "..."}}

authority_document rows are shared: every reference to the same
(kind, identifier_scheme, identifier) points at one row, whichever case or
dataset cites it. The extractors derive title, issuer, date and url from the
identifier alone, so every record with the same key carries the same
attributes; the loader inserts the first and never updates it.

``raw_reference`` is the reference as written (or the metadata value as
stored); with the mention's text_field, language and char_start it is the
row's key in case_authority_reference (case_authority_reference_uk).
"""

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterator, Optional

from data_extraction.linking.artifact import (
    ArtifactError,
    ArtifactWriter,
    CaseKey,
    DatasetWriters,
)

# The source datasets of the authority extractors, one per extractor (the
# brief's naming), and the kinds of document they may write.
AUTHORITY_DATASETS = (
    "rs_text_authority",
    "echr_text_authority",
    "cellar_authority",
    "rs_publication",
)
KINDS = (
    "nl_parliamentary_paper",  # Kamerstukken, Handelingen (R4.1)
    "nl_official_publication",  # Staatsblad, Staatscourant, Tractatenblad (R4.1/R4.2)
    "nl_policy_rule",  # Vreemdelingencirculaire, tax decrees (R4.2)
    "eu_preparatory_act",  # Cellar sector 5 (R4.3)
    "eu_decision",  # Cellar sector 3, descriptor D (R4.3)
    "national_court_decision",  # Cellar sector 8, foreign ECLIs (R4.4)
    "efta_court",  # Cellar sector E, judgments (R4.4)
    "efta_document",  # Cellar sector E, other descriptors (R4.4)
    "un_treaty_body",  # CCPR, CAT, CRC, ... documents and views (R4.5)
    "coe_body",  # Venice Commission, CPT, GRECO, ECRI, Committee of Ministers (R4.5)
    "literature",  # journal reports and articles (R4.6)
    "annotation",  # a named author's note on a decision (R4.6)
)
TEXT_FIELDS = ("fulltext", "summary", "national_judgement_xml", "metadata")


def is_authority_dataset(name: Optional[str]) -> bool:
    return name in AUTHORITY_DATASETS


def _optional_str(value, name):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ArtifactError(f"{name} must be a string, got {value!r}")
    return value or None


@dataclass(frozen=True)
class AuthorityDoc:
    kind: str
    identifier_scheme: str
    identifier: str
    title: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None  # ISO date, only when the identifier gives the full date
    url: Optional[str] = None

    @property
    def key(self):
        return (self.kind, self.identifier_scheme, self.identifier)

    def validate(self):
        if self.kind not in KINDS:
            raise ArtifactError(f"unknown authority kind {self.kind!r}")
        if not self.identifier_scheme or not self.identifier:
            raise ArtifactError("an authority needs identifier_scheme and identifier")
        if self.identifier != self.identifier.strip():
            raise ArtifactError(f"identifier {self.identifier!r} has outer whitespace")
        if self.date is not None:
            try:
                date.fromisoformat(self.date)
            except (TypeError, ValueError):
                raise ArtifactError(f"bad authority date {self.date!r}") from None

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError(f"authority must be an object, got {value!r}")
        unknown = set(value) - {f for f in cls.__dataclass_fields__}
        if unknown:
            raise ArtifactError(f"unknown authority field(s): {sorted(unknown)}")
        doc = cls(
            **{
                f: _optional_str(value.get(f), f) if f not in ("kind",) else value.get(f)
                for f in cls.__dataclass_fields__
            }
        )
        doc.validate()
        return doc

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class AuthorityMention:
    text_field: str
    language: Optional[str] = None
    text_source: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    context: Optional[str] = None
    segment_hash: Optional[str] = None

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError(f"mention must be an object, got {value!r}")
        try:
            mention = cls(**value)
        except TypeError as exc:
            raise ArtifactError(f"bad mention {value!r}: {exc}") from None
        mention.validate()
        return mention

    def validate(self):
        if self.text_field not in TEXT_FIELDS:
            raise ArtifactError(f"unknown text_field {self.text_field!r}")
        if (self.char_start is None) != (self.char_end is None):
            raise ArtifactError("char_start and char_end go together")
        if self.char_start is not None and not 0 <= self.char_start <= self.char_end:
            raise ArtifactError(f"bad offsets {self.char_start}..{self.char_end}")

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True)
class AuthorityRecord:
    source: CaseKey
    authority: AuthorityDoc
    raw_reference: str
    source_dataset: str
    extractor_version: str
    mention: AuthorityMention
    pinpoint: Optional[str] = None
    match_method: Optional[str] = None
    confidence: Optional[float] = None

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError("record must be an object")
        for required in (
            "source",
            "authority",
            "raw_reference",
            "source_dataset",
            "extractor_version",
            "mention",
        ):
            if not value.get(required):
                raise ArtifactError(f"record needs {required}")
        unknown = set(value) - set(cls.__dataclass_fields__)
        if unknown:
            raise ArtifactError(f"unknown record field(s): {sorted(unknown)}")
        record = cls(
            source=CaseKey.from_dict(value["source"]),
            authority=AuthorityDoc.from_dict(value["authority"]),
            raw_reference=value["raw_reference"],
            source_dataset=value["source_dataset"],
            extractor_version=value["extractor_version"],
            mention=AuthorityMention.from_dict(value["mention"]),
            pinpoint=value.get("pinpoint") or None,
            match_method=value.get("match_method") or None,
            confidence=value.get("confidence"),
        )
        record.validate()
        return record

    def validate(self):
        if not is_authority_dataset(self.source_dataset):
            raise ArtifactError(
                f"{self.source_dataset!r} is not an authority dataset (AUTHORITY_DATASETS)"
            )
        if not isinstance(self.raw_reference, str) or not self.raw_reference.strip():
            raise ArtifactError("record needs a non-blank raw_reference")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ArtifactError(f"confidence must be between 0 and 1, got {self.confidence}")
        self.authority.validate()
        self.mention.validate()

    def to_dict(self):
        out = {
            "source": self.source.to_dict(),
            "authority": self.authority.to_dict(),
            "raw_reference": self.raw_reference,
            "source_dataset": self.source_dataset,
            "extractor_version": self.extractor_version,
            "mention": self.mention.to_dict(),
        }
        for name in ("pinpoint", "match_method", "confidence"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        return out


# The writers of artifact.py serialise any record with to_dict() and route on
# source_dataset, so they serve this artifact unchanged.
AuthorityWriter = ArtifactWriter
AuthorityDatasetWriters = DatasetWriters


def write_jsonl(records, path) -> int:
    """Write records, one per line, sorted for a stable hash; returns the count."""
    with AuthorityWriter(path) as writer:
        writer.write(records)
    return writer.count


def read_jsonl(path) -> Iterator[AuthorityRecord]:
    """Read and validate records; ArtifactError names the bad line."""
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield AuthorityRecord.from_dict(json.loads(line))
            except (ArtifactError, json.JSONDecodeError) as exc:
                raise ArtifactError(f"{path}:{number}: {exc}") from None
