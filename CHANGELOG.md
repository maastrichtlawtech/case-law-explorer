# Changelog

Notable changes to the case-law-explorer ETL and database, in human-readable
form. Not every commit is listed — this tracks changes that affect schema,
data, or how the pipeline is operated, grouped by theme rather than by date.

## LIDO pipeline consolidation

Two independent DAGs used to both download and parse the same ~12GB LIDO
Linked Data export (`lido-export.ttl.gz`):

- `lido_sqlite_build`, which used the `rechtspraak-lido-sqlite` package to
  parse case metadata and citations into a local `lido.db` SQLite file, and
- `lido_postgres` (`airflow/dags/lido/`), which independently re-downloaded
  and re-parsed the same export to resolve law-element hierarchy and
  case-to-law citation links, targeting a `pg_lido` Postgres connection that
  was never actually created — so this DAG had never run in practice.

Consolidated into a single pipeline:

- **`rechtspraak-lido-sqlite`** (external package, local clone at
  `../rechtspraak-lido-sqlite`, bumped `0.1.1` → `0.2.0`) now parses
  everything in one streaming pass over the export: case metadata (as
  before), plus law-element hierarchy (`law_element` table) and BWB aliases
  (`law_alias` table, via a new `src/bwbidlist.py` module downloading
  `BWBIdList.xml.zip`). A second in-package pass (`resolve_case_law_links`)
  decomposes each case's raw `refereertAan`/`linkt` predicate values and
  writes clean citation links into a new `case_law` table, replacing what
  used to be garbled pipe-delimited blobs in `case_citation`.
- **`airflow/dags/lido/`** was rewritten from a full standalone DAG down to a
  single task, `merge_into_cle.py`, appended to the end of the
  `lido_sqlite_build` DAG. It reads `lido.db`'s new tables and merges them
  directly into `cle_v2` (see table mapping below) — no separate database.
  `lido/dag.py`, `lido/config.py`, and everything under `lido/tasks/` and
  `lido/utils/` for the old standalone parse/convert steps were deleted.
- `rechtspraak_etl.py` no longer calls `lido_reference_loader.py`, which
  bridged the never-created `pg_lido` into `case_law_reference`;
  `lido_reference_loader.py` is marked deprecated (not yet deleted, pending a
  spot-check of `case_law_reference` coverage).

### Old table → current table mapping

| Old `lido_postgres` target | Now lands in |
|---|---|
| `legal_case` | `cle_v2.cases` (enrichment `UPDATE` only, never inserts) |
| `law_element` (type=`wet`) | `cle_v2.legislation` |
| `law_element` (everything else) | `cle_v2.legal_provision` |
| `case_law` | `cle_v2.case_law_reference` |
| `law_alias` | `cle_v2.legislation_alias` |

`lido.db`'s own `law_element`/`case_law`/`law_alias`/`metadata` tables are
transient: staged into `cle_v2._lido_stage_*` and dropped after every merge.

### Bugs found and fixed along the way

- `resolve_case_law_links` originally re-resolved each citation with a fresh
  SQL lookup per row; against real data (3.7M cases) this projected to
  36+ hours. Replaced with an in-memory index (`_LawIndex`) built from one
  full-table scan of `law_element` — brought the same pass down to ~2
  minutes.
- Made `resolve_case_law_links` resumable: a raw `refereertAan` value always
  contains `|`, a cleaned one never does, so a rerun after an interruption
  skips already-processed rows instead of wiping them.
- `bwbidlist.py`'s `zip_path.with_suffix(".xml")` on `BWBIdList.xml.zip`
  produced `BWBIdList.xml.xml` (only the last suffix is replaced) instead of
  `BWBIdList.xml`; fixed to `zip_path.parent / "BWBIdList.xml"`.
- `legal_provision.jc_id` / `legislation.jc_id` had `UNIQUE` constraints that
  don't hold in real LIDO data (distinct dated `lido_id` nodes can share a
  jci1.3 reference); dropped both constraints, keeping `lido_id` as the true
  natural key.

## Database schema (`db/schema.sql`)

- Fixed `CREATE VIEW ... TABLESPACE cle_v2 AS` (invalid syntax — `TABLESPACE`
  doesn't apply to views) across all 6 views.
- Seeded `cle_v2.language` with all 24 official EU language ISO codes; it was
  empty and `case_text` inserts were failing its FK check.
- Added a real unique index, `legislation_alias_uk` on
  `(legislation_id, alias)` — the table previously had none.
- Dropped `legal_provision_jc_id_key` / `legislation_jc_id_key` (see above).

## Operations

- `docker-compose.yaml`: capped `AIRFLOW__CELERY__WORKER_CONCURRENCY` (16 → 2)
  and `AIRFLOW__WEBSERVER__WORKERS` (4 → 2). The default pool sizes are meant
  for a multi-user production install; on this single-node dev host, the
  idle worker/gunicorn processes were sitting in swap and contributed to
  repeated host-level OOM kills during large data-loading tasks (e.g.
  staging `case_law`'s 11.36M rows) — confirmed via `/proc/<pid>/status`
  RSS polling that the loading code itself was never the memory hog.

## Documentation

- `ARCHITECTURE.md`, `db/README.md`, `docs/setup/README.md`: removed
  references to the `pg_lido` Postgres connection/schema and the standalone
  `lido_postgres` DAG, updated the storage-layer diagram to reflect the
  single-`cle_v2`-schema design.
- `airflow/dags/lido/README.md`: rewritten to describe the new
  merge-only role of this directory.

## Known follow-ups (not yet done)

- `airflow/requirements.txt` still pins `rechtspraak-lido-sqlite==0.1.1`;
  `0.2.0` is installed manually in the running container and will be lost on
  the next container recreation until this is bumped and the package is
  actually published.
- `lido_reference_loader.py` / `citation_update.py` are deprecated but not
  deleted.
- ~78% of `legal_provision` rows have a NULL `legislation_id`, because most
  BWB regelingen aren't RDF-typed `Wet` and the current law-element type map
  doesn't cover their actual top-level type.
- `legal_provision.parent_id` hierarchy (`isOnderdeelVan` /
  `isOnderdeelVanRegeling`) is not extracted by either the old or new
  parsing logic.
