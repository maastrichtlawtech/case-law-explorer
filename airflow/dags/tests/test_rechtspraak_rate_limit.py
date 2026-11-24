import threading

import pandas as pd
import rechtspraak_extractor.rechtspraak_metadata as rex_metadata
from data_extraction.caselaw.rechtspraak import rate_limit
from data_extraction.caselaw.rechtspraak import rechtspraak_extraction as extraction


def test_limiter_spaces_sequential_calls(monkeypatch):
    clock = {"now": 100.0}
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(rate_limit.time, "sleep", lambda s: clock.update(now=clock["now"] + s))
    limiter = rate_limit.RateLimiter(per_second=4)
    times = []

    for _ in range(5):
        limiter.wait()
        times.append(clock["now"])

    assert [round(b - a, 9) for a, b in zip(times, times[1:])] == [0.25] * 4


def test_limiter_gives_concurrent_threads_distinct_slots(monkeypatch):
    sleeps = []
    lock = threading.Lock()
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 100.0)

    def record_sleep(seconds):
        with lock:
            sleeps.append(round(seconds, 9))

    monkeypatch.setattr(rate_limit.time, "sleep", record_sleep)
    limiter = rate_limit.RateLimiter(per_second=4)

    threads = [threading.Thread(target=limiter.wait) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # One thread goes at once; the other seven wait 0.25 s apart.
    assert sorted(sleeps) == [0.25 * n for n in range(1, 8)]


def test_per_ecli_fetches_go_through_the_limiter(monkeypatch):
    waits = []
    monkeypatch.setattr(rate_limit, "wait_for_slot", lambda: waits.append(1))

    assert getattr(rex_metadata.extract_data_from_xml, "rate_limited", False)
    wrapped = rate_limit.rate_limited(lambda url, fake_headers=False: b"<xml/>")

    assert wrapped("https://data.rechtspraak.nl/uitspraken/content?id=x") == b"<xml/>"
    assert waits == [1]


def test_metadata_calls_fetch_sequentially_without_fake_headers(monkeypatch, tmp_path):
    calls = []

    def fake_metadata(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"ecli": ["ECLI:NL:HR:2026:1"], "full_text": ["tekst " * 300]})

    monkeypatch.setattr(extraction, "get_rechtspraak_metadata", fake_metadata)
    monkeypatch.setattr(extraction, "_fetch_extra_sqlite_columns", lambda *a: pd.DataFrame())
    base = pd.DataFrame({"id": ["ECLI:NL:HR:2026:1"], "summary": [""]})

    extraction._metadata_for_base(base, 10, "lido.db", str(tmp_path), "2026-11-16")

    assert calls
    assert all(call["multi_threading"] is False for call in calls)
    assert all(call["_fake_headers"] is False for call in calls)
