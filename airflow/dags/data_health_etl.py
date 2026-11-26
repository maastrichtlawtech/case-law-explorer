"""Scheduled daily Data Health Overview DAG (read-only reporting).

Completely independent of every ingestion, enrichment, and promotion DAG:
never blocks or fails other pipelines. Collects a full health overview of:
  - ``db-dev`` (directly via PostgresCLEClient)
  - live production ``db`` (via ``etl-promoter``'s authenticated
    ``POST /v1/health-report`` endpoint, when promotion is configured)

Writes dated and latest JSON/Markdown reports under ``$DATA_PATH/health/``,
persists snapshots into ``cle_v2.etl_health_snapshot``, logs the full Markdown
overview, and optionally notifies ``HEALTH_REPORT_WEBHOOK_URL``.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from airflow.operators.python import PythonOperator
from dotenv import find_dotenv, load_dotenv
from etl_factory import DEFAULT_ARGS, get_data_path, get_schedule

from airflow import DAG

dag = DAG(
    dag_id="data_health_etl",
    default_args=DEFAULT_ARGS,
    description="Daily read-only dataset health overview (freshness, completeness, links, law refs, authorities, outcomes)",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule=get_schedule("HEALTH_REPORT", "0 7 * * *"),
    max_active_runs=1,
    max_active_tasks=2,
)


def _write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(tmp, path)


def run_dev_health_report(**_context):
    load_dotenv(find_dotenv(), override=True)
    import data_health
    from data_loading.clients.postgres import PostgresCLEClient

    data_path = get_data_path()
    cache_dir = os.path.join(data_path, "cache")
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        report = data_health.collect_health_report(conn, target="db-dev", cache_dir=cache_dir)
        data_health.save_snapshot(conn, report)

    md = data_health.render_markdown(report)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    health_dir = os.path.join(data_path, "health")
    _write_text(os.path.join(health_dir, "dev-latest.json"), json.dumps(report, indent=2, sort_keys=True))
    _write_text(os.path.join(health_dir, "dev-latest.md"), md)
    _write_text(os.path.join(health_dir, f"dev-{day}.json"), json.dumps(report, indent=2, sort_keys=True))
    logging.info("\n%s", md)
    return {"target": "db-dev", "status": report["status"], "alerts": len(report["alerts"])}


def run_production_health_report(**_context):
    load_dotenv(find_dotenv(), override=True)
    import data_health

    token = os.getenv("ETL_PROMOTER_INTERNAL_TOKEN", "").strip()
    if not token:
        logging.info("ETL_PROMOTER_INTERNAL_TOKEN unset; skipping production health snapshot")
        return {"skipped": True, "reason": "no_promoter_token"}

    url = os.getenv("ETL_PROMOTER_INTERNAL_URL", "http://etl-promoter:8080").rstrip("/")
    req = urllib.request.Request(
        f"{url}/v1/health-report",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-ETL-Promoter-Token": token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logging.warning("Production health snapshot request failed (non-fatal): %s", exc)
        return {"skipped": True, "reason": str(exc)}

    report = payload.get("report") or {}
    md = payload.get("markdown") or data_health.render_markdown(report)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    health_dir = os.path.join(get_data_path(), "health")
    _write_text(os.path.join(health_dir, "latest.json"), json.dumps(report, indent=2, sort_keys=True))
    _write_text(os.path.join(health_dir, "latest.md"), md)
    _write_text(os.path.join(health_dir, f"prod-{day}.json"), json.dumps(report, indent=2, sort_keys=True))
    logging.info("\n%s", md)

    webhook = os.getenv("HEALTH_REPORT_WEBHOOK_URL", "").strip()
    if webhook:
        data_health.post_webhook(webhook, report, md)

    return {
        "target": "production",
        "status": report.get("status"),
        "alerts": len(report.get("alerts") or []),
        "snapshot_id": payload.get("snapshot_id"),
    }


with dag:
    # Both tasks are independent and run in parallel with zero dependencies.
    PythonOperator(
        task_id="report_dev_health",
        python_callable=run_dev_health_report,
    )
    PythonOperator(
        task_id="report_production_health",
        python_callable=run_production_health_report,
    )
