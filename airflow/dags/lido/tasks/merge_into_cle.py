"""Merge lido.db's law_element/case_law/law_alias/metadata tables into cle_v2.

lido.db is built by the lido_sqlite_build DAG (rechtspraak-lido-sqlite package,
which now parses law elements and resolves case-law links itself -- see that
package's src/parse.py). This task reads it and merges into the cle_v2 tables
that already model the same concepts (legislation/legal_provision/
legislation_alias/case_law_reference/cases), rather than a separate pg_lido
database (issue: two independent, redundant downloads+parses of the same
12GB export, and duplicate table pairs within the same schema).

Staged via ephemeral cle_v2._lido_stage_* tables (COPY is much faster than a
per-row Python upsert loop at this volume -- comparable to lido_sqlite_build's
own ~3.7M metadata rows), then merged with plain INSERT...SELECT...JOIN...
ON CONFLICT statements. Safe to rerun: every insert is idempotent, and the
`cases` touch is an enrichment UPDATE (skip-if-missing, never inserts new
case rows -- an ECLI only in the LIDO export but not yet extracted by
rechtspraak_etl is left alone, matching the precedent the old
lido_reference_loader.py already set for exactly this situation).
"""

import logging
import os
import subprocess
import tempfile

from airflow.providers.postgres.hooks.postgres import PostgresHook
from data_loading.clients.postgres import CONN_PG_CLE, SCHEMA

# (columns, select_sql, chunk_source_table). chunk_source_table is set only
# for case_law -- at ~11M rows it's an order of magnitude bigger than
# everything else here, and dumping it in one continuous scan (whether via
# Python's sqlite3 module or the sqlite3 CLI, batched/committed or not) was
# what reliably got this OOM-killed, independent of host memory load: it
# reads several GB out of a 12.9GB db file fast enough to spike page-cache
# growth past whatever headroom exists. Chunking by rowid range spreads that
# I/O over several smaller bursts instead of one continuous one.
_STAGE_TABLES = {
    "_lido_stage_law_element": (
        "type TEXT, bwb_id TEXT, bwb_label_id TEXT, lido_id TEXT, jc_id TEXT, number TEXT, title TEXT",
        "SELECT type, bwb_id, bwb_label_id, lido_id, jc_id, number, title FROM law_element",
        None,
    ),
    "_lido_stage_case_law": (
        "ecli TEXT, law_lido_id TEXT, source TEXT, jc_id TEXT, opschrift TEXT",
        "SELECT ecli, law_lido_id, source, jc_id, opschrift FROM case_law "
        "WHERE rowid BETWEEN {lo} AND {hi}",
        "case_law",
    ),
    "_lido_stage_law_alias": (
        "alias TEXT, bwb_id TEXT, source TEXT",
        "SELECT alias, bwb_id, source FROM law_alias",
        None,
    ),
    "_lido_stage_cases": (
        "ecli TEXT, title TEXT, date_decision TEXT",
        "SELECT ecli, title, date_decision FROM metadata WHERE ecli != ''",
        None,
    ),
}

_CHUNK_SIZE = 100_000

