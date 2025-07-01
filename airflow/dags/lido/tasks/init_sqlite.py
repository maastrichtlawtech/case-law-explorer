import os
from lido.utils.sqlite import get_conn


def task_init_sqlite(db_path: str):

    conn = get_conn(db_path)
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS legal_case (
            id INTEGER PRIMARY KEY,
            ecli_id TEXT UNIQUE NOT NULL,
            title TEXT,
            celex_id TEXT UNIQUE,
            zaaknummer TEXT,
            uitspraakdatum DATE
        );
        
        CREATE TABLE IF NOT EXISTS law_element (
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

        CREATE TABLE IF NOT EXISTS case_law (
            id INTEGER PRIMARY KEY,
            case_id INTEGER,
            law_id INTEGER,
            source TEXT CHECK (source IN ('lido-ref', 'lido-linkt', 'custom')),
            jc_id TEXT,
            lido_id TEXT,
            opschrift TEXT,
            FOREIGN KEY (case_id) REFERENCES legal_case(id),
            FOREIGN KEY (law_id) REFERENCES law_element(id)
        );
        CREATE INDEX IF NOT EXISTS idx_caselaw_cl ON case_law (case_id, law_id);
        CREATE INDEX IF NOT EXISTS idx_caselaw_lc ON case_law (law_id, case_id);
        
        CREATE TABLE IF NOT EXISTS law_alias (
            id INTEGER PRIMARY KEY,
            alias TEXT NOT NULL,
            bwb_id TEXT NOT NULL,
            source TEXT CHECK (source IN ('opschrift', 'bwbidlist')),
            UNIQUE (bwb_id, alias COLLATE NOCASE)
        );
        CREATE INDEX IF NOT EXISTS idx_law_alias ON law_alias(alias COLLATE NOCASE);
    """)
    conn.commit()
    cursor.close()
    print("Database initialized.")