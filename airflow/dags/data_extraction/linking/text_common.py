"""
Helpers shared by the text link extractors (rs_text, echr_text, cjeu_text).

Everything here is pure except ``iter_case_batches`` and ``connect``, which
read from the database an extractor is pointed at. Nothing calls an external
service.
"""

import argparse
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from data_extraction.linking import resolver
from data_extraction.linking.artifact import CaseKey, LinkRecord, Mention, write_jsonl

log = logging.getLogger(__name__)

CONTEXT_CHARS = 150  # on each side: "up to ~300 chars around it"
BATCH_SIZE = 500


def env_flag(name: str, default: bool) -> bool:
    """A boolean feature flag from the environment ('1', 'true', 'yes', 'on')."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def context(
    text: str, start: int, end: int, width: int = CONTEXT_CHARS, collapse_space: bool = False
) -> str:
    """Up to ``width`` characters on each side of a mention; with
    ``collapse_space`` every whitespace run becomes one space and the ends are
    stripped (rs_text)."""
    snippet = text[max(0, start - width) : end + width]
    if collapse_space:
        return re.sub(r"\s+", " ", snippet).strip()
    return snippet


def cjeu_year_ok(court: str, year2: str, max_year: Optional[int] = None) -> bool:
    """Does a CJEU case number's two-digit year fit its court, and not postdate
    the citation? C/T from 1989, F 2005-2016, no court letter 1953-1988
    (rs_text and echr_text)."""
    y = int(year2)
    if court:
        full = 1900 + y if y >= 50 else 2000 + y
        if court == "F" and not 2005 <= full <= 2016:
            return False
        if court in ("C", "T") and full < 1989:
            return False
    else:
        if not 53 <= y <= 88:
            return False
        full = 1900 + y
    return max_year is None or full <= max_year


@dataclass(frozen=True)
class TextUnit:
    """One stored text and where it came from (for the mention's provenance)."""

    text: str
    text_field: str = "fulltext"
    language: Optional[str] = None
    text_source: Optional[str] = None


@dataclass(frozen=True)
class Source:
    key: CaseKey
    date: Optional[date] = None


def source_key(ecli=None, celex=None, item_id=None) -> CaseKey:
    return CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None)


def mention(unit: TextUnit, start: int, end: int, section: Optional[str] = None) -> Mention:
    return Mention(
        text_field=unit.text_field,
        raw_text=unit.text[start:end],
        language=unit.language,
        text_source=unit.text_source,
        char_start=start,
        char_end=end,
        context=context(unit.text, start, end),
        section=section,
    )


@dataclass
class PendingLink:
    """A link being assembled; several mentions of one target merge into one."""

    target: Optional[CaseKey]
    relation_type: str
    source_dataset: str
    match_method: Optional[str]
    confidence: Optional[float]
    target_ref_raw: Optional[str] = None
    target_ref_scheme: Optional[str] = None
    mentions: List[Mention] = field(default_factory=list)

    def merge_key(self):
        target = self.target.to_dict() if self.target else None
        ref = None if self.target else (self.target_ref_scheme, self.target_ref_raw)
        return (
            tuple(sorted(target.items())) if target else None,
            ref,
            self.relation_type,
            self.source_dataset,
        )


def build_records(source: Source, pending: Iterable[PendingLink], extractor_version: str):
    """Merge pending links per (target, relation, dataset) and return LinkRecords.

    When the same target is reached by several rules, the most confident rule
    is kept as the row's match_method/confidence and every mention is kept.
    Self-links are dropped.
    """
    merged: Dict[tuple, PendingLink] = {}
    for link in pending:
        if link.target is not None and link.target == source.key:
            continue
        key = link.merge_key()
        current = merged.get(key)
        if current is None:
            merged[key] = PendingLink(
                target=link.target,
                relation_type=link.relation_type,
                source_dataset=link.source_dataset,
                match_method=link.match_method,
                confidence=link.confidence,
                target_ref_raw=link.target_ref_raw,
                target_ref_scheme=link.target_ref_scheme,
                mentions=list(link.mentions),
            )
            continue
        if (link.confidence or 0) > (current.confidence or 0):
            current.match_method, current.confidence = link.match_method, link.confidence
            if link.target_ref_raw and not current.target_ref_raw:
                current.target_ref_raw = link.target_ref_raw
                current.target_ref_scheme = link.target_ref_scheme
        current.mentions.extend(link.mentions)
    records = []
    for link in merged.values():
        seen, mentions = set(), []
        for m in sorted(
            link.mentions,
            key=lambda m: (m.text_source or "", m.language or "", m.text_field, m.char_start or 0),
        ):
            mkey = (m.text_field, m.language, m.text_source, m.char_start, m.raw_text)
            if mkey not in seen:
                seen.add(mkey)
                mentions.append(m)
        record = LinkRecord(
            source=source.key,
            target=link.target,
            target_ref_raw=link.target_ref_raw,
            target_ref_scheme=link.target_ref_scheme if link.target_ref_raw else None,
            relation_type=link.relation_type,
            source_dataset=link.source_dataset,
            extractor_version=extractor_version,
            match_method=link.match_method,
            confidence=link.confidence,
            mentions=tuple(mentions),
        )
        record.validate()
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Dates as courts write them ("22 June 2004", "22 juin 2004", "22. Juni 2004")
# ---------------------------------------------------------------------------

