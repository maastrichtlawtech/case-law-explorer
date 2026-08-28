from datetime import datetime

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
