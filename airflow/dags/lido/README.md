# Lido -> cle_v2 merge

This used to be a standalone DAG (`lido_postgres`) that independently
downloaded and parsed the same 12GB LIDO export (`lido-export.ttl.gz`,
<https://data.overheid.nl/dataset/linked-data-overheid>) as `lido_sqlite_build`,
into a separate database (`pg_lido`) with its own `legal_case`/`law_element`/
`case_law`/`law_alias` tables -- near-duplicates of `cle_v2.cases`/
`legislation`/`legal_provision`/`case_law_reference`/`legislation_alias`,
which were sitting empty and unwired.

All of that parsing now lives in the `rechtspraak-lido-sqlite` package itself
(see that package's `src/parse.py`, `src/bwbidlist.py`): one download, one
pass over the export, populating `law_element`/`case_law`/`law_alias` in the
same `lido.db` that `rechtspraak_extractor` already reads for case metadata
and citations.

What's left here is just the merge step: `tasks/merge_into_cle.py`, run as
the last task in the `lido_sqlite_build` DAG (`airflow/dags/lido_sqlite_build.py`),
after `lido.db` is fully built. It stages `lido.db`'s `law_element`/
`case_law`/`law_alias`/`metadata` tables into ephemeral `cle_v2._lido_stage_*`
tables (via `COPY`, not a per-row loop -- comparable row counts to
`lido_sqlite_build`'s own ~3.7M metadata rows), then merges into `cle_v2`
with plain `INSERT ... SELECT ... JOIN ... ON CONFLICT` statements:

- `law_element` rows where `type='wet'` -> `legislation`
- everything else -> `legal_provision` (`legislation_id` resolved by `bwb_id`)
- `law_alias` -> `legislation_alias` (resolved by `bwb_id`)
- `metadata` -> enrichment-only `UPDATE` on `cases` (skip-if-missing: never
  inserts a case row, only fills gaps on ECLIs `rechtspraak_etl` already
  loaded)
- `case_law` -> `case_law_reference` (two statements, one per conflict index:
  legislation-target and provision-target)

Idempotent and safe to rerun -- every insert conflicts on an existing unique
key, and the `cases` touch never creates rows.

Uses the same `pg_cle` Airflow connection as every other DAG that writes to
`cle_v2` (`data_loading/clients/postgres.py`) -- no separate `pg_lido`
connection anymore.
