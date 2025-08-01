import json
from lido.utils.sqlite import get_conn
from lido.config import FILE_SQLITE_DB, FILE_BWB_IDS_JSON, TBL_LAW_ALIAS

def task_bwbidlist_to_sqlite():

    conn = get_conn(FILE_SQLITE_DB)
    cursor = conn.cursor()

    with open(FILE_BWB_IDS_JSON, 'r') as f:
        bwb_titles = json.load(f)
        for bwb_id, titles in bwb_titles:
            for title in titles:
                cursor.execute(f"INSERT OR IGNORE INTO {TBL_LAW_ALIAS} (alias, bwb_id, source) VALUES (?, ?, 'bwbidlist')", (title, bwb_id,))
