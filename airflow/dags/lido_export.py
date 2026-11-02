"""
Download and sanity-check the LIDO bulk export for lido_sqlite_build.

KOOP moved the export from lido-export.ttl.gz to lido-export.nt.gz (listed on
data.overheid.nl/dataset/linked-data-overheid). The old URL kept answering
HTTP 200 with an HTML error page, which was saved as the export: the build
parsed nothing, kept the old lido.db and stayed green. So a download now has to
be a complete gzip of plausible size before it replaces anything, and a build
has to contain recent decisions.
"""

import gzip
import logging
import os
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

import requests

DEFAULT_EXPORT_URL = "https://linkeddata.overheid.nl/export/lido-export.nt.gz"
GZIP_MAGIC = b"\x1f\x8b"
MIN_EXPORT_BYTES = 1_000_000_000
# The export is monthly, and decisions are published some weeks after the date.
MAX_NEWEST_DECISION_AGE_DAYS = 75
DOWNLOAD_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 60


def _fetch(url, part_path):
    """Append the rest of ``url`` to ``part_path``; return the expected total size."""
    offset = part_path.stat().st_size if part_path.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with requests.get(url, stream=True, timeout=60, headers=headers) as response:
        response.raise_for_status()
        resumed = response.status_code == 206
        if not resumed:
            offset = 0
        total = offset + int(response.headers.get("content-length", 0))
        with open(part_path, "ab" if resumed else "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    return total


def verify_export(path, min_bytes=MIN_EXPORT_BYTES):
    """Raise ValueError unless ``path`` is a complete gzip of plausible size."""
    size = os.path.getsize(path)
    if size < min_bytes:
        raise ValueError(f"LIDO export is only {size} bytes; minimum is {min_bytes}")
    with open(path, "rb") as handle:
        if handle.read(2) != GZIP_MAGIC:
            raise ValueError("LIDO export is not gzip")
    try:
        with gzip.open(path, "rb") as handle:
            while handle.read(1 << 24):
                pass
    except (OSError, EOFError) as exc:
        raise ValueError(f"LIDO export is not a complete gzip: {exc}") from exc


def download_export(dest, url=DEFAULT_EXPORT_URL, min_bytes=MIN_EXPORT_BYTES):
    """Download to ``dest`` atomically, resuming: the host drops connections."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part_path = dest.with_name(dest.name + ".part")
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            total = _fetch(url, part_path)
            size = part_path.stat().st_size
            if total and size != total:
                raise OSError(f"got {size} of {total} bytes")
            break
        except (requests.RequestException, OSError) as exc:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise
            logging.warning("LIDO download attempt %s failed: %s", attempt, exc)
            time.sleep(RETRY_DELAY_SECONDS)
    try:
        verify_export(part_path, min_bytes)
    except ValueError:
        part_path.unlink()
        raise
    os.replace(part_path, dest)


def verify_build_freshness(db_path, today=None, max_age_days=MAX_NEWEST_DECISION_AGE_DAYS):
    """Raise ValueError when lido.db's newest past decision is too old."""
    today = today or date.today()
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        newest = connection.execute(
            "SELECT MAX(date_decision) FROM metadata WHERE date_decision <= ?",
            (today.isoformat(),),
        ).fetchone()[0]
    finally:
        connection.close()
    if not newest or date.fromisoformat(newest[:10]) < today - timedelta(days=max_age_days):
        raise ValueError(f"lido.db's newest decision is {newest}; the export looks stale")
    logging.info("lido.db's newest decision is %s", newest)
