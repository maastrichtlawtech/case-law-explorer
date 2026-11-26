"""
Acts outside the BWB register: the record, the curated fixture and the
legislation artifact.

One JSON object per line, keyed by the natural key (scheme, identifier), never
by legislation.id:

    {"scheme": "celex", "identifier": "32016R0679", "jurisdiction": "EU",
     "document_type": "regulation", "enacted_year": 2016,
     "source_dataset": "legislation_cellar",
     "extractor_version": "legislation_catalog/1.0.0"}

Optional: title, enacted_date (ISO date), eli, aliases (list of strings;
loaded into legislation_alias with source 'curated'), protocol_number
(curated ECHR rows only; not stored).

Schemes (migration 0011, legislation_uk_external):

    celex       CELEX number of the whole act (data_extraction/legislation/celex.py)
    coe_treaty  Council of Europe treaty, CETS number in three digits ('005')
    un_treaty   UN Treaty Collection MTDSG chapter-number ('IV-11')

Datasets:

    legislation_curated  external_acts.json: the treaties, the Charter, the ECHR
                         and its Protocols, the main UN conventions (with titles
                         and aliases)
    legislation_cellar   the CELEX numbers of sectors 1-3 Cellar data in the
                         database refers to (catalog.py); title NULL
"""

import json
import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from data_extraction.linking.artifact import ArtifactError, ArtifactWriter

SCHEMES = ("celex", "coe_treaty", "un_treaty")
JURISDICTIONS = ("EU", "CE", "UN")
DATASET_CURATED = "legislation_curated"
DATASET_CELLAR = "legislation_cellar"
DATASET_CELLAR_SPARQL = "cellar_legislation_sparql"
DATASETS = (DATASET_CURATED, DATASET_CELLAR, DATASET_CELLAR_SPARQL)
CURATED_VERSION = "legislation_curated/1.0.0"
ALIAS_SOURCE = "curated"
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "external_acts.json")

# The predicate of legislation_uk_external, restated in every ON CONFLICT.
UK_PREDICATE = "scheme IN ('celex', 'coe_treaty', 'un_treaty')"


@dataclass(frozen=True)
class ActRecord:
    scheme: str
    identifier: str
    jurisdiction: str
    source_dataset: str
    extractor_version: str
    document_type: Optional[str] = None
    title: Optional[str] = None
    enacted_date: Optional[str] = None
    enacted_year: Optional[int] = None
    eli: Optional[str] = None
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    protocol_number: Optional[int] = None

    @property
    def key(self) -> Tuple[str, str]:
        return (self.scheme, self.identifier)

    @classmethod
    def from_dict(cls, value, source_dataset=None, extractor_version=None):
        if not isinstance(value, dict):
            raise ArtifactError("act must be an object")
        known = set(cls.__dataclass_fields__)
        unknown = set(value) - known
        if unknown:
            raise ArtifactError(f"unknown act field(s): {sorted(unknown)}")
        data = dict(value)
        data.setdefault("source_dataset", source_dataset)
        data.setdefault("extractor_version", extractor_version)
        data["aliases"] = tuple(data.get("aliases") or ())
        try:
            record = cls(**data)
        except TypeError as exc:
            raise ArtifactError(f"bad act {value!r}: {exc}") from None
        record.validate()
        return record

    def validate(self):
        if self.scheme not in SCHEMES:
            raise ArtifactError(f"unknown scheme {self.scheme!r}")
        if not self.identifier or self.identifier != self.identifier.strip():
            raise ArtifactError(f"bad identifier {self.identifier!r}")
        if self.jurisdiction not in JURISDICTIONS:
            raise ArtifactError(f"unknown jurisdiction {self.jurisdiction!r}")
        if self.source_dataset not in DATASETS:
            raise ArtifactError(f"unknown source_dataset {self.source_dataset!r}")
        if not self.extractor_version:
            raise ArtifactError("act needs extractor_version")
        if self.enacted_date is not None:
            try:
                parsed = date.fromisoformat(self.enacted_date)
            except (TypeError, ValueError):
                raise ArtifactError(f"bad enacted_date {self.enacted_date!r}") from None
            if self.enacted_year is not None and parsed.year != self.enacted_year:
                raise ArtifactError("enacted_date and enacted_year disagree")
        if any(not isinstance(a, str) or not a.strip() for a in self.aliases):
            raise ArtifactError(f"bad alias in {self.aliases!r}")

    def to_dict(self):
        out = {
            "scheme": self.scheme,
            "identifier": self.identifier,
            "jurisdiction": self.jurisdiction,
            "source_dataset": self.source_dataset,
            "extractor_version": self.extractor_version,
        }
        for name in ("document_type", "title", "enacted_date", "enacted_year", "eli"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if self.aliases:
            out["aliases"] = list(self.aliases)
        if self.protocol_number is not None:
            out["protocol_number"] = self.protocol_number
        return out


@lru_cache(maxsize=None)
def _curated(path: str) -> Tuple[ActRecord, ...]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    records = tuple(
        ActRecord.from_dict(item, DATASET_CURATED, CURATED_VERSION) for item in data["acts"]
    )
    keys = [r.key for r in records]
    if len(keys) != len(set(keys)):
        raise ArtifactError(f"{path}: duplicate (scheme, identifier)")
    return records


def curated_acts(path: str = FIXTURE) -> List[ActRecord]:
    """The committed fixture, in file order."""
    return list(_curated(os.path.abspath(path)))


def curated_by_key(path: str = FIXTURE) -> Dict[Tuple[str, str], ActRecord]:
    return {r.key: r for r in _curated(os.path.abspath(path))}


def echr_protocols(path: str = FIXTURE) -> Dict[int, ActRecord]:
    """{protocol number: act}; 0 is the Convention itself."""
    return {
        r.protocol_number: r
        for r in _curated(os.path.abspath(path))
        if r.scheme == "coe_treaty" and r.protocol_number is not None
    }


def write_acts(batches: Iterable[Iterable[ActRecord]], path) -> int:
    """Write the legislation artifact, one sorted batch after another (the
    curated acts first, so a loader meets their titles before a bare CELEX
    row of the same act). Returns the number of records."""
    with ArtifactWriter(path) as writer:
        for batch in batches:
            writer.write(batch)
    return writer.count


def read_acts(path) -> Iterator[ActRecord]:
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield ActRecord.from_dict(json.loads(line))
            except (ArtifactError, json.JSONDecodeError) as exc:
                raise ArtifactError(f"{path}:{number}: {exc}") from None
