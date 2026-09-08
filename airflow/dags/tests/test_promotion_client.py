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


def test_failed_promotion_is_selected_for_idempotent_retry():
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
