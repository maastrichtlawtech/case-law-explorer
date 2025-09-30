import json
from lido.utils.sqlite import get_conn
from lido.config import FILE_SQLITE_DB, FILE_BWB_IDS_JSON, TBL_LAW_ALIAS

def task_bwbidlist_to_sqlite():

    conn = get_conn(FILE_SQLITE_DB)
    cursor = conn.cursor()

    amount_bwbs = 0
    amount_titles = 0

    with open(FILE_BWB_IDS_JSON, 'r') as f:
        bwb_titles = json.load(f)
        for bwb_id, titles in bwb_titles:
            amount_bwbs += 1
            for title in titles:
                cursor.execute(f"INSERT OR IGNORE INTO {TBL_LAW_ALIAS} (alias, bwb_id, source) VALUES (?, ?, 'bwbidlist')", (title, bwb_id,))
                amount_titles += 1

    conn.commit()
    cursor.close()

    return [amount_bwbs, amount_titles]
