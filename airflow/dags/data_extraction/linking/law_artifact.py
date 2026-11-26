"""
The law-reference artifact: what the law-reference extractors write and
data_loading/law_reference_loader reads (roadmap R3.2-R3.4).

One JSON object per line, like the link artifact (artifact.py), and keyed the
same way: the citing case by natural key (ECLI, else CELEX, else item_id), the
cited act by scheme + identifier, never by database ids, so one file loads into
db-dev and, after verification, into production.

    {"source": {"ecli": "ECLI:NL:RVS:2020:423"},
     "target": {"scheme": "celex", "identifier": "32011L0095",
                "alternatives": []},                    # tried in order after identifier
     "raw_scheme": "celex", "raw_resource": "32011L0095",
     "raw_subdivision": "15",                           # article (and paragraph) as cited
     "article": "15",                                   # the article alone, for legal_provision
     "raw_reference": "artikel 15, aanhef en onder c, van Richtlijn 2011/95/EU",
     "role": "cited", "source_dataset": "rs_text_eu_law",
     "extractor_version": "eu_law_text/1.0.0",
     "match_method": "act_number", "confidence": 0.95,
     "mentions": [{"text_field": "fulltext", ...}]}     # artifact.Mention, provenance only

``target`` names the act the loader resolves to ``legislation`` (scheme +
identifier, then each alternative, then legislation_alias rows with source
'curated'). When nothing matches, the row is written unresolved with
raw_scheme / raw_resource / raw_subdivision only. ``raw_*`` are what the row
stores whatever the resolution, so a re-run after the act is added finds the
same natural key. ``mentions`` stay in the artifact (case_law_reference has
no mention table); the loader stores the first mention's text as
raw_reference when the record has none.

match_method (what identified the act): ``celex_metadata`` (a Cellar
relation), ``act_number`` ("Richtlijn 2011/95/EU"), ``treaty_article``
("artikel 267 VWEU"), ``act_name`` ("artikel 6 AVG").
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Iterator, Optional, Tuple

from data_extraction.linking.artifact import ArtifactError, CaseKey, Mention

# The source datasets this artifact may carry: each has its own extractor and
# can be removed with one DELETE ... WHERE source_dataset = ....
LAW_DATASETS = ("cellar_law_ref", "rs_text_eu_law", "echr_text_eu_law")
LAW_MATCH_METHODS = ("celex_metadata", "act_number", "treaty_article", "act_name")
TARGET_SCHEMES = ("celex", "coe_treaty", "un_treaty")
RAW_SCHEMES = ("celex",)


@dataclass(frozen=True)
class LawTarget:
    scheme: str
    identifier: str
    alternatives: Tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError(f"target must be an object, got {value!r}")
        unknown = set(value) - {"scheme", "identifier", "alternatives"}
        if unknown:
            raise ArtifactError(f"unknown target field(s): {sorted(unknown)}")
        target = cls(
            scheme=value.get("scheme") or "",
            identifier=value.get("identifier") or "",
            alternatives=tuple(value.get("alternatives") or ()),
        )
        target.validate()
        return target

    def validate(self):
        if self.scheme not in TARGET_SCHEMES:
            raise ArtifactError(f"unknown target scheme {self.scheme!r}")
        if not self.identifier:
            raise ArtifactError("target needs an identifier")
        if any(not a for a in self.alternatives):
            raise ArtifactError("empty alternative identifier")

    @property
    def identifiers(self) -> Tuple[str, ...]:
        """identifier, then the alternatives, without repeats."""
        seen, out = set(), []
        for value in (self.identifier,) + self.alternatives:
            if value not in seen:
                seen.add(value)
                out.append(value)
        return tuple(out)

    def to_dict(self):
        out = {"scheme": self.scheme, "identifier": self.identifier}
        if self.alternatives:
            out["alternatives"] = list(self.alternatives)
        return out


@dataclass(frozen=True)
class LawReferenceRecord:
    source: CaseKey
    target: LawTarget
    raw_scheme: str
    raw_resource: str
    source_dataset: str
    extractor_version: str
    role: str = "cited"
    raw_subdivision: Optional[str] = None
    article: Optional[str] = None
    raw_reference: Optional[str] = None
    match_method: Optional[str] = None
    confidence: Optional[float] = None
    mentions: tuple = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError("record must be an object")
        for required in (
            "source",
            "target",
            "raw_scheme",
            "raw_resource",
            "source_dataset",
            "extractor_version",
            "role",
        ):
            if not value.get(required):
                raise ArtifactError(f"record needs {required}")
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(value) - known
        if unknown:
            raise ArtifactError(f"unknown record field(s): {sorted(unknown)}")
        record = cls(
            source=CaseKey.from_dict(value["source"]),
            target=LawTarget.from_dict(value["target"]),
            raw_scheme=value["raw_scheme"],
            raw_resource=value["raw_resource"],
            raw_subdivision=value.get("raw_subdivision") or None,
            article=value.get("article") or None,
            raw_reference=value.get("raw_reference") or None,
            role=value["role"],
            source_dataset=value["source_dataset"],
            extractor_version=value["extractor_version"],
            match_method=value.get("match_method") or None,
            confidence=value.get("confidence"),
            mentions=tuple(Mention.from_dict(m) for m in value.get("mentions") or ()),
        )
        record.validate()
        return record

    def validate(self):
        if self.source_dataset not in LAW_DATASETS:
            raise ArtifactError(f"{self.source_dataset!r} is not a law dataset (LAW_DATASETS)")
        if self.raw_scheme not in RAW_SCHEMES:
            raise ArtifactError(f"unknown raw_scheme {self.raw_scheme!r}")
        if not self.raw_resource:
            raise ArtifactError("record needs raw_resource")
        self.target.validate()
        if self.match_method is not None and self.match_method not in LAW_MATCH_METHODS:
            raise ArtifactError(f"bad match_method {self.match_method!r}")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ArtifactError(f"confidence must be between 0 and 1, got {self.confidence}")
        if self.article is not None and self.raw_subdivision is None:
            raise ArtifactError("article without raw_subdivision")

    @property
    def natural_key(self):
        """What identifies the stored row (case_law_reference_uk_raw's columns)."""
        return (
            self.source,
            self.raw_scheme,
            self.raw_resource,
            self.raw_subdivision or "",
            self.role,
            self.source_dataset,
        )

    def to_dict(self):
        out = {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "raw_scheme": self.raw_scheme,
            "raw_resource": self.raw_resource,
            "role": self.role,
            "source_dataset": self.source_dataset,
            "extractor_version": self.extractor_version,
        }
        for name in (
            "raw_subdivision",
            "article",
            "raw_reference",
            "match_method",
            "confidence",
        ):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if self.mentions:
            out["mentions"] = [
                {k: v for k, v in asdict(m).items() if v is not None} for m in self.mentions
            ]
        return out


def read_jsonl(path) -> Iterator[LawReferenceRecord]:
    """Read and validate records; ArtifactError names the bad line."""
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield LawReferenceRecord.from_dict(json.loads(line))
            except (ArtifactError, json.JSONDecodeError) as exc:
                raise ArtifactError(f"{path}:{number}: {exc}") from None