_MONTHS = {
    # en
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    # fr
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
    # de
    "januar": 1, "jänner": 1, "februar": 2, "märz": 3, "juni": 6, "juli": 7, "oktober": 10,
    "dezember": 12,
    # nl
    "januari": 1, "februari": 2, "maart": 3, "mei": 5, "augustus": 8,
    # it
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "dicembre": 12,
    # es
    "enero": 1, "febrero": 2, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}  # fmt: skip

DATE_RE = re.compile(
    r"\b(?P<day>[0-3]?\d)(?:\.|er|st|nd|rd|th)?\s+(?:de\s+)?(?P<month>[^\W\d_]{3,10})\.?\s+"
    r"(?:de\s+)?(?P<year>1[89]\d\d|20\d\d)\b"
)


def parse_date_match(match) -> Optional[date]:
    month = _MONTHS.get(match.group("month").lower())
    if month is None:
        return None
    try:
        return date(int(match.group("year")), month, int(match.group("day")))
    except ValueError:
        return None


def first_date(text: str) -> Optional[Tuple[date, int, int]]:
    """The first valid written date in text, with its offsets."""
    for match in DATE_RE.finditer(text):
        value = parse_date_match(match)
        if value is not None:
            return value, match.start(), match.end()
    return None


# ---------------------------------------------------------------------------
# Database side: candidate lookups and keyset paging
# ---------------------------------------------------------------------------


class CandidateLookup:
    """Candidates per identifier scheme, from case_identifier (resolver.fetch_candidates).

    ``prefetch`` loads a whole batch's values in one query per scheme; ``get``
    answers from the cache and fetches anything missing.
    """

    def __init__(self, cursor):
        self.cursor = cursor
        self._cache: Dict[str, Dict[str, list]] = {}

    def prefetch(self, scheme: str, values: Iterable[str]):
        cache = self._cache.setdefault(scheme, {})
        missing = sorted({v for v in values if v and v not in cache})
        if not missing:
            return
        found = resolver.fetch_candidates(self.cursor, scheme, missing)
        for value in missing:
            cache[value] = found.get(value, [])

    def get(self, scheme: str, values: Iterable[str]) -> Dict[str, list]:
        values = [v for v in values if v]
        self.prefetch(scheme, values)
        cache = self._cache[scheme] if scheme in self._cache else {}
        return {v: cache.get(v, []) for v in values}

    def clear(self):
        self._cache.clear()


class DictLookup:
    """In-memory lookup for unit tests: {scheme: {value_normalized: [Candidate]}}."""

    def __init__(self, data: Optional[Dict[str, Dict[str, list]]] = None):
        self.data = data or {}

    def prefetch(self, scheme, values):
        return None

    def get(self, scheme, values):
        table = self.data.get(scheme, {})
        return {v: list(table.get(v, [])) for v in values if v}

    def clear(self):
        return None


def iter_case_batches(
    conn,
    ids_sql: str,
    params: Sequence = (),
    case_ids: Optional[Sequence[int]] = None,
    id_range: Optional[Tuple[Optional[int], Optional[int]]] = None,
    batch_size: int = BATCH_SIZE,
) -> Iterator[List[int]]:
    """Yield lists of case ids in ascending order, by keyset.

    ``ids_sql`` selects ``case_id`` and must contain the placeholder ``{where}``
    where the keyset and range conditions go (each starting with AND), and end
    with ``ORDER BY case_id LIMIT %s``-free text: the paging is added here.
    """
    if case_ids is not None:
        ids = sorted({int(i) for i in case_ids})
        for i in range(0, len(ids), batch_size):
            yield ids[i : i + batch_size]
        return
    low, high = id_range or (None, None)
    last = None
    while True:
        conditions, values = [], list(params)
        if last is not None:
            conditions.append("AND case_id > %s")
            values.append(last)
        if low is not None:
            conditions.append("AND case_id >= %s")
            values.append(low)
        if high is not None:
            conditions.append("AND case_id <= %s")
            values.append(high)
        sql = ids_sql.format(where=" ".join(conditions)) + " ORDER BY case_id LIMIT %s"
        values.append(batch_size)
        with conn.cursor() as cursor:
            cursor.execute(sql, values)
            ids = [row[0] for row in cursor.fetchall()]
        if not ids:
            return
        yield ids
        last = ids[-1]


def connect(dsn_env: str):
    import psycopg2

    dsn = os.environ.get(dsn_env)
    if not dsn:
        raise SystemExit(f"environment variable {dsn_env} is not set")
    return psycopg2.connect(dsn)


def cli_args(description: str, argv=None, extra=None):
    """The extractors' common CLI; ``extra(parser)`` adds an extractor's own options."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    parser.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    parser.add_argument("--case-id", type=int, action="append", default=None)
    parser.add_argument("--out", required=True, help="JSONL artifact to write")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="cases per batch")
    if extra is not None:
        extra(parser)
    return parser.parse_args(argv)


def write_artifact(records: Iterable[LinkRecord], out_path) -> int:
    return write_jsonl(records, out_path)
