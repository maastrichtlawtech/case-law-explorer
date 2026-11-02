import io
import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import etl_factory
import pytest


def test_controller_window_takes_precedence():
    context = {
        "dag_run": SimpleNamespace(
            run_id="manual__controller__1",
            run_type="manual",
            conf={"window_start": "2026-05-01", "window_end": "2026-08-28"},
        )
    }

    assert etl_factory.resolve_run_window("ECHR", context) == (
        date(2026, 5, 1),
        date(2026, 8, 28),
        False,
    )


def test_scheduled_window_refreshes_two_prior_and_current_month():
    context = {
        "dag_run": SimpleNamespace(
            run_id="scheduled__2026-09-07T04:00:00+00:00",
            run_type="scheduled",
            conf={},
        ),
        "data_interval_end": datetime(2026, 9, 7, 4),
    }

    assert etl_factory.resolve_run_window("ECHR", context) == (
        date(2026, 7, 1),
        date(2026, 9, 6),
        True,
    )


def test_monthly_runner_is_sequential_and_refreshes_scheduled_artifacts(monkeypatch):
    calls = []
    monkeypatch.setattr(etl_factory, "get_data_path", lambda: "/data")

    etl_factory.run_monthly_window(
        "CELLAR",
        lambda **kwargs: calls.append(kwargs),
        dag_run=SimpleNamespace(
            run_id="scheduled__1",
            run_type="scheduled",
            conf={},
        ),
        data_interval_end=datetime(2026, 9, 7, 3),
    )

    assert [(call["start_date"].date(), call["end_date"].date()) for call in calls] == [
        (date(2026, 7, 1), date(2026, 7, 31)),
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 6)),
    ]
    assert all(call["force_refresh"] for call in calls)
    assert [call["is_final_chunk"] for call in calls] == [False, False, True]


def test_manual_backfill_can_force_refresh_historical_artifacts(monkeypatch):
    calls = []
    monkeypatch.setattr(etl_factory, "get_data_path", lambda: "/data")

    etl_factory.run_monthly_window(
        "CELLAR",
        lambda **kwargs: calls.append(kwargs),
        dag_run=SimpleNamespace(
            run_id="manual__cellar_repair",
            run_type="manual",
            conf={
                "window_start": "2011-01-01",
                "window_end": "2011-02-28",
                "force_refresh": True,
            },
        ),
    )

    assert len(calls) == 2
    assert all(call["force_refresh"] for call in calls)


def test_successful_run_registers_exact_controller_window():
    context = {
        "dag_run": SimpleNamespace(
            run_id="manual__controller__1",
            run_type="manual",
            conf={
                "requested_by": "david",
                "window_start": "2026-05-01",
                "window_end": "2026-08-28",
            },
        )
    }
    response = io.BytesIO(b'{"batch_id":"00000000-0000-0000-0000-000000000001"}')
    with patch.dict(
        "os.environ",
        {
            "ETL_PROMOTION_ENABLED": "true",
            "ETL_PROMOTER_INTERNAL_TOKEN": "test-token",
        },
    ), patch("etl_factory.urllib.request.urlopen", return_value=response) as urlopen:
        result = etl_factory.register_promotion("echr_etl", "ECHR", **context)

    request = urlopen.call_args.args[0]
    payload = json.loads(request.data)
    assert payload == {
        "dag_id": "echr_etl",
        "run_id": "manual__controller__1",
        "requested_by": "david",
        "window_start": "2026-05-01",
        "window_end": "2026-08-28",
    }
    assert request.headers["X-etl-promoter-token"] == "test-token"
    assert result["batch_id"].endswith("1")


def _run_window_with_empty(tmp_path, monkeypatch, empty_from, data_interval_end):
    monkeypatch.setattr(etl_factory, "get_data_path", lambda: str(tmp_path))

    def etl(**kwargs):
        if kwargs["start_date"].date() >= empty_from:
            raise etl_factory.NoSourceData("no data")

    etl_factory.run_monthly_window(
        "ECHR",
        etl,
        dag_run=SimpleNamespace(run_id="scheduled__1", run_type="scheduled", conf={}),
        data_interval_end=data_interval_end,
    )


def _marker(tmp_path, chunk):
    return tmp_path / "processed" / chunk / etl_factory.NO_SOURCE_DATA_MARKER


def test_empty_short_final_chunk_is_marked_not_failed(tmp_path, monkeypatch):
    _run_window_with_empty(tmp_path, monkeypatch, date(2026, 11, 1), datetime(2026, 11, 2, 4))

    assert _marker(tmp_path, "2026-11-01").is_file()
    assert not _marker(tmp_path, "2026-10-01").exists()


def test_marker_is_cleared_once_the_chunk_has_data(tmp_path, monkeypatch):
    marker = _marker(tmp_path, "2026-11-01")
    marker.parent.mkdir(parents=True)
    marker.write_text("stale")

    _run_window_with_empty(tmp_path, monkeypatch, date(2099, 1, 1), datetime(2026, 11, 9, 4))

    assert not marker.exists()


@pytest.mark.parametrize(
    "empty_from, interval_end",
    [
        (date(2026, 10, 1), datetime(2026, 11, 2, 4)),  # an earlier chunk is empty
        (date(2026, 11, 1), datetime(2026, 11, 16, 4)),  # long final chunk: 15 days
        (date(2026, 9, 1), datetime(2026, 11, 2, 4)),  # everything is empty
    ],
)
def test_other_empty_chunks_still_fail(tmp_path, monkeypatch, empty_from, interval_end):
    with pytest.raises(etl_factory.NoSourceData):
        _run_window_with_empty(tmp_path, monkeypatch, empty_from, interval_end)
