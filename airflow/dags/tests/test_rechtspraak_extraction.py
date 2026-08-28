from datetime import datetime
from types import SimpleNamespace

from data_extraction.caselaw.rechtspraak import rechtspraak_extraction as extraction
from data_extraction.caselaw.rechtspraak.rechtspraak_extraction import _daily_ranges


def test_daily_ranges_includes_the_requested_end_date():
    ranges = list(_daily_ranges("2026-07-30", "2026-07-31"))

    assert ranges == [
        (datetime(2026, 7, 30), datetime(2026, 7, 31)),
        (datetime(2026, 7, 31), datetime(2026, 8, 1)),
    ]


def test_daily_ranges_handles_a_single_day():
    assert list(_daily_ranges("2026-08-28", "2026-08-28")) == [
        (datetime(2026, 8, 28), datetime(2026, 8, 29))
    ]


def test_bounded_paginator_stops_when_upstream_count_is_one_too_high(monkeypatch):
    pages = [
        {"feed": {"entry": [{"id": "one"}, {"id": "two"}]}},
        {"feed": {"entry": []}},
    ]
    calls = []

    class Response:
        raw = SimpleNamespace(decode_content=False)
        text = "ignored"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(extraction.rex, "MAX_ECLIS_PER_PAGE", 2)
    monkeypatch.setattr(extraction.rex, "API_REQUEST_TIMEOUT", 1)
    monkeypatch.setattr(extraction.rex, "SLEEP_BETWEEN_REQUESTS", 0)
    monkeypatch.setattr(
        extraction.rex,
        "_build_api_url",
        lambda base, rows, offset, start, end: str(offset),
    )
    monkeypatch.setattr(
        extraction.rex.requests,
        "get",
        lambda url, timeout: calls.append(url) or Response(),
    )
    monkeypatch.setattr(extraction.rex, "parse_xml_response", lambda text: pages.pop(0))

    rows = extraction._bounded_get_data_from_url("api", 3, "2026-08-19", "2026-08-20")

    assert rows == [{"id": "one"}, {"id": "two"}]
    assert calls == ["0", "2"]
