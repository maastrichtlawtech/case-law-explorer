"""
Link artifact and link loader.

The artifact tests are pure. The loader tests need a real Postgres (the
loader's correctness is in its SQL: partial-index arbiters, ON CONFLICT,
cascades), so they run only when CLE_TEST_PG_DSN points at a server where
the test may create and drop a scratch database, e.g.

    CLE_TEST_PG_DSN=postgresql://postgres:test@localhost:5432/postgres

The schema is built from db/schema.sql, which mirrors the deployed migrations.
"""

import json
import os
import uuid
from pathlib import Path

import pytest

from data_extraction.linking.artifact import (
    ArtifactError,
    CaseKey,
    LinkRecord,
    Mention,
    match_method,
    read_jsonl,
    write_jsonl,
)

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"


def _record(**overrides):
    value = {
        "source": {"ecli": "ECLI:NL:RVS:2020:423"},
        "target": {"ecli": "ECLI:EU:C:2019:189"},
        "target_ref_raw": "C-221/17",
        "target_ref_scheme": "cjeu_case_number",
        "relation_type": "cites",
        "source_dataset": "rs_text_cjeu_casenum",
        "extractor_version": "rs_text/test",
        "match_method": "case_number/cjeu_judgment",
        "confidence": 0.9,
        "mentions": [
            {
                "text_field": "fulltext",
                "language": "nl",
                "text_source": "RECHTSPRAAK",
                "char_start": 10,
                "char_end": 18,
                "raw_text": "C‑221/17",
            }
        ],
    }
    value.update(overrides)
    return value


# ---------------------------------------------------------------------------
# artifact
# ---------------------------------------------------------------------------


def test_record_round_trip(tmp_path):
    record = LinkRecord.from_dict(_record())
    path = tmp_path / "links.jsonl"
    assert write_jsonl([record], path) == 1
    assert list(read_jsonl(path)) == [record]


def test_write_is_sorted_and_stable(tmp_path):
    a = LinkRecord.from_dict(_record(source={"ecli": "ECLI:NL:B:2020:1"}))
    b = LinkRecord.from_dict(_record(source={"ecli": "ECLI:NL:A:2020:1"}))
    first, second = tmp_path / "1.jsonl", tmp_path / "2.jsonl"
    write_jsonl([a, b], first)
    write_jsonl([b, a], second)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"source": {}}, "needs source"),
        ({"source": {"case_id": 1}}, "unknown case key"),
        ({"target": None, "target_ref_raw": None, "target_ref_scheme": None}, "needs a target"),
        ({"target_ref_scheme": "bogus"}, "known scheme"),
        ({"target_ref_raw": None}, "without target_ref_raw"),
        ({"confidence": 1.5}, "between 0 and 1"),
        ({"target": {"ecli": "ECLI:NL:RVS:2020:423"}}, "itself"),
        ({"mentions": [{"text_field": "body", "raw_text": "x"}]}, "text_field"),
        ({"mentions": [{"text_field": "summary", "raw_text": "x", "char_start": 3}]}, "together"),
        (
            {
                "mentions": [
                    {"text_field": "summary", "raw_text": "x", "char_start": 5, "char_end": 2}
                ]
            },
            "bad offsets",
        ),
    ],
)
def test_invalid_records_are_refused(overrides, message):
    with pytest.raises(ArtifactError, match=message):
        LinkRecord.from_dict(_record(**overrides))


def test_read_names_the_bad_line(tmp_path):
    path = tmp_path / "links.jsonl"
    good = json.dumps(_record())
    path.write_text(good + "\n" + json.dumps(_record(confidence=7)) + "\n")
    with pytest.raises(ArtifactError, match=r"links.jsonl:2"):
        list(read_jsonl(path))


def test_match_method_convention():
    assert match_method("case_number", "cjeu_judgment") == "case_number/cjeu_judgment"
    assert match_method("ecli") == match_method("ecli", "ecli") == "ecli"
    with pytest.raises(ArtifactError, match="unknown match method"):
        match_method("guess", "x")


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"match_method": "cjeu_judgment"}, "bad match_method"),
        ({"match_method": "case_number/"}, "bad match_method"),
        ({"target": None, "match_method": "case_number/cjeu_judgment"}, "method alone"),
        ({"target": None, "match_method": "case_number", "confidence": 0.9}, "no confidence"),
    ],
)
def test_match_method_is_validated(overrides, message):
    with pytest.raises(ArtifactError, match=message):
        LinkRecord.from_dict(_record(**overrides))


def test_case_key_drops_empty_fields():
    assert CaseKey.from_dict({"ecli": "E", "celex": ""}).to_dict() == {"ecli": "E"}
    assert Mention.from_dict({"text_field": "metadata", "raw_text": "x"}).char_start is None


# ---------------------------------------------------------------------------
# loader, against a real database
# ---------------------------------------------------------------------------

DSN = os.environ.get("CLE_TEST_PG_DSN")
needs_db = pytest.mark.skipif(not DSN, reason="CLE_TEST_PG_DSN not set")


