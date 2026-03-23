# Connect to PostgreSQL
import sqlite3


def cursor_is_sqlite(cursor):
    return isinstance(cursor, sqlite3.Cursor)


def get_conn(db="stage.db"):
    return sqlite3.connect(db)
