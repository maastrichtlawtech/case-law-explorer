"""
Load a case-context artifact (data_extraction/case_context/artifact.py) into
case_outcome and case_status (roadmap R5.1, R5.2).

Insert-only, like link_loader: natural keys are mapped to cases.id in the
database it runs against (db-dev for the weekly run and the backfill,
production for the promoter's replay), rows go in with ON CONFLICT DO NOTHING
on the tables' unique indexes (restated: case_outcome_uk and case_status_uk
are plain, not partial), nothing is updated or deleted. A dataset is removed
with one ``DELETE FROM case_outcome / case_status WHERE source_dataset = ...``.

  * a record whose case is not in this database is counted (case_missing)
    and skipped;
  * a status naming a related case that is not in this database is counted
    (related_missing) and skipped rather than written without it: the unique
    key leaves related_case_id out, so a row written without it could never
    gain it later (a later run would conflict with it);
  * the confidence column comes from migration 0012; against a database
    without it the rows are written without confidence.

Returns counts per source_dataset: inserted, existing, case_missing,
related_missing (zero counts left out).

CLI:
    python -m data_loading.outcome_loader --dsn-env VAR PATH [PATH ...]
"""

import argparse
import json
import logging
import os
from collections import Counter, defaultdict
from types import SimpleNamespace
from typing import Iterable

from data_extraction.case_context.artifact import OutcomeRecord, Record, read_jsonl
from data_loading.link_loader import _cases_by_key, _resolve

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
BATCH_SIZE = 1000

_OUTCOME_CONFLICT = (
    'ON CONFLICT ("case_id", "scope", COALESCE("article", \'\'), "outcome", "source_dataset") '
    "DO NOTHING RETURNING id"
)
_STATUS_CONFLICT = (
    'ON CONFLICT ("case_id", "status", COALESCE("status_date", \'-infinity\'::date), '
    '"source_dataset") DO NOTHING RETURNING id'
)


def has_confidence(cursor, table) -> bool:
    cursor.execute(
        """SELECT 1 FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = 'confidence'""",
        (SCHEMA, table),
    )
    return cursor.fetchone() is not None


def _execute_values(cursor, sql, rows):
    from psycopg2.extras import execute_values

    return execute_values(cursor, sql, rows, page_size=len(rows), fetch=True)


def _insert(cursor, table, columns, conflict, keyed_rows, counts, dataset):
    """keyed_rows: [(conflict key, values)]. Within a batch the first row per
    key is sent (a repeated key counts as existing); the rest is left to ON
    CONFLICT DO NOTHING."""
    seen, values = set(), []
    for key, row in keyed_rows:
        if key in seen:
            continue
        seen.add(key)
        values.append(row)
    inserted = _execute_values(
        cursor,
        f"INSERT INTO {SCHEMA}.{table} ({', '.join(columns)}) VALUES %s {conflict}",
        values,
    )
    counts[dataset]["inserted"] += len(inserted)
    counts[dataset]["existing"] += len(keyed_rows) - len(inserted)


_OUTCOME_COLUMNS = (
    "case_id",
    "scope",
    "article",
    "outcome",
    "raw_value",
    "source_dataset",
    "extractor_version",
)
_STATUS_COLUMNS = (
    "case_id",
    "status",
    "status_date",
    "related_case_id",
    "raw_value",
    "source_dataset",
    "extractor_version",
)


def _load_batch(cursor, batch, counts, confidence_columns):
    found = _cases_by_key(
        cursor,
        [
            SimpleNamespace(
                source=r.case, target=None if isinstance(r, OutcomeRecord) else r.related
            )
            for r in batch
        ],
    )
    outcome_conf = confidence_columns["case_outcome"]
    status_conf = confidence_columns["case_status"]
    outcomes, statuses = defaultdict(list), defaultdict(list)
    for record in batch:
        dataset_counts = counts[record.source_dataset]
        case = _resolve(found, record.case)
        if case is None:
            dataset_counts["case_missing"] += 1
            continue
        if isinstance(record, OutcomeRecord):
            key = (case[0], record.scope, record.article or "", record.outcome)
            row = (
                case[0],
                record.scope,
                record.article,
                record.outcome,
                record.raw_value,
                record.source_dataset,
                record.extractor_version,
            ) + ((record.confidence,) if outcome_conf else ())
            outcomes[record.source_dataset].append((key, row))
            continue
        related_id = None
        if record.related is not None:
            related = _resolve(found, record.related)
            if related is None:
                dataset_counts["related_missing"] += 1
                continue
            related_id = related[0]
        key = (case[0], record.status, record.status_date)
        row = (
            case[0],
            record.status,
            record.status_date,
            related_id,
            record.raw_value,
            record.source_dataset,
            record.extractor_version,
        ) + ((record.confidence,) if status_conf else ())
        statuses[record.source_dataset].append((key, row))

    extra = ("confidence",)
    for dataset, rows in sorted(outcomes.items()):
        columns = _OUTCOME_COLUMNS + (extra if outcome_conf else ())
        _insert(cursor, "case_outcome", columns, _OUTCOME_CONFLICT, rows, counts, dataset)
    for dataset, rows in sorted(statuses.items()):
        columns = _STATUS_COLUMNS + (extra if status_conf else ())
        _insert(cursor, "case_status", columns, _STATUS_CONFLICT, rows, counts, dataset)


def load_records(conn, records: Iterable[Record], batch_size: int = BATCH_SIZE):
    """Insert records batch by batch, one transaction per batch; returns
    {source_dataset: {count: n}}."""
    counts = defaultdict(Counter)
    batch = []
    with conn.cursor() as cursor:
        confidence_columns = {t: has_confidence(cursor, t) for t in ("case_outcome", "case_status")}
    conn.rollback()

    def flush():
        if not batch:
            return
        with conn.cursor() as cursor:
            _load_batch(cursor, batch, counts, confidence_columns)
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
        log.info("case context load %s: %s", dataset, dict(sorted(c.items())))
    return {dataset: {k: v for k, v in c.items() if v} for dataset, c in counts.items()}


def load_artifact(conn, path, batch_size: int = BATCH_SIZE):
    """Load one JSONL artifact file; see load_records."""
    return load_records(conn, read_jsonl(path), batch_size=batch_size)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load case outcome / status artifacts")
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f"environment variable {args.dsn_env} is not set")
    import psycopg2

    logging.basicConfig(level=logging.INFO)
    conn = psycopg2.connect(dsn)
    try:
        result = {path: load_artifact(conn, path) for path in args.paths}
    finally:
        conn.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
