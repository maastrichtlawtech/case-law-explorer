
from lido.utils.sqlite import get_conn
from lido.config import *

def task_sqlite_to_csv():
    conn = get_conn(FILE_SQLITE_DB)
    cursor = conn.cursor()

    # .mode csv
    # .headers on
    # .output export_law_element.csv
    # SELECT * FROM law_element;

    