@pytest.fixture
def conn():
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
            cursor.execute("""
                INSERT INTO cle_v2.cases (ecli, celex_id, sources) VALUES
                  ('ECLI:NL:RVS:2020:423', NULL, '{RS}'),
                  ('ECLI:EU:C:2019:189', '62017CJ0221', '{CJEU}'),
                  ('ECLI:NL:HR:2020:593', NULL, '{RS}');
                INSERT INTO cle_v2.case_text (case_id, language, source, fulltext)
                SELECT id, 'nl', 'RECHTSPRAAK', 'tekst' FROM cle_v2.cases
                 WHERE ecli = 'ECLI:NL:RVS:2020:423';
                """)
        db.commit()
        yield db
    finally:
        db.close()
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
        admin.close()


def _rows(conn, sql):
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


@needs_db
def test_loader_inserts_resolved_row_with_provenance_and_mention(conn):
    from data_loading.link_loader import load_records

    counts = load_records(conn, [LinkRecord.from_dict(_record())])
    assert counts == {"rs_text_cjeu_casenum": {"inserted": 1, "mentions_inserted": 1}}
    rows = _rows(
        conn,
        """
        SELECT s.ecli, t.ecli, cc.match_method, cc.confidence, cc.target_ref_raw,
               cc.is_cross_jurisdiction, cc.weight, m.raw_text, m.case_text_id IS NOT NULL
          FROM cle_v2.case_citation cc
          JOIN cle_v2.cases s ON s.id = cc.source_case_id
          JOIN cle_v2.cases t ON t.id = cc.target_case_id
          JOIN cle_v2.case_citation_mention m ON m.citation_id = cc.id
        """,
    )
    assert rows == [
        (
            "ECLI:NL:RVS:2020:423",
            "ECLI:EU:C:2019:189",
            "case_number/cjeu_judgment",
            pytest.approx(0.9),
            "C-221/17",
            True,
            1,
            "C‑221/17",
            True,
        )
    ]


@needs_db
def test_loader_is_idempotent_and_adds_new_mentions(conn):
    from data_loading.link_loader import load_records

    load_records(conn, [LinkRecord.from_dict(_record())])
    again = _record()
    again["mentions"].append({"text_field": "summary", "language": "nl", "raw_text": "C-221/17"})
    counts = load_records(conn, [LinkRecord.from_dict(again)])
    assert counts == {"rs_text_cjeu_casenum": {"existing": 1, "mentions_inserted": 1}}
    assert _rows(conn, "SELECT count(*) FROM cle_v2.case_citation") == [(1,)]
    assert _rows(conn, "SELECT count(*) FROM cle_v2.case_citation_mention") == [(2,)]


@needs_db
def test_loader_writes_missing_target_unresolved_and_reference_only(conn):
    from data_loading.link_loader import load_records

    records = [
        # target not in this database: kept by its ECLI for late binding
        _record(
            target={"ecli": "ECLI:EU:C:2013:720"},
            target_ref_raw="C-199/12",
            source_dataset="rs_text_ecli",
        ),
        # nothing matched: kept by reference
        _record(
            target=None,
            target_ref_raw="C-999/99",
            source_dataset="rs_text_cjeu_casenum",
            match_method="case_number",
            confidence=None,
        ),
        # source case absent: skipped
        _record(source={"ecli": "ECLI:NL:XX:2020:1"}),
    ]
    first = load_records(conn, [LinkRecord.from_dict(r) for r in records])
    second = load_records(conn, [LinkRecord.from_dict(r) for r in records])
    assert first == {
        "rs_text_ecli": {"inserted_unresolved": 1, "mentions_inserted": 1},
        "rs_text_cjeu_casenum": {
            "inserted_unresolved": 1,
            "mentions_inserted": 1,
            "source_missing": 1,
        },
    }
    assert second == {
        "rs_text_ecli": {"existing": 1},
        "rs_text_cjeu_casenum": {"existing": 1, "source_missing": 1},
    }
    rows = _rows(
        conn,
        """
        SELECT source_dataset, target_ecli_raw, target_ref_raw, target_ref_scheme,
               is_cross_jurisdiction
          FROM cle_v2.case_citation ORDER BY source_dataset
        """,
    )
    assert rows == [
        ("rs_text_cjeu_casenum", None, "C-999/99", "cjeu_case_number", False),
        ("rs_text_ecli", "ECLI:EU:C:2013:720", "C-199/12", "cjeu_case_number", True),
    ]


@needs_db
def test_dataset_is_removed_with_one_delete(conn):
    from data_loading.link_loader import load_records

    load_records(conn, [LinkRecord.from_dict(_record())])
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM cle_v2.case_citation WHERE source_dataset = 'rs_text_cjeu_casenum'"
        )
    conn.commit()
    assert _rows(conn, "SELECT count(*) FROM cle_v2.case_citation_mention") == [(0,)]
