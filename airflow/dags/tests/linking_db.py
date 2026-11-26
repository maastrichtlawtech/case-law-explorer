"""
Scratch database for the link extractor tests, as in test_link_loader.py:
built from db/schema.sql, only when CLE_TEST_PG_DSN points at a server where
the test may create and drop a database, e.g.

    CLE_TEST_PG_DSN=postgresql://postgres:test@localhost:5432/postgres
"""

import os
import uuid
from pathlib import Path

import pytest

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"
DSN = os.environ.get("CLE_TEST_PG_DSN")
needs_db = pytest.mark.skipif(not DSN, reason="CLE_TEST_PG_DSN not set")


@pytest.fixture
def scratch_db():
    psycopg2 = pytest.importorskip("psycopg2")
    name = "cle_link_test_" + uuid.uuid4().hex[:8]
    admin = psycopg2.connect(DSN)
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE "{name}"')
    base, _, _ = DSN.rpartition("/")
    db = psycopg2.connect(f"{base}/{name}")
    try:
        sql = SCHEMA_SQL.read_text().replace('CREATE SCHEMA "public";', "")
        with db.cursor() as cursor:
            cursor.execute(sql)
        db.commit()
        yield db
    finally:
        db.close()
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
        admin.close()


def execute(conn, sql, params=None):
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall() if cursor.description else None
    conn.commit()
    return rows


def add_case(conn, ecli=None, celex=None, decided=None, sources=("CJEU",), case_number=None):
    """Insert a case; returns its id."""
    return execute(
        conn,
        """INSERT INTO cle_v2.cases (ecli, celex_id, date_decision, sources, case_number)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (ecli, celex, decided, list(sources), case_number),
    )[0][0]


def add_identifier(conn, case_id, scheme, value, value_normalized, source="test"):
    execute(
        conn,
        """INSERT INTO cle_v2.case_identifier (case_id, scheme, value, value_normalized, source)
           VALUES (%s, %s, %s, %s, %s)""",
        (case_id, scheme, value, value_normalized, source),
    )
