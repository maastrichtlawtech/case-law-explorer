"""
Load a law-reference artifact (data_extraction/linking/law_artifact.py) into
case_law_reference (roadmap R3.2-R3.4). The single entry point for every
law-reference file: load_artifact hands echr_article files (Phase 3a) to
legislation_loader. Insert-only, like link_loader:

  * the citing case is looked up by ECLI, then CELEX, then item_id (the same
    lookup as link_loader); a record whose case is missing is counted and
    skipped;
  * the act is resolved to ``legislation`` by (target scheme, identifier),
    then each alternative identifier in order, then legislation_alias rows
    with source 'curated' naming one of those identifiers; the lowest id wins
    when several rows match;
  * with an article, legal_provision (element_type 'article', same
    legislation, article_label equal ignoring case) gives provision_id;
  * a resolved row keeps raw_scheme / raw_resource / raw_subdivision and goes in
    under case_law_reference_uk_resolved_ref (0014); an unresolved one
    (legislation absent) has raw_* only and goes in under
    case_law_reference_uk_raw (0001), so it can be resolved by a later run,
    which adds the resolved row next to it (the unresolved row stays: nothing
    is updated);
  * both statements name their unique index with its predicate restated, so
    they work against the deployed (partial) indexes and db/schema.sql alike.

Nothing is updated or deleted; a dataset is removed with one
``DELETE FROM case_law_reference WHERE source_dataset = ...``. Returns counts
per source_dataset: inserted (resolved), inserted_unresolved, existing,
source_missing, with_provision.

CLI:
    python -m data_loading.law_reference_loader load --dsn-env VAR PATH [PATH ...]
"""

import argparse
import json
import logging
import os
from collections import Counter, defaultdict
from types import SimpleNamespace
from typing import Iterable

from data_extraction.linking.law_artifact import LAW_DATASETS, LawReferenceRecord, read_jsonl
from data_loading.link_loader import _cases_by_key, _resolve

log = logging.getLogger(__name__)

# Weekly switch for law-reference extraction (linking_tasks) and for resolving
# new Cellar CDM law references at insert (cjeu_loader). Default off: with it
# off, the DAGs and the CJEU load behave exactly as before.
FLAG = "LAW_REFERENCE_EXTRACTION_ENABLED"
_TRUE = ("1", "true", "yes", "on")


def enabled() -> bool:
    value = os.environ.get(FLAG)
    return bool(value and value.strip().lower() in _TRUE)


SCHEMA = "cle_v2"
BATCH_SIZE = 2000
ALIAS_SOURCE = "curated"
PROVISION_ELEMENT = "article"

# Columns added by caselaw-coolify 0012 (provenance); the loader refuses to run
# without them rather than write rows nobody can attribute to a version.
PROVENANCE_COLUMNS = ("extractor_version", "match_method", "confidence")


# The datasets case_law_reference_uk_resolved_ref (0014) covers: the three law
# datasets and cellar_sparql (cjeu_loader resolves new CDM law references at
# insert when LAW_REFERENCE_EXTRACTION_ENABLED is on). The ON CONFLICT
# predicates below restate the index predicate word for word.
INDEX_DATASETS = ("cellar_sparql",) + LAW_DATASETS


def datasets_sql() -> str:
    for name in INDEX_DATASETS:
        assert "'" not in name
    return "(" + ", ".join(f"'{d}'" for d in INDEX_DATASETS) + ")"


_COLUMNS = (
    ("case_id", "bigint"),
    ("legislation_id", "bigint"),
    ("provision_id", "bigint"),
    ("raw_scheme", "text"),
    ("raw_resource", "text"),
    ("raw_subdivision", "text"),
    ("raw_reference", "text"),
    ("role", "text"),
    ("source_dataset", "text"),
    ("extractor_version", "text"),
    ("match_method", "text"),
    ("confidence", "real"),
)
_COLUMN_LIST = ", ".join(c for c, _t in _COLUMNS)
_TEMPLATE = "(" + ", ".join(["%s::integer"] + [f"%s::{t}" for _c, t in _COLUMNS]) + ")"
_KEY = "(case_id, raw_scheme, raw_resource, COALESCE(raw_subdivision, ''), role, source_dataset)"

# case_law_reference_uk_resolved_ref (caselaw-coolify 0014).
RESOLVED_PREDICATE = (
    "raw_resource IS NOT NULL AND (legislation_id IS NOT NULL OR provision_id IS NOT NULL) "
    f"AND source_dataset IN {datasets_sql()}"
)
# case_law_reference_uk_raw (caselaw-coolify 0001).
UNRESOLVED_PREDICATE = (
    "provision_id IS NULL AND legislation_id IS NULL AND raw_resource IS NOT NULL"
)


