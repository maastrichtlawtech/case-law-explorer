from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import promotion_client


NOW = datetime(2026, 9, 10, 6, tzinfo=timezone.utc)


def test_selects_only_mature_batches_after_latest_promotion():
    batches = [
        {
            "batch_id": "old-failure",
            "status": "failed",
            "created_at": "2026-08-01T00:00:00+00:00",
        },
        {
            "batch_id": "last-good",
            "status": "promoted",
            "created_at": "2026-08-15T00:00:00+00:00",
        },
        {
            "batch_id": "mature",
            "status": "verified",
            "created_at": "2026-09-07T03:00:00+00:00",
            "verified_at": "2026-09-07T04:00:00+00:00",
        },
        {
            "batch_id": "too-new",
            "status": "verified",
            "created_at": "2026-09-09T12:00:00+00:00",
            "verified_at": "2026-09-09T13:00:00+00:00",
        },
    ]

    selected = promotion_client.select_batches_for_run(
        batches, minimum_age_hours=48, now=NOW
    )

    assert [batch["batch_id"] for batch in selected] == ["mature"]


def test_unresolved_failure_after_latest_promotion_fails_the_airflow_task():
    batches = [
        {
            "batch_id": "last-good",
            "status": "promoted",
            "created_at": "2026-09-01T00:00:00+00:00",
        },
        {
            "batch_id": "broken",
            "status": "failed",
            "created_at": "2026-09-07T03:00:00+00:00",
            "error": "full-text coverage below threshold",
        },
    ]

    with pytest.raises(RuntimeError, match="full-text coverage below threshold"):
        promotion_client.select_batches_for_run(batches, 48, now=NOW)


def test_failed_promotion_without_replacement_is_selected_for_reverification():
    batches = [
        {
            "batch_id": "retry-me",
            "status": "failed",
            "failed_stage": "promotion",
            "created_at": "2026-09-07T03:00:00+00:00",
            "verified_at": "2026-09-07T04:00:00+00:00",
        }
    ]

    selected = promotion_client.select_batches_for_run(batches, 48, now=NOW)

    assert [batch["batch_id"] for batch in selected] == ["retry-me"]


def _rs_batch(batch_id, status, window, created, verified=None, **extra):
    return {
        "batch_id": batch_id,
        "status": status,
        "window_start": window[0],
        "window_end": window[1],
        "created_at": created,
        "verified_at": verified,
        **extra,
    }


def test_failed_promotion_covered_by_a_later_batch_is_skipped():
    # A scheduled batch whose artifacts a later backfill rewrote (5 Nov 2026).
    batches = [
        _rs_batch(
            "scheduled",
            "failed",
            ("2026-07-01", "2026-09-01"),
            "2026-09-01T02:30:00+00:00",
            "2026-09-01T02:35:00+00:00",
            failed_stage="promotion",
            error="artifact changed after verification",
        ),
        _rs_batch(
            "backfill",
            "verified",
            ("2026-06-01", "2026-09-03"),
            "2026-09-03T03:20:00+00:00",
            "2026-09-03T03:25:00+00:00",
        ),
    ]

    selected = promotion_client.select_batches_for_run(batches, 48, now=NOW)

    assert [batch["batch_id"] for batch in selected] == ["backfill"]


def test_failed_promotion_partly_covered_blocks_later_batches():
    batches = [
        _rs_batch(
            "scheduled",
            "failed",
            ("2026-07-01", "2026-09-01"),
            "2026-09-01T02:30:00+00:00",
            "2026-09-01T02:35:00+00:00",
            failed_stage="promotion",
        ),
        _rs_batch(
            "may-only",
            "verified",
            ("2026-05-01", "2026-05-31"),
            "2026-09-03T03:40:00+00:00",
            "2026-09-03T03:45:00+00:00",
        ),
    ]

    selected = promotion_client.select_batches_for_run(batches, 48, now=NOW)

    assert [batch["batch_id"] for batch in selected] == ["scheduled"]


def test_failed_lido_promotion_is_superseded_by_any_later_build():
    batches = [
        {
            "batch_id": "rebuild",
            "status": "failed",
            "failed_stage": "promotion",
            "created_at": "2026-09-01T18:00:00+00:00",
        },
        {
            "batch_id": "monthly",
            "status": "verified",
            "created_at": "2026-09-08T01:00:00+00:00",
            "verified_at": "2026-09-08T01:05:00+00:00",
        },
    ]

    selected = promotion_client.select_batches_for_run(batches, 48, now=NOW)

    assert [batch["batch_id"] for batch in selected] == ["monthly"]


