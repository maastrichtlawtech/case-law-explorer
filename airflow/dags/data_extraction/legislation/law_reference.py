"""
The law-reference artifact: a case refers to a provision (or a whole act)
outside the BWB register. What an extractor such as echr_articles.py writes and
data_loading/legislation_loader.py reads.

One JSON object per line, natural keys only:

    {"source": {"ecli": "ECLI:CE:ECHR:2008:0612JUD001875603"},
     "act": {"scheme": "coe_treaty", "identifier": "005"},
     "article": "6", "paragraph": "1",
     "role": "violation", "source_dataset": "echr_article",
     "extractor_version": "echr_article/1.0.0",
     "raw_scheme": "echr_article", "raw_subdivision": "6-1",
     "raw_reference": "6-1"}

``source`` is a case key as in the link artifact (ECLI, else CELEX, else
item_id). ``article`` is required unless the reference is to the whole act;
``paragraph`` needs ``article``. The loader creates the provision rows it needs
(insert-only) and writes case_law_reference with provision_id and
legislation_id set and raw_resource NULL, the shape
case_law_reference_uk_provision covers.
"""

import json
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

from data_extraction.legislation.acts import SCHEMES
from data_extraction.linking.artifact import ArtifactError, CaseKey

DATASETS = ("echr_article",)


@dataclass(frozen=True)
class LawReferenceRecord:
    source: CaseKey
    scheme: str
    identifier: str
    role: str
    source_dataset: str
    extractor_version: str
    article: Optional[str] = None
    paragraph: Optional[str] = None
    raw_scheme: Optional[str] = None
    raw_subdivision: Optional[str] = None
    raw_reference: Optional[str] = None

    # The link loader's case lookup reads .source and .target.
    target = None

    @property
    def act_key(self) -> Tuple[str, str]:
        return (self.scheme, self.identifier)

    @property
    def provision_key(self) -> Optional[Tuple[str, Optional[str]]]:
        return None if self.article is None else (self.article, self.paragraph)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ArtifactError("record must be an object")
        for required in ("source", "act", "role", "source_dataset", "extractor_version"):
            if not value.get(required):
                raise ArtifactError(f"record needs {required}")
        act = value["act"]
        if not isinstance(act, dict) or set(act) != {"scheme", "identifier"}:
            raise ArtifactError(f"act must be {{scheme, identifier}}, got {act!r}")
        known = {
            "source",
            "act",
            "role",
            "source_dataset",
            "extractor_version",
            "article",
            "paragraph",
            "raw_scheme",
            "raw_subdivision",
            "raw_reference",
        }
        unknown = set(value) - known
        if unknown:
            raise ArtifactError(f"unknown field(s): {sorted(unknown)}")
        record = cls(
            source=CaseKey.from_dict(value["source"]),
            scheme=act["scheme"],
            identifier=act["identifier"],
            role=value["role"],
            source_dataset=value["source_dataset"],
            extractor_version=value["extractor_version"],
            article=value.get("article") or None,
            paragraph=value.get("paragraph") or None,
            raw_scheme=value.get("raw_scheme") or None,
            raw_subdivision=value.get("raw_subdivision") or None,
            raw_reference=value.get("raw_reference") or None,
        )
        record.validate()
        return record

    def validate(self):
        if self.source is None:
            raise ArtifactError("record needs a source case")
        if self.source_dataset not in DATASETS:
            raise ArtifactError(f"{self.source_dataset!r} is not a law-reference dataset")
        if self.scheme not in SCHEMES or not self.identifier:
            raise ArtifactError(f"bad act {self.scheme!r}/{self.identifier!r}")
        if self.paragraph is not None and self.article is None:
            raise ArtifactError("paragraph without article")

    def to_dict(self):
        out = {
            "source": self.source.to_dict(),
            "act": {"scheme": self.scheme, "identifier": self.identifier},
            "role": self.role,
            "source_dataset": self.source_dataset,
            "extractor_version": self.extractor_version,
        }
        for name in ("article", "paragraph", "raw_scheme", "raw_subdivision", "raw_reference"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        return out


def read_law_references(path) -> Iterator[LawReferenceRecord]:
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield LawReferenceRecord.from_dict(json.loads(line))
            except (ArtifactError, json.JSONDecodeError) as exc:
                raise ArtifactError(f"{path}:{number}: {exc}") from None
