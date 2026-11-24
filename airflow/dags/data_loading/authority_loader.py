"""
Load an authority artifact (data_extraction/linking/authority_artifact.py)
into authority_document and case_authority_reference (roadmap R4.1-R4.6).

The same code loads the weekly artifacts into db-dev, the promoter's replay
into production and the historical backfill, so it only ever inserts:

  * authority_document: one row per (kind, identifier_scheme, identifier),
    shared by every case and dataset that cites it. A document already
    present is used as it is (its attributes are never updated);
  * case_authority_reference: one row per record, keyed by
    case_authority_reference_uk (case, raw_reference, text_field, language,
    char_start, source_dataset); a row already present is left as it is.

The citing case is mapped from its natural key (ECLI, else CELEX, else
item_id) in this database; a record whose case is missing is counted and
skipped. case_text_id comes from (case, language, text source), and
context_segment_id from the mention's segment_hash when there is one.

Each batch takes a fixed number of statements, whatever its size: case
lookup, document insert, document lookup, case_text / case_segment lookups,
reference insert. Returns counts per source_dataset: inserted, existing,
source_missing and documents_inserted (documents first inserted by a record
of that dataset).

Removing a dataset is ``DELETE FROM case_authority_reference WHERE
source_dataset = ...``. authority_document rows carry no dataset (they are
shared); documents left without references can be removed afterwards with
``DELETE FROM authority_document d WHERE NOT EXISTS (SELECT 1 FROM
case_authority_reference r WHERE r.authority_document_id = d.id)``.

CLI:
    python -m data_loading.authority_loader --dsn-env VAR PATH [PATH ...]
"""

import argparse
import json
import logging
import os
from collections import Counter, defaultdict
from typing import Iterable

from data_extraction.linking.authority_artifact import AuthorityRecord, read_jsonl
from data_loading.link_loader import _cases_by_key, _resolve, _template, _values

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
BATCH_SIZE = 2000

_DOC_FIELDS = (
    ("kind", "text"),
    ("identifier_scheme", "text"),
    ("identifier", "text"),
    ("title", "text"),
    ("issuer", "text"),
    ("date", "date"),
    ("url", "text"),
)
_DOC_COLUMNS = ", ".join(f for f, _t in _DOC_FIELDS)
# The arbiter restates the partial index's expression and predicate, so the
# statement works against the deployed partial index and any local copy.
_INSERT_DOCUMENTS = f"""
    INSERT INTO {SCHEMA}.authority_document ({_DOC_COLUMNS})
    SELECT {_DOC_COLUMNS} FROM (VALUES %s) AS v(ord, {_DOC_COLUMNS})
     ORDER BY ord
    ON CONFLICT (kind, COALESCE(identifier_scheme, ''), identifier)
        WHERE identifier IS NOT NULL
    DO NOTHING
    RETURNING id, kind, identifier_scheme, identifier
"""
_DOC_TEMPLATE = _template(["integer"] + [t for _f, t in _DOC_FIELDS])
_FIND_DOCUMENTS = f"""
    SELECT d.id, d.kind, d.identifier_scheme, d.identifier
      FROM (VALUES %s) AS v(kind, identifier_scheme, identifier)
      JOIN {SCHEMA}.authority_document d
        ON d.kind = v.kind AND COALESCE(d.identifier_scheme, '') = COALESCE(v.identifier_scheme, '')
       AND d.identifier = v.identifier
"""
_FIND_TEMPLATE = "(%s::text, %s::text, %s::text)"

_REF_FIELDS = (
    ("case_id", "bigint"),
    ("authority_document_id", "bigint"),
    ("raw_reference", "text"),
    ("pinpoint", "text"),
    ("case_text_id", "bigint"),
    ("text_field", "text"),
    ("language", "text"),
    ("char_start", "integer"),
    ("char_end", "integer"),
    ("context", "text"),
    ("context_segment_id", "bigint"),
    ("source_dataset", "text"),
    ("extractor_version", "text"),
    ("match_method", "text"),
    ("confidence", "real"),
)
_REF_COLUMNS = ", ".join(f for f, _t in _REF_FIELDS)
_INSERT_REFERENCES = f"""
    INSERT INTO {SCHEMA}.case_authority_reference ({_REF_COLUMNS})
    SELECT {_REF_COLUMNS} FROM (VALUES %s) AS v(ord, {_REF_COLUMNS})
     ORDER BY ord
    ON CONFLICT (case_id, md5(raw_reference), COALESCE(text_field, ''), COALESCE(language, ''),
                 COALESCE(char_start, -1), source_dataset)
    DO NOTHING
    RETURNING source_dataset
"""
_REF_TEMPLATE = _template(["integer"] + [t for _f, t in _REF_FIELDS])

_CASE_TEXTS = f"""
    SELECT case_id, language, source, id FROM {SCHEMA}.case_text
     WHERE case_id = ANY(%s) AND source = ANY(%s)
"""
_CASE_SEGMENTS = f"""
    SELECT case_id, segment_hash, id FROM {SCHEMA}.case_segment
     WHERE case_id = ANY(%s) AND segment_hash = ANY(%s)
"""