def test_reverified_batch_matures_from_verification_and_holds_later_batches():
    batches = [
        _rs_batch(
            "reverified",
            "verifying",
            ("2026-07-01", "2026-09-01"),
            "2026-09-01T02:30:00+00:00",
        ),
        _rs_batch(
            "later",
            "verified",
            ("2026-07-01", "2026-09-02"),
            "2026-09-02T02:30:00+00:00",
            "2026-09-02T02:35:00+00:00",
        ),
    ]

    assert promotion_client.select_batches_for_run(batches, 48, now=NOW) == []

    batches[0].update(status="verified", verified_at="2026-09-09T06:00:00+00:00")
    assert promotion_client.select_batches_for_run(batches, 48, now=NOW) == []


def test_verification_failure_is_reported_even_behind_a_waiting_batch():
    batches = [
        _rs_batch(
            "too-new",
            "verified",
            ("2026-07-01", "2026-09-01"),
            "2026-09-09T02:30:00+00:00",
            "2026-09-09T02:35:00+00:00",
        ),
        _rs_batch(
            "broken",
            "failed",
            ("2026-07-01", "2026-09-02"),
            "2026-09-09T12:00:00+00:00",
            error="row count dropped",
        ),
    ]

    with pytest.raises(RuntimeError, match="row count dropped"):
        promotion_client.select_batches_for_run(batches, 48, now=NOW)


def test_failed_promotion_is_registered_again_instead_of_promoted():
    cfg = {
        "url": "http://etl-promoter:8080",
        "token": "token",
        "request_timeout": 30,
        "wait_seconds": 60,
        "poll_seconds": 1,
        "minimum_age_hours": 48,
    }
    failed = _rs_batch(
        "batch-1",
        "failed",
        ("2026-07-01", "2026-09-01"),
        "2026-09-01T02:30:00+00:00",
        "2026-09-01T02:35:00+00:00",
        failed_stage="promotion",
        error="artifact changed after verification",
        dag_id="rechtspraak_etl",
        run_id="scheduled__2026-08-31T02:00:00+00:00",
        requested_by="airflow",
    )
    with patch.object(promotion_client, "client_settings", return_value=cfg), patch.object(
        promotion_client,
        "promoter_json",
        side_effect=[{"batches": [failed]}, {"status": "verifying"}],
    ) as request:
        with pytest.raises(RuntimeError, match="verified again"):
            promotion_client.promote_source_batches("rechtspraak_etl")

    (path,) = request.call_args_list[1].args
    assert path == "/v1/batches"
    assert request.call_args_list[1].kwargs["payload"] == {
        "dag_id": "rechtspraak_etl",
        "run_id": "scheduled__2026-08-31T02:00:00+00:00",
        "window_start": "2026-07-01",
        "window_end": "2026-09-01",
        "requested_by": "airflow",
    }
    assert len(request.call_args_list) == 2


def test_check_promoter_rejects_background_auto_promotion():
    with patch.object(
        promotion_client,
        "promoter_json",
        return_value={"ready": True, "auto_promote": True, "problems": []},
    ):
        with pytest.raises(RuntimeError, match="must be false"):
            promotion_client.check_promoter_ready()


def test_promote_source_calls_and_waits_for_each_batch():
    cfg = {
        "url": "http://etl-promoter:8080",
        "token": "token",
        "request_timeout": 30,
        "wait_seconds": 60,
        "poll_seconds": 1,
        "minimum_age_hours": 48,
    }
    listing = {
        "batches": [
            {
                "batch_id": "batch-1",
                "status": "verified",
                "created_at": "2026-09-01T03:00:00+00:00",
                "verified_at": "2026-09-01T04:00:00+00:00",
            }
        ]
    }
    with patch.object(promotion_client, "client_settings", return_value=cfg), patch.object(
        promotion_client, "promoter_json", side_effect=[listing, {"status": "verified"}]
    ) as request, patch.object(
        promotion_client, "_wait_for", return_value={"status": "promoted"}
    ):
        with patch.object(promotion_client, "select_batches_for_run", return_value=listing["batches"]):
            result = promotion_client.promote_source_batches("cellar_etl")

    assert result == ["batch-1"]
    assert request.call_args_list[1].kwargs["method"] == "POST"


def test_lido_promotion_is_skipped_unless_enabled(monkeypatch):
    monkeypatch.delenv("ETL_PROMOTION_LIDO_ENABLED", raising=False)
    with patch.object(promotion_client, "promoter_json") as promoter_json:
        assert promotion_client.promote_source_batches("lido_sqlite_build") == []
    promoter_json.assert_not_called()


def test_lido_promotion_runs_when_enabled(monkeypatch):
    monkeypatch.setenv("ETL_PROMOTION_LIDO_ENABLED", "true")
    with patch.object(promotion_client, "promoter_json", return_value={"batches": []}) as promoter_json:
        assert promotion_client.promote_source_batches("lido_sqlite_build") == []
    promoter_json.assert_called_once()
