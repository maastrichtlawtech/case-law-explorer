import json
from lido.utils.sqlite import get_conn
from lido.config import *

def task_bwbidlist_to_sqlite():
    
    conn = get_conn(FILE_SQLITE_DB)
    cursor = conn.cursor()

    with open(FILE_BWB_IDS_JSON, 'r') as f:
        bwb_titles = json.load(f)
        for bwb_id, titles in bwb_titles:
            for title in titles:
                cursor.execute("INSERT OR IGNORE INTO law_alias (alias, bwb_id, source) VALUES (?, ?, 'bwbidlist')", (title, bwb_id,))