_MERGE_SQL = f"""
-- 1. legislation (type='wet' rows). cle_v2 holds one legislation row per BWB
--    act (production: 265k rows, none sharing an identifier, most without a
--    lido_id), while LIDO has a 'wet' element per version of an act. Keying
--    on lido_id alone inserted a second row per version for acts that already
--    exist, so the latest LIDO version is attached to the act's row by BWB id
--    and only acts cle_v2 does not have yet are inserted.
-- 1a. existing acts take their latest LIDO version
UPDATE {SCHEMA}.legislation l
SET lido_id = v.lido_id, jc_id = v.jc_id, title = COALESCE(NULLIF(v.title, ''), l.title)
FROM (
    SELECT DISTINCT ON (bwb_id) bwb_id, lido_id, jc_id, title
    FROM {SCHEMA}._lido_stage_law_element
    WHERE type = 'wet' AND bwb_id <> ''
    ORDER BY bwb_id, lido_id DESC
) v
WHERE l.id = (SELECT min(o.id) FROM {SCHEMA}.legislation o
              WHERE o.scheme = 'bwb' AND o.identifier = v.bwb_id)
  AND l.lido_id IS DISTINCT FROM v.lido_id
  -- Databases loaded by the earlier merge hold a row per version, and there the
  -- latest version already has its row and nothing is changed.
  AND NOT EXISTS (SELECT 1 FROM {SCHEMA}.legislation o WHERE o.lido_id = v.lido_id);

-- 1b. acts cle_v2 does not have yet
INSERT INTO {SCHEMA}.legislation (identifier, scheme, title, lido_id, jc_id)
SELECT v.bwb_id, 'bwb', v.title, v.lido_id, v.jc_id
FROM (
    SELECT DISTINCT ON (bwb_id) bwb_id, lido_id, jc_id, title
    FROM {SCHEMA}._lido_stage_law_element
    WHERE type = 'wet' AND bwb_id <> ''
    ORDER BY bwb_id, lido_id DESC
) v
WHERE NOT EXISTS (
    SELECT 1 FROM {SCHEMA}.legislation l WHERE l.scheme = 'bwb' AND l.identifier = v.bwb_id)
ON CONFLICT (lido_id) DO UPDATE SET title = EXCLUDED.title, identifier = EXCLUDED.identifier;

-- 2. legal_provision (everything else), legislation_id resolved by bwb_id
INSERT INTO {SCHEMA}.legal_provision
    (legislation_id, element_type, article_label, bwb_label_id, lido_id, jc_id, title)
SELECT leg.id, le.type, le.number, NULLIF(le.bwb_label_id, '')::bigint, le.lido_id, le.jc_id, le.title
FROM {SCHEMA}._lido_stage_law_element le
LEFT JOIN LATERAL (
    SELECT id FROM {SCHEMA}.legislation
    WHERE scheme = 'bwb' AND identifier = le.bwb_id
    ORDER BY lido_id DESC LIMIT 1
) leg ON true
WHERE le.type != 'wet'
ON CONFLICT (lido_id) DO UPDATE SET title = EXCLUDED.title, legislation_id = EXCLUDED.legislation_id;

-- 3. legislation_alias
INSERT INTO {SCHEMA}.legislation_alias (legislation_id, alias, source)
SELECT leg.id, la.alias, la.source
FROM {SCHEMA}._lido_stage_law_alias la
JOIN LATERAL (
    SELECT id FROM {SCHEMA}.legislation
    WHERE scheme = 'bwb' AND identifier = la.bwb_id
    ORDER BY lido_id DESC LIMIT 1
) leg ON true
ON CONFLICT (legislation_id, alias) DO NOTHING;

-- 4. cases enrichment (skip-if-missing: never inserts, only fills gaps on rows
--    rechtspraak_etl already loaded). Only rows with a gap are touched: an
--    UPDATE of every matched case rewrote millions of unchanged rows.
UPDATE {SCHEMA}.cases c
SET title = COALESCE(c.title, NULLIF(s.title, '')),
    date_decision = COALESCE(c.date_decision, NULLIF(s.date_decision, '')::date)
FROM {SCHEMA}._lido_stage_cases s
WHERE c.ecli = s.ecli
  AND ((c.title IS NULL AND NULLIF(s.title, '') IS NOT NULL)
       OR (c.date_decision IS NULL AND NULLIF(s.date_decision, '') IS NOT NULL));

-- 5. case_law_reference. Production holds LIDO's references from the legacy
--    ETL as one row per case and target labelled rs_lido-both (LIDO's ref and
--    linkt links together, 4.2M rows), plus 125k legacy rs_lido_linkt rows.
--    Writing one row per LIDO link type under new names would store most
--    references two or three times, so: one row per case and target, labelled
--    rs_lido-both, and only where no LIDO-sourced reference to that target
--    exists yet under any of these names. Legacy rows identify their target
--    by BWB id and article (raw_resource, raw_subdivision) and carry a
--    provision_id for only about 80 percent, so a target matches on provision_id or on
--    BWB id + article label (provision) / on legislation_id or BWB id (law).

-- 5a. legislation-target
INSERT INTO {SCHEMA}.case_law_reference (case_id, legislation_id, raw_reference, role, source_dataset)
SELECT DISTINCT ON (c.id, leg.id) c.id, leg.id, cl.opschrift, 'cited', 'rs_lido-both'
FROM {SCHEMA}._lido_stage_case_law cl
JOIN {SCHEMA}.cases c ON c.ecli = cl.ecli
-- A reference names one version of an act, cle_v2 keeps one row per act.
JOIN {SCHEMA}._lido_stage_law_element le ON le.lido_id = cl.law_lido_id AND le.type = 'wet'
JOIN LATERAL (
    SELECT id, identifier FROM {SCHEMA}.legislation
    WHERE scheme = 'bwb' AND identifier = le.bwb_id
    ORDER BY lido_id DESC NULLS LAST LIMIT 1
) leg ON true
WHERE NOT EXISTS (
    SELECT 1 FROM {SCHEMA}.case_law_reference x
    WHERE x.case_id = c.id
      AND x.source_dataset IN ('rs_lido-both', 'rs_lido_linkt', 'rs_lido_ref', 'rs_lido_custom')
      AND (x.legislation_id = leg.id OR x.raw_resource = leg.identifier))
ORDER BY c.id, leg.id, cl.opschrift NULLS LAST
-- The predicate names the partial index this arbiter is meant to hit. See the
-- note on upsert_citation in data_loading/clients/postgres.py: db/schema.sql
-- declares case_law_reference_uk_legislation unqualified, the Coolify bundle's
-- migration declares it WHERE-qualified, and only the qualified form is
-- inferable on both.
ON CONFLICT (case_id, legislation_id, role, source_dataset)
    WHERE provision_id IS NULL AND legislation_id IS NOT NULL AND raw_resource IS NULL
DO NOTHING;

-- 5b. provision-target
INSERT INTO {SCHEMA}.case_law_reference (case_id, provision_id, raw_reference, role, source_dataset)
SELECT DISTINCT ON (c.id, lp.id) c.id, lp.id, cl.opschrift, 'cited', 'rs_lido-both'
FROM {SCHEMA}._lido_stage_case_law cl
JOIN {SCHEMA}.cases c ON c.ecli = cl.ecli
JOIN {SCHEMA}.legal_provision lp ON lp.lido_id = cl.law_lido_id
LEFT JOIN {SCHEMA}.legislation leg ON leg.id = lp.legislation_id
WHERE NOT EXISTS (
    SELECT 1 FROM {SCHEMA}.case_law_reference x
    WHERE x.case_id = c.id
      AND x.source_dataset IN ('rs_lido-both', 'rs_lido_linkt', 'rs_lido_ref', 'rs_lido_custom')
      AND (x.provision_id = lp.id
           OR (x.raw_resource = leg.identifier AND x.raw_subdivision = lp.article_label)))
ORDER BY c.id, lp.id, cl.opschrift NULLS LAST
ON CONFLICT (case_id, provision_id, role, source_dataset)
    WHERE provision_id IS NOT NULL AND raw_resource IS NULL
DO NOTHING;
"""


