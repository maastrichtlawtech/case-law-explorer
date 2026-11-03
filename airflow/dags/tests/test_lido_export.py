import gzip
from datetime import date
import sqlite3

import lido_export
import pytest


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code
        self.headers = {"content-length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise lido_export.requests.HTTPError(str(self.status_code))

    def iter_content(self, chunk_size):
        yield self.body


def test_html_error_page_never_replaces_the_export(tmp_path, monkeypatch):
    dest = tmp_path / "lido.nt.gz"
    dest.write_bytes(b"previous")
    html = b"<html>/export/lido-export.ttl.gz (No such file or directory)</html>"
    monkeypatch.setattr(lido_export.requests, "get", lambda *a, **k: FakeResponse(html))

    with pytest.raises(ValueError, match="not gzip"):
        lido_export.download_export(dest, min_bytes=1)

    assert dest.read_bytes() == b"previous"
    assert not (tmp_path / "lido.nt.gz.part").exists()


def test_undersized_download_is_rejected(tmp_path, monkeypatch):
    body = gzip.compress(b"<s> <p> <o> .\n")
    monkeypatch.setattr(lido_export.requests, "get", lambda *a, **k: FakeResponse(body))

    with pytest.raises(ValueError, match="minimum"):
        lido_export.download_export(tmp_path / "lido.nt.gz")


def test_truncated_gzip_is_rejected(tmp_path):
    path = tmp_path / "x.gz"
    path.write_bytes(gzip.compress(b"<s> <p> <o> .\n" * 1000)[:-20])

    with pytest.raises(ValueError, match="complete gzip"):
        lido_export.verify_export(path, min_bytes=1)


def test_download_resumes_after_a_dropped_connection(tmp_path, monkeypatch):
    body = gzip.compress(b"<s> <p> <o> .\n" * 1000)
    requested = []

    def get(url, headers, **_):
        requested.append(headers.get("Range"))
        if not headers:
            (tmp_path / "lido.nt.gz.part").write_bytes(body[:10])
            raise lido_export.requests.ConnectionError("dropped")
        return FakeResponse(body[10:], status_code=206)

    monkeypatch.setattr(lido_export.requests, "get", get)
    monkeypatch.setattr(lido_export, "RETRY_DELAY_SECONDS", 0)

    lido_export.download_export(tmp_path / "lido.nt.gz", min_bytes=1)

    assert requested == [None, "bytes=10-"]
    assert (tmp_path / "lido.nt.gz").read_bytes() == body


def test_failing_resume_restarts_the_download(tmp_path, monkeypatch):
    body = gzip.compress(b"<s> <p> <o> .\n" * 1000)
    (tmp_path / "lido.nt.gz.part").write_bytes(body[:10])
    requested = []

    def get(url, headers, **_):
        requested.append(headers.get("Range"))
        if headers:
            return FakeResponse(b"<html>504 Gateway Time-out</html>", status_code=504)
        return FakeResponse(body)

    monkeypatch.setattr(lido_export.requests, "get", get)
    monkeypatch.setattr(lido_export, "RETRY_DELAY_SECONDS", 0)

    lido_export.download_export(tmp_path / "lido.nt.gz", min_bytes=1)

    assert requested == ["bytes=10-", None]
    assert (tmp_path / "lido.nt.gz").read_bytes() == body


def test_complete_partial_file_is_accepted(tmp_path, monkeypatch):
    body = gzip.compress(b"<s> <p> <o> .\n" * 1000)
    (tmp_path / "lido.nt.gz.part").write_bytes(body)
    monkeypatch.setattr(lido_export.requests, "get", lambda *a, **k: FakeResponse(b"", status_code=416))

    lido_export.download_export(tmp_path / "lido.nt.gz", min_bytes=1)

    assert (tmp_path / "lido.nt.gz").read_bytes() == body


def _db(tmp_path, *dates):
    path = tmp_path / "lido.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE metadata (date_decision TEXT)")
    connection.executemany("INSERT INTO metadata VALUES (?)", [(d,) for d in dates])
    connection.commit()
    connection.close()
    return path


def test_stale_build_fails(tmp_path):
    db = _db(tmp_path, "2026-05-28", "2099-01-01")
    with pytest.raises(ValueError, match="2026-05-28"):
        lido_export.verify_build_freshness(db, today=date(2026, 11, 2))


def test_fresh_build_passes(tmp_path):
    db = _db(tmp_path, "2026-10-20")
    lido_export.verify_build_freshness(db, today=date(2026, 11, 2))