def _insert_sql(predicate):
    return f"""
        INSERT INTO {SCHEMA}.case_law_reference ({_COLUMN_LIST})
        SELECT {_COLUMN_LIST} FROM (VALUES %s) AS v(ord, {_COLUMN_LIST})
         ORDER BY ord
        ON CONFLICT {_KEY} WHERE {predicate}
        DO NOTHING
        RETURNING source_dataset, provision_id
    """


_INSERT_RESOLVED = _insert_sql(RESOLVED_PREDICATE)
_INSERT_UNRESOLVED = _insert_sql(UNRESOLVED_PREDICATE)

_LEGISLATION_SQL = f"""
    SELECT scheme, identifier, min(id)
      FROM {SCHEMA}.legislation
     WHERE scheme = ANY(%s) AND identifier = ANY(%s)
     GROUP BY scheme, identifier
"""
_ALIAS_SQL = f"""
    SELECT a.alias, min(a.legislation_id)
      FROM {SCHEMA}.legislation_alias a
      JOIN {SCHEMA}.legislation l ON l.id = a.legislation_id
     WHERE a.source = %s AND a.alias = ANY(%s)
     GROUP BY a.alias
"""
_PROVISION_SQL = f"""
    SELECT legislation_id, lower(article_label), min(id)
      FROM {SCHEMA}.legal_provision
     WHERE legislation_id = ANY(%s) AND element_type = %s AND lower(article_label) = ANY(%s)
     GROUP BY legislation_id, lower(article_label)
"""
_COLUMNS_SQL = """
    SELECT column_name FROM information_schema.columns
     WHERE table_schema = %s AND table_name = 'case_law_reference'
"""


def check_schema(conn):
    """Raise when case_law_reference lacks the provenance columns (0012)."""
    with conn.cursor() as cursor:
        cursor.execute(_COLUMNS_SQL, (SCHEMA,))
        present = {row[0] for row in cursor.fetchall()}
    conn.rollback()
    missing = [c for c in PROVENANCE_COLUMNS if c not in present]
    if missing:
        raise RuntimeError(
            f"{SCHEMA}.case_law_reference lacks {missing}: apply caselaw-coolify 0012 and 0014 "
            "before loading law references"
        )


def _resolve_acts(cursor, records):
    """{(scheme, identifier tuple): legislation_id} for every record target."""
    schemes = sorted({r.target.scheme for r in records})
    identifiers = sorted({i for r in records for i in r.target.identifiers})
    direct, aliases = {}, {}
    if identifiers:
        cursor.execute(_LEGISLATION_SQL, (schemes, identifiers))
        direct = {(scheme, ident): lid for scheme, ident, lid in cursor.fetchall()}
        cursor.execute(_ALIAS_SQL, (ALIAS_SOURCE, identifiers))
        aliases = dict(cursor.fetchall())
    resolved = {}
    for record in records:
        key = (record.target.scheme, record.target.identifiers)
        if key in resolved:
            continue
        found = next(
            (direct[(key[0], i)] for i in key[1] if (key[0], i) in direct),
            None,
        )
        if found is None:
            found = next((aliases[i] for i in key[1] if i in aliases), None)
        resolved[key] = found
    return resolved


def _resolve_provisions(cursor, wanted):
    """wanted: {(legislation_id, article_lower)} -> {same: provision_id}."""
    if not wanted:
        return {}
    cursor.execute(
        _PROVISION_SQL,
        (
            sorted({lid for lid, _a in wanted}),
            PROVISION_ELEMENT,
            sorted({a for _l, a in wanted}),
        ),
    )
    return {(lid, art): pid for lid, art, pid in cursor.fetchall() if (lid, art) in wanted}


def _values(cursor, sql, rows):
    if not rows:
        return []
    from psycopg2.extras import execute_values

    return execute_values(cursor, sql, rows, template=_TEMPLATE, page_size=len(rows), fetch=True)


