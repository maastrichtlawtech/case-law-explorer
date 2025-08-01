from airflow.providers.postgres.hooks.postgres import PostgresHook

from dags.lido.config import TBL_CASE_LAW, TBL_CASES, TBL_LAW_ALIAS, TBL_LAWS

SQL_CREATE_STAGING_TABLES = f"""
    CREATE TABLE IF NOT EXISTS {TBL_CASES}_staging (
        id SERIAL PRIMARY KEY,
        -- ecli_id TEXT UNIQUE NOT NULL,
        ecli_id TEXT NOT NULL,
        title TEXT,
        -- celex_id TEXT UNIQUE,
        celex_id TEXT,
        zaaknummer TEXT,
        uitspraakdatum DATE
    );

    CREATE TABLE IF NOT EXISTS {TBL_LAWS}_staging (
        id SERIAL PRIMARY KEY,
        type TEXT CHECK (type IN ('wet', 'boek', 'deel', 'titeldeel', 'hoofdstuk', 'artikel', 'paragraaf', 'subparagraaf', 'afdeling')),
        bwb_id TEXT,
        bwb_label_id BIGINT,
        -- lido_id TEXT UNIQUE,
        lido_id TEXT,
        -- jc_id TEXT UNIQUE,
        jc_id TEXT,
        number TEXT,
        title TEXT
    );

    CREATE TABLE IF NOT EXISTS {TBL_CASE_LAW}_staging (
        id SERIAL PRIMARY KEY,
        case_id INTEGER,
        law_id INTEGER,
        source TEXT CHECK (source IN ('lido-ref', 'lido-linkt', 'custom')),
        jc_id TEXT,
        lido_id TEXT,
        opschrift TEXT,
        -- FOREIGN KEY (case_id) REFERENCES legal_case(id),
        -- FOREIGN KEY (law_id) REFERENCES law_element(id)
    );

    CREATE TABLE IF NOT EXISTS {TBL_LAW_ALIAS}_staging (
        id SERIAL PRIMARY KEY,
        alias TEXT NOT NULL,
        bwb_id TEXT NOT NULL,
        source TEXT CHECK (source IN ('opschrift', 'bwbidlist'))
    );
"""

