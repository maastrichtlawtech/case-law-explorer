from lido.config import FILE_SQLITE_DB
from lido.utils.sqlite import get_conn


def task_sqlite_to_csv():
    conn = get_conn(FILE_SQLITE_DB)
    cursor = conn.cursor()

    # .mode csv
    # .headers on
    # .output export_law_element.csv
    # SELECT * FROM law_element;
