# Database

`schema.sql` is the DDL for the Postgres store this ETL loads into (issue #42). It defines three schemas:

- **`cle_v2`** — the live application schema. All tables the ETL and the `citations`/`citations-api` frontend read and write live here: `cases` (+ per-source detail tables `rs_document`, `cjeu_document`, `cjeu_national_document`, `echr_document`), `case_text` (full text + summary + tsvector/embedding columns), `case_citation`, `case_segment`, `case_summary_version`, `network_snapshot`/`case_network_metric`/`case_cluster*`, plus `legislation`/`legal_provision`/`legislation_alias`/`case_law_reference` populated from LIDO by `lido_sqlite_build`'s merge step (`airflow/dags/lido/tasks/merge_into_cle.py`) — no separate LIDO database or schema.
- **`legacy`** — holding schema from the DynamoDB → Postgres data migration (issue #42's already-completed migration script/data-validation steps). Not written to by this ETL going forward.
- **`public`** — Airflow's own metadata (managed by Airflow itself). Unrelated to `cle_v2`.

Requires the `vector` extension (pgvector) for `case_text.summary_embedding` / `case_segment.embedding` and their `hnsw` indexes.

Future schema changes belong in `db/migrations/` (not yet created) rather than hand-editing `schema.sql` in place, once this schema is live in production.

## Local dev

The `cle-postgres` service in `docker-compose.yaml` initializes a local Postgres from this file for development and DAG testing, separate from Airflow's own `postgres` service. Point the Airflow connection `pg_cle` at it.