def _load_batch(cursor, batch, counts):
    found = _cases_by_key(cursor, [SimpleNamespace(source=r.source, target=None) for r in batch])
    acts = _resolve_acts(cursor, batch)
    planned, seen = [], set()
    for record in batch:
        c = counts[record.source_dataset]
        source = _resolve(found, record.source)
        if source is None:
            c["source_missing"] += 1
            continue
        case_id = source[0]
        key = (case_id,) + record.natural_key[1:]
        if key in seen:
            c["duplicate_in_batch"] += 1
            continue
        seen.add(key)
        legislation_id = acts[(record.target.scheme, record.target.identifiers)]
        planned.append((record, case_id, legislation_id))
    provisions = _resolve_provisions(
        cursor,
        {(lid, rec.article.lower()) for rec, _c, lid in planned if lid and rec.article},
    )
    resolved_rows, unresolved_rows = [], []
    for record, case_id, legislation_id in planned:
        provision_id = None
        if legislation_id and record.article:
            provision_id = provisions.get((legislation_id, record.article.lower()))
        raw_reference = record.raw_reference or (
            record.mentions[0].raw_text if record.mentions else None
        )
        row = (
            case_id,
            legislation_id,
            provision_id,
            record.raw_scheme,
            record.raw_resource,
            record.raw_subdivision,
            raw_reference,
            record.role,
            record.source_dataset,
            record.extractor_version,
            record.match_method,
            record.confidence,
        )
        target = resolved_rows if legislation_id else unresolved_rows
        target.append((len(target),) + row)
    for rows, sql, label in (
        (resolved_rows, _INSERT_RESOLVED, "inserted"),
        (unresolved_rows, _INSERT_UNRESOLVED, "inserted_unresolved"),
    ):
        inserted = Counter()
        for dataset, provision_id in _values(cursor, sql, rows):
            inserted[dataset] += 1
            counts[dataset][label] += 1
            if provision_id is not None:
                counts[dataset]["with_provision"] += 1
        planned_per = Counter(row[9] for row in rows)
        for dataset, n in planned_per.items():
            counts[dataset]["existing"] += n - inserted[dataset]


def load_records(conn, records: Iterable[LawReferenceRecord], batch_size: int = BATCH_SIZE):
    """Insert records batch by batch, one transaction per batch; returns
    {source_dataset: {count: n}} (zero counts left out)."""
    check_schema(conn)
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
        log.info("law reference load %s: %s", dataset, dict(sorted(c.items())))
    return {dataset: {k: v for k, v in c.items() if v} for dataset, c in counts.items()}


# The other law-reference artifact: ECHR article references (Phase 3a,
# data_extraction/legislation/law_reference.py), which name a provision of an
# act the curated fixture holds and are loaded by data_loading.legislation_loader
# (provisions created insert-only, rows under case_law_reference_uk_provision /
# _uk_legislation with raw_resource NULL). Its record shape and arbiter indexes
# differ from this module's, so it keeps its own reader and loader; load_artifact
# routes a file by the source_dataset of its first record, so the promoter
# replays every 'law_references' file through this one entry point.
from data_extraction.legislation.law_reference import DATASETS as PROVISION_DATASETS  # noqa: E402

# Every source dataset a law-reference file may carry; the two lists are disjoint.
ALL_DATASETS = LAW_DATASETS + PROVISION_DATASETS


def artifact_dataset(path):
    """source_dataset of the file's first record, or None for an empty file."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    return json.loads(line).get("source_dataset")
                except (ValueError, AttributeError):
                    return None
    return None


def _without_records(path) -> bool:
    with open(path, encoding="utf-8") as handle:
        return not any(line.strip() for line in handle)


def load_artifact(conn, path, batch_size: int = BATCH_SIZE):
    """Load one JSONL law-reference artifact of any of ALL_DATASETS; see
    load_records, or legislation_loader.load_law_references for echr_article.
    A file without records loads nothing and checks no schema, so an empty
    echr_article file loads where 0012 is not applied yet (its loader needs
    only 0011)."""
    dataset = artifact_dataset(path)
    if dataset is None and _without_records(path):
        return {}
    if dataset in PROVISION_DATASETS:
        from data_loading import legislation_loader

        return legislation_loader.load_law_reference_artifact(conn, path, batch_size=batch_size)
    return load_records(conn, read_jsonl(path), batch_size=batch_size)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _connect(dsn_env, readonly=False):
    import psycopg2

    dsn = os.environ.get(dsn_env)
    if not dsn:
        raise SystemExit(f"environment variable {dsn_env} is not set")
    conn = psycopg2.connect(dsn)
    if readonly:
        conn.set_session(readonly=True)
    return conn


def run_cli(extract, description, argv=None):
    """The law-reference extractors' backfill CLI over a cases.id range:
    ``--dsn-env VAR --from-id N --to-id M --out PATH [--load]``. Without
    --load the connection is read-only and only the artifact is written."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    parser.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    parser.add_argument("--case-id", type=int, action="append", default=None)
    parser.add_argument("--out", required=True, help="JSONL artifact to write")
    parser.add_argument("--load", action="store_true", help="also load the artifact into the DSN")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = _connect(args.dsn_env, readonly=not args.load)
    try:
        result = {
            "extract": extract(
                conn,
                case_ids=args.case_id,
                id_range=(args.from_id, args.to_id),
                out_path=args.out,
            )
        }
        if args.load:
            result["load"] = load_artifact(conn, args.out)
    finally:
        conn.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load law-reference artifacts (R3.2-R3.4).")
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load", help="load JSONL law-reference artifacts")
    load.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    load.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    load.add_argument("paths", nargs="+", help="artifact files")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = _connect(args.dsn_env)
    try:
        result = {
            str(path): load_artifact(conn, path, batch_size=args.batch_size) for path in args.paths
        }
    finally:
        conn.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
