import os
from lido.utils.sqlite import get_conn
from lido.config import FILE_SQLITE_DB, TBL_LAWS, TBL_CASES, TBL_CASE_LAW, TBL_LAW_ALIAS

def task_init_sqlite():

    conn = get_conn(FILE_SQLITE_DB)
    cursor = conn.cursor()
    cursor.executescript(f"""
        CREATE TABLE IF NOT EXISTS {TBL_CASES} (
            id INTEGER PRIMARY KEY,
            ecli_id TEXT UNIQUE NOT NULL,
            title TEXT,
            celex_id TEXT UNIQUE,
            zaaknummer TEXT,
            uitspraakdatum DATE
        );

        CREATE TABLE IF NOT EXISTS {TBL_LAWS} (
            id INTEGER PRIMARY KEY,
            type TEXT CHECK (type IN ('wet', 'boek', 'deel', 'titeldeel', 'hoofdstuk', 'artikel', 'paragraaf', 'subparagraaf', 'afdeling')),
            bwb_id TEXT,
            bwb_label_id INTEGER,
            lido_id TEXT UNIQUE,
            jc_id TEXT UNIQUE,
            number TEXT,
            title TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_bwb_id ON law_element(bwb_id, bwb_label_id);
        CREATE INDEX IF NOT EXISTS idx_law_element_filter ON law_element (bwb_id, lower(number), type);

        CREATE INDEX IF NOT EXISTS idx_bwb_id ON {TBL_LAWS} (bwb_id, bwb_label_id);
        CREATE INDEX IF NOT EXISTS idx_law_element_filter ON {TBL_LAWS} (bwb_id, lower(number), type);

        CREATE TABLE IF NOT EXISTS {TBL_CASE_LAW} (
            id INTEGER PRIMARY KEY,
            case_id INTEGER,
            law_id INTEGER,
            source TEXT CHECK (source IN ('lido-ref', 'lido-linkt', 'custom')),
            jc_id TEXT,
            lido_id TEXT,
            opschrift TEXT,
            FOREIGN KEY (case_id) REFERENCES {TBL_CASES}(id),
            FOREIGN KEY (law_id) REFERENCES {TBL_LAWS}(id)
        );
        CREATE INDEX IF NOT EXISTS idx_caselaw_cl ON {TBL_CASE_LAW} (case_id, law_id);
        CREATE INDEX IF NOT EXISTS idx_caselaw_lc ON {TBL_CASE_LAW} (law_id, case_id);

        CREATE TABLE IF NOT EXISTS {TBL_LAW_ALIAS} (
            id INTEGER PRIMARY KEY,
            alias TEXT NOT NULL,
            bwb_id TEXT NOT NULL,
            source TEXT CHECK (source IN ('opschrift', 'bwbidlist')),
            UNIQUE (bwb_id, alias COLLATE NOCASE)
        );
        CREATE INDEX IF NOT EXISTS idx_law_alias ON {TBL_LAW_ALIAS}(alias COLLATE NOCASE);
    """)
    conn.commit()
    cursor.close()
    print("Database initialized.")
