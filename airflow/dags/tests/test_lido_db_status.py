import logging
import sqlite3

from data_extraction.caselaw.rechtspraak import rechtspraak_extraction as extraction


def _lido_db(path, rows):
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE metadata (ecli TEXT PRIMARY KEY, date_decision TEXT)")
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", rows)
    connection.commit()
    connection.close()
    return str(path)


def test_lido_db_status_reports_a_missing_database(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    path = str(tmp_path / "lido.db")

    assert extraction._lido_sqlite_db_path(path) == path
    assert "LIDO_DB status=missing" in caplog.text
    assert not (tmp_path / "lido.db").exists()


def test_lido_db_status_reports_an_empty_database(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    path = _lido_db(tmp_path / "lido.db", [])

    extraction._lido_sqlite_db_path(path)

    assert "LIDO_DB status=empty" in caplog.text


def test_lido_db_status_reports_a_database_without_the_metadata_table(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    path = tmp_path / "lido.db"
    path.write_bytes(b"<!DOCTYPE html><html>not a database</html>")

    extraction._lido_sqlite_db_path(str(path))

    assert "LIDO_DB status=unreadable" in caplog.text


def test_lido_db_status_reports_size_and_newest_decision(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    path = _lido_db(
        tmp_path / "lido.db",
        [("ECLI:NL:HR:2026:1", "2026-10-30"), ("ECLI:NL:HR:2026:2", "2026-11-02")],
    )

    extraction._lido_sqlite_db_path(path)

    assert "LIDO_DB status=ok" in caplog.text
    assert "cases=2 newest_decision=2026-11-02" in caplog.text