def _dump_table_to_csv(lido_db_path: str, select_sql: str, csv_path: str) -> int:
    """Dumps select_sql's results to a CSV file on disk via the sqlite3 CLI,
    rather than iterating rows through Python's sqlite3 module and building
    CSV in memory. Iterating an ~11M-row table (case_law) that way -- even
    committed in small batches -- reliably got the process OOM-killed
    (confirmed independent of host memory pressure: still failed at the same
    point with 21GB free after the first, host-load-related failures were
    ruled out). Streaming a query straight to a file, entirely outside this
    process's own memory, is what the original (never-run) lido_postgres DAG
    did successfully at this same scale via `sqlite3 ... -csv "SELECT ..." >
    file.csv`; this mirrors that proven approach instead of reinventing a
    Python-side one."""
    with open(csv_path, "wb") as f:
        subprocess.run(
            ["sqlite3", "-readonly", "-csv", lido_db_path, select_sql],
            stdout=f,
            stderr=subprocess.PIPE,
            check=True,
        )
    with open(csv_path, "rb") as f:
        return sum(1 for _ in f)


def _copy_table_from_csv(pg_cursor, table: str, csv_path: str) -> None:
    with open(csv_path, "rb") as f:
        pg_cursor.copy_expert(
            sql=f"COPY {SCHEMA}.{table} FROM STDIN WITH (FORMAT csv, NULL '')", file=f
        )


def _row_id_bounds(lido_db_path: str, table: str) -> tuple[int, int] | None:
    result = subprocess.run(
        ["sqlite3", "-readonly", "-csv", lido_db_path, f"SELECT MIN(rowid), MAX(rowid) FROM {table}"],
        capture_output=True,
        text=True,
        check=True,
    )
    lo, hi = result.stdout.strip().split(",")
    if not lo or not hi:
        return None
    return int(lo), int(hi)


def merge_lido_db_into_cle_v2(lido_db_path: str) -> None:
    pg_conn = PostgresHook(postgres_conn_id=CONN_PG_CLE).get_conn()
    pg_cursor = pg_conn.cursor()

    try:
        with tempfile.TemporaryDirectory(dir=os.path.dirname(lido_db_path)) as tmp_dir:
            # Staging tables are dropped up front (idempotent even if a
            # previous run died partway and left them behind) and committed
            # per table (per chunk, for case_law), so this whole phase can't
            # accumulate one giant uncommitted transaction.
            for table, (columns, select_sql, chunk_source) in _STAGE_TABLES.items():
                pg_cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table}")
                pg_cursor.execute(f"CREATE TABLE {SCHEMA}.{table} ({columns})")
                pg_conn.commit()

                total_written = 0
                bounds = _row_id_bounds(lido_db_path, chunk_source) if chunk_source else None
                if bounds is None:
                    windows = [select_sql]
                else:
                    lo, hi = bounds
                    windows = [
                        select_sql.format(lo=start, hi=min(start + _CHUNK_SIZE - 1, hi))
                        for start in range(lo, hi + 1, _CHUNK_SIZE)
                    ]

                for window_sql in windows:
                    csv_path = os.path.join(tmp_dir, f"{table}.csv")
                    written = _dump_table_to_csv(lido_db_path, window_sql, csv_path)
                    _copy_table_from_csv(pg_cursor, table, csv_path)
                    pg_conn.commit()
                    os.remove(csv_path)
                    total_written += written
                    if len(windows) > 1:
                        logging.info("  ...%d row(s) staged into %s.%s so far", total_written, SCHEMA, table)

                logging.info("Staged %d row(s) into %s.%s", total_written, SCHEMA, table)

        # The merge itself is one transaction: every statement in it is
        # idempotent (ON CONFLICT), so a failure here just needs a rerun,
        # not a rollback-then-redo of the (already-committed) staging step.
        pg_cursor.execute(_MERGE_SQL)
        pg_conn.commit()

        for table in _STAGE_TABLES:
            pg_cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table}")
        pg_conn.commit()
    finally:
        pg_cursor.close()
        pg_conn.close()
