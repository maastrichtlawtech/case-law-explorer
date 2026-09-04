import io
import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import etl_factory


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


def test_scheduled_window_refreshes_previous_and_current_month():
    context = {
        "dag_run": SimpleNamespace(
            run_id="scheduled__2026-09-07T04:00:00+00:00",
            run_type="scheduled",
            conf={},
        ),
        "data_interval_end": datetime(2026, 9, 7, 4),
    }

    assert etl_factory.resolve_run_window("ECHR", context) == (
        date(2026, 8, 1),
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
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 6)),
    ]
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