class _Keyed:
    """What link_loader._cases_by_key reads from a record: source and target."""

    __slots__ = ("source", "target")

    def __init__(self, source):
        self.source = source
        self.target = None


def _documents(cursor, planned, counts):
    """authority_document id for every document of planned [(record, case_id)];
    inserts the new ones (first record of the batch wins) in one statement."""
    first = {}
    for record, _case_id in planned:
        first.setdefault(record.authority.key, record)
    rows = [
        (i,) + tuple(getattr(r.authority, f) for f, _t in _DOC_FIELDS)
        for i, r in enumerate(first.values())
    ]
    ids = {}
    for doc_id, kind, scheme, identifier in _values(cursor, _INSERT_DOCUMENTS, rows, _DOC_TEMPLATE):
        key = (kind, scheme, identifier)
        ids[key] = doc_id
        counts[first[key].source_dataset]["documents_inserted"] += 1
    missing = sorted(k for k in first if k not in ids)
    for doc_id, kind, scheme, identifier in _values(
        cursor, _FIND_DOCUMENTS, missing, _FIND_TEMPLATE
    ):
        ids[(kind, scheme, identifier)] = doc_id
    return ids


def _text_ids(cursor, planned):
    case_ids = sorted({case_id for _r, case_id in planned})
    sources = sorted({r.mention.text_source for r, _c in planned} - {None})
    hashes = sorted({r.mention.segment_hash for r, _c in planned} - {None})
    texts, segments = {}, {}
    if case_ids and sources:
        cursor.execute(_CASE_TEXTS, (case_ids, sources))
        texts = {(c, lang, src): i for c, lang, src, i in cursor.fetchall()}
    if case_ids and hashes:
        cursor.execute(_CASE_SEGMENTS, (case_ids, hashes))
        segments = {(c, h): i for c, h, i in cursor.fetchall()}
    return texts, segments


def _load_batch(cursor, batch, counts):
    found = _cases_by_key(cursor, [_Keyed(r.source) for r in batch])
    planned = []
    for record in batch:
        source = _resolve(found, record.source)
        if source is None:
            counts[record.source_dataset]["source_missing"] += 1
            continue
        planned.append((record, source[0]))
    if not planned:
        return
    doc_ids = _documents(cursor, planned, counts)
    texts, segments = _text_ids(cursor, planned)
    rows = []
    for i, (record, case_id) in enumerate(planned):
        m = record.mention
        rows.append(
            (
                i,
                case_id,
                doc_ids[record.authority.key],
                record.raw_reference,
                record.pinpoint,
                texts.get((case_id, m.language, m.text_source)),
                m.text_field,
                m.language,
                m.char_start,
                m.char_end,
                m.context,
                segments.get((case_id, m.segment_hash)),
                record.source_dataset,
                record.extractor_version,
                record.match_method,
                record.confidence,
            )
        )
    inserted = Counter(
        dataset for (dataset,) in _values(cursor, _INSERT_REFERENCES, rows, _REF_TEMPLATE)
    )
    planned_per_dataset = Counter(record.source_dataset for record, _c in planned)
    for dataset, total in planned_per_dataset.items():
        counts[dataset]["inserted"] += inserted[dataset]
        counts[dataset]["existing"] += total - inserted[dataset]


def load_records(conn, records: Iterable[AuthorityRecord], batch_size: int = BATCH_SIZE):
    """Insert records batch by batch, one transaction per batch; records are
    read lazily, so an artifact of any size streams. Returns
    {source_dataset: {count: n}} (zero counts left out)."""
    counts = defaultdict(Counter)
    batch = []

    def flush():
        if not batch:
            return
        with conn.cursor() as cursor:
            _load_batch(cursor, batch, counts)
        conn.commit()
        batch.clear()

    try:
        for record in records:
            batch.append(record)
            if len(batch) >= batch_size:
                flush()
        flush()
    except Exception:
        conn.rollback()
        raise
    for dataset, c in sorted(counts.items()):
        log.info("authority load %s: %s", dataset, dict(sorted(c.items())))
    return {dataset: {k: v for k, v in c.items() if v} for dataset, c in counts.items()}


def load_artifact(conn, path, batch_size: int = BATCH_SIZE):
    """Load one JSONL authority artifact; see load_records."""
    return load_records(conn, read_jsonl(path), batch_size=batch_size)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Load authority artifacts (insert-only)")
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args(argv)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f"environment variable {args.dsn_env} is not set")
    import psycopg2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = psycopg2.connect(dsn)
    try:
        result = {}
        for path in args.paths:
            for dataset, c in load_artifact(conn, path, args.batch_size).items():
                total = result.setdefault(dataset, Counter())
                total.update(c)
    finally:
        conn.close()
    print(json.dumps({d: dict(c) for d, c in result.items()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
