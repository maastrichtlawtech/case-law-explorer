"""Internal client used by the scheduled db-dev to production promotion DAG.

The production credential remains inside ``etl-promoter``.  Airflow only has
the promoter's narrow internal token and asks it to verify/status/promote
registered ETL batches.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


SOURCE_DAG_IDS = (
    "rechtspraak_etl",
    "cellar_etl",
    "echr_etl",
    "lido_sqlite_build",
)


def _positive_int(name, default):
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def client_settings():
    return {
        "url": os.getenv(
            "ETL_PROMOTER_INTERNAL_URL", "http://etl-promoter:8080"
        ).rstrip("/"),
        "token": os.getenv("ETL_PROMOTER_INTERNAL_TOKEN", "").strip(),
        "request_timeout": _positive_int("ETL_PROMOTER_API_TIMEOUT_SECONDS", 30),
        "wait_seconds": _positive_int("ETL_PROMOTION_DAG_WAIT_SECONDS", 21600),
        "poll_seconds": _positive_int("ETL_PROMOTION_DAG_POLL_SECONDS", 30),
        "minimum_age_hours": _positive_int("ETL_PROMOTION_MIN_AGE_HOURS", 48),
    }


def promoter_json(path, method="GET", payload=None, authenticated=True, cfg=None):
    cfg = cfg or client_settings()
    if authenticated and not cfg["token"]:
        raise RuntimeError("ETL_PROMOTER_INTERNAL_TOKEN is required")
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if authenticated:
        headers["X-ETL-Promoter-Token"] = cfg["token"]
    request = urllib.request.Request(
        f"{cfg['url']}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=cfg["request_timeout"]) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"ETL promoter returned HTTP {exc.code} for {method} {path}: {detail}"
        ) from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ETL promoter request failed for {method} {path}") from exc


def check_promoter_ready(**_context):
    health = promoter_json("/healthz", authenticated=False)
    if not health.get("ready"):
        raise RuntimeError(f"ETL promoter is not ready: {health.get('problems', [])}")
    if health.get("auto_promote"):
        raise RuntimeError(
            "ETL_PROMOTION_AUTO_PROMOTE must be false when promotion is controlled by Airflow"
        )
    logging.info(
        "Promoter ready: %s -> %s",
        health.get("dev_host"),
        health.get("production_host"),
    )
    return health


def _timestamp(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def select_batches_for_run(batches, minimum_age_hours, now=None):
    """Select ordered, mature batches after the latest successful promotion."""
    now = now or datetime.now(timezone.utc)
    promoted_times = [
        _timestamp(batch.get("created_at"))
        for batch in batches
        if batch.get("status") == "promoted"
    ]
    promoted_times = [value for value in promoted_times if value is not None]
    cutoff = max(promoted_times) if promoted_times else None
    pending = []
    failures = []
    minimum_age = timedelta(hours=minimum_age_hours)

    for batch in sorted(batches, key=lambda item: item.get("created_at") or ""):
        created_at = _timestamp(batch.get("created_at"))
        if batch.get("status") == "promoted" or not created_at:
            continue
        if cutoff is not None and created_at <= cutoff:
            continue
        if batch.get("status") == "failed":
            if batch.get("failed_stage") == "promotion":
                pending.append(batch)
            else:
                failures.append(batch)
            continue
        mature_at = _timestamp(batch.get("verified_at")) or created_at
        if batch.get("status") == "promoting" or now - mature_at >= minimum_age:
            pending.append(batch)

    if failures:
        details = "; ".join(
            f"{batch.get('batch_id')}: {batch.get('error') or 'verification failed'}"
            for batch in failures
        )
        raise RuntimeError(f"Unresolved failed promotion batches: {details}")
    return pending


def _batch(batch_id, cfg):
    return promoter_json(f"/v1/batches/{urllib.parse.quote(batch_id, safe='')}", cfg=cfg)


def _wait_for(batch_id, accepted_states, cfg):
    deadline = time.monotonic() + cfg["wait_seconds"]
    while True:
        batch = _batch(batch_id, cfg)
        status = batch.get("status")
        if status == "failed":
            raise RuntimeError(
                f"Promotion batch {batch_id} failed: {batch.get('error') or 'unknown error'}"
            )
        if status in accepted_states:
            return batch
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Promotion batch {batch_id} did not reach {sorted(accepted_states)} "
                f"within {cfg['wait_seconds']} seconds (current status: {status})"
            )
        time.sleep(cfg["poll_seconds"])


def promote_source_batches(source_dag_id, **_context):
    if source_dag_id not in SOURCE_DAG_IDS:
        raise ValueError(f"Unsupported source DAG: {source_dag_id}")
    cfg = client_settings()
    query = urllib.parse.urlencode({"dag_id": source_dag_id})
    listing = promoter_json(f"/v1/batches?{query}", cfg=cfg)
    pending = select_batches_for_run(
        listing.get("batches", []), cfg["minimum_age_hours"]
    )
    if not pending:
        logging.info(
            "No verified %s batches are at least %s hours old",
            source_dag_id,
            cfg["minimum_age_hours"],
        )
        return []

    promoted = []
    for summary in pending:
        batch_id = summary["batch_id"]
        status = summary.get("status")
        if status == "verifying":
            status = _wait_for(batch_id, {"verified", "promoted"}, cfg)["status"]
        if status in {"verified", "failed"}:
            promoter_json(
                f"/v1/batches/{urllib.parse.quote(batch_id, safe='')}/promote",
                method="POST",
                payload={},
                cfg=cfg,
            )
            status = "promoting"
        if status == "promoting":
            _wait_for(batch_id, {"promoted"}, cfg)
        promoted.append(batch_id)
        logging.info("Promoted %s batch %s", source_dag_id, batch_id)
    return promoted