SQL_SWAP_TABLES_AND_DEPS = f"""
BEGIN;
    -- rename prod to _prev
    ALTER TABLE {TBL_LAWS} RENAME TO {TBL_LAWS}_prev
    ALTER TABLE {TBL_CASES} RENAME TO {TBL_CASES}_prev
    ALTER TABLE {TBL_CASE_LAW} RENAME TO {TBL_CASE_LAW}_prev
    ALTER TABLE {TBL_LAW_ALIAS} RENAME TO {TBL_LAW_ALIAS}_prev

    -- rename _staging to prod
    ALTER TABLE {TBL_LAWS}_staging RENAME TO {TBL_LAWS}_prev
    ALTER TABLE {TBL_CASES}_staging RENAME TO {TBL_CASES}_prev
    ALTER TABLE {TBL_CASE_LAW}_staging RENAME TO {TBL_CASE_LAW}_prev
    ALTER TABLE {TBL_LAW_ALIAS}_staging RENAME TO {TBL_LAW_ALIAS}_prev

    -- drop constraints from previous
    ALTER TABLE IF EXISTS {TBL_LAWS}_prev DROP CONSTRAINT {TBL_LAWS}_jc_id_key;
    ALTER TABLE IF EXISTS {TBL_LAWS}_prev DROP CONSTRAINT {TBL_LAWS}_lido_id_key;
    ALTER TABLE IF EXISTS {TBL_CASES}_prev DROP CONSTRAINT {TBL_CASES}_celex_id_key;
    ALTER TABLE IF EXISTS {TBL_CASES}_prev DROP CONSTRAINT {TBL_CASES}_ecli_id_key;
    ALTER TABLE IF EXISTS {TBL_CASE_LAW}_prev DROP CONSTRAINT {TBL_CASE_LAW}_case_id_fkey;
    ALTER TABLE IF EXISTS {TBL_CASE_LAW}_prev DROP CONSTRAINT {TBL_CASE_LAW}_law_id_fkey;

    -- drop indexes from previous
    DROP INDEX IF EXISTS idx_{TBL_CASES}_id_ecli;
    DROP INDEX IF EXISTS idx_{TBL_LAWS}_bwb_id;
    DROP INDEX IF EXISTS idx_{TBL_LAWS}_filter;
    DROP INDEX IF EXISTS idx_{TBL_CASE_LAW}_cl;
    DROP INDEX IF EXISTS idx_{TBL_CASE_LAW}_lc;
    DROP INDEX IF EXISTS idx_{TBL_LAW_ALIAS}_uniq;
    DROP INDEX IF EXISTS idx_{TBL_LAW_ALIAS}_index;

    -- add constraints to new
    ALTER TABLE {TBL_LAWS} ADD CONSTRAINT {TBL_LAWS}_jc_id_key UNIQUE (jc_id);
    ALTER TABLE {TBL_LAWS} ADD CONSTRAINT {TBL_LAWS}_lido_id_key UNIQUE (lido_id);
    ALTER TABLE {TBL_CASES} ADD CONSTRAINT {TBL_CASES}_celex_id_key UNIQUE (celex_id);
    ALTER TABLE {TBL_CASES} ADD CONSTRAINT {TBL_CASES}_ecli_id_key UNIQUE (ecli_id);

    ALTER TABLE {TBL_CASE_LAW} ADD CONSTRAINT {TBL_CASE_LAW}_case_id_fkey FOREIGN KEY (case_id) REFERENCES {TBL_CASES} (id);
    ALTER TABLE {TBL_CASE_LAW} ADD CONSTRAINT {TBL_CASE_LAW}_law_id_fkey FOREIGN KEY (law_id) REFERENCES {TBL_LAWS} (id);

    -- add indexes to new
    CREATE INDEX IF NOT EXISTS idx_{TBL_CASES}_id_ecli ON {TBL_CASES} (id, ecli_id);

    CREATE INDEX IF NOT EXISTS idx_{TBL_LAWS}_bwb_id ON {TBL_LAWS} (bwb_id, bwb_label_id);
    CREATE INDEX IF NOT EXISTS idx_{TBL_LAWS}_filter ON {TBL_LAWS} (bwb_id, lower(number), type);

    CREATE INDEX IF NOT EXISTS idx_{TBL_CASE_LAW}_cl ON {TBL_CASE_LAW} (case_id, law_id);
    CREATE INDEX IF NOT EXISTS idx_{TBL_CASE_LAW}_lc ON {TBL_CASE_LAW} (law_id, case_id);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_{TBL_LAW_ALIAS}_uniq ON {TBL_LAW_ALIAS} (bwb_id, LOWER(alias));
    CREATE INDEX IF NOT EXISTS idx_{TBL_LAW_ALIAS}_index ON {TBL_LAW_ALIAS} (lower(alias));
COMMIT;
"""

def task_create_staging_tables():
    hook = PostgresHook(postgres_conn_id="my_pg")
    conn = hook.get_conn()
    cursor = conn.cursor()

    cursor.execute(SQL_CREATE_STAGING_TABLES)

def task_load_csv(table, path):
    hook = PostgresHook(postgres_conn_id="my_pg")
    conn = hook.get_conn()
    cursor = conn.cursor()

    with open(path, "rb") as f:
        cursor.copy_expert(
            sql=f"COPY {table} FROM STDIN WITH CSV HEADER",
            file=f
        )

    conn.commit()

def task_swap(table):
    hook = PostgresHook(postgres_conn_id="my_pg")
    conn = hook.get_conn()
    cursor = conn.cursor()

    cursor.execute(SQL_SWAP_TABLES_AND_DEPS)
