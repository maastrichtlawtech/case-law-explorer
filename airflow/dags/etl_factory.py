"""
Shared machinery for the monthly caselaw ETL DAGs (rechtspraak_etl,
cellar_etl, echr_etl). Each DAG supplies its own extraction logic; the
month iteration, task-group wiring, config lookup, and raw-file cleanup
policy live here so the three DAGs stay in sync.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import date, datetime, timedelta

from airflow.models.variable import Variable
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

DEFAULT_ARGS = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}


def get_var(name, default=None):
    """Airflow Variable with an environment-variable fallback (docker-compose
    loads .env into the containers, so both places work)."""
    return Variable.get(name, default_var=os.getenv(name, default))


def get_data_path():
    return get_var("DATA_PATH", "/opt/airflow/data")


def get_month_end(date):
    """Last day of `date`'s month, as a datetime."""
    last_day = monthrange(date.year, date.month)[1]
    return datetime(date.year, date.month, last_day)


def get_schedule(var_prefix, default):
    """Return a configurable cron schedule, with ``none`` disabling it."""
    value = str(get_var(f"{var_prefix}_SCHEDULE", default) or "").strip()
    return None if value.lower() in {"", "none", "null", "off"} else value


def get_optional_int(name):
    """Return an optional positive extraction cap; blank/none/all means no cap."""
    value = str(get_var(name, "") or "").strip()
    if value.lower() in {"", "none", "all", "unlimited"}:
        return None
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{name} must be positive, blank, or 'all'")
    return parsed


def _as_date(value, field):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc


def resolve_run_window(var_prefix, context):
    """Resolve the inclusive source window for a manual or scheduled run.

    Controller/UI runs may provide ``window_start`` and ``window_end`` in
    dag_run.conf. Scheduled runs refresh the previous and current calendar
    month, which catches late publications while reusing stable artifact
    directories. A manual UI run without conf uses the configured backfill
    dates.
    """
    dag_run = context.get("dag_run")
    conf = (getattr(dag_run, "conf", None) or {}) if dag_run else {}
    configured_start = conf.get("window_start")
    configured_end = conf.get("window_end")
    if configured_start or configured_end:
        if not configured_start or not configured_end:
            raise ValueError("window_start and window_end must be supplied together")
        start = _as_date(configured_start, "window_start")
        end = _as_date(configured_end, "window_end")
        scheduled = False
    else:
        run_id = str(getattr(dag_run, "run_id", ""))
        run_type = str(getattr(dag_run, "run_type", "")).lower()
        scheduled = run_id.startswith("scheduled__") or "scheduled" in run_type
        if scheduled:
            interval_end = context.get("data_interval_end") or context.get("logical_date")
            if interval_end is None:
                raise ValueError("scheduled run has no data_interval_end")
            end = _as_date(interval_end, "data_interval_end") - timedelta(days=1)
            current_month = end.replace(day=1)
            previous_month_end = current_month - timedelta(days=1)
            start = previous_month_end.replace(day=1)
        else:
            start = _as_date(get_var(f"{var_prefix}_START_DATE"), f"{var_prefix}_START_DATE")
            end = _as_date(get_var(f"{var_prefix}_END_DATE"), f"{var_prefix}_END_DATE")
    if start > end:
        raise ValueError("window_start must not be after window_end")
    return start, end, scheduled


def run_monthly_window(var_prefix, etl_callable, **context):
    """Run one source window in sequential month-sized chunks."""
    start, end, scheduled = resolve_run_window(var_prefix, context)
    logging.info("Resolved %s window %s to %s", var_prefix, start, end)
    current = start
    while current <= end:
        chunk_end = min(
            date(current.year, current.month, monthrange(current.year, current.month)[1]),
            end,
        )
        etl_callable(
            start_date=datetime.combine(current, datetime.min.time()),
            end_date=datetime.combine(chunk_end, datetime.min.time()),
            _data_path=get_data_path(),
            force_refresh=scheduled,
        )
        current = chunk_end + timedelta(days=1)


def register_promotion(dag_id, var_prefix=None, **context):
    """Register the successful run for verification and optional promotion."""
    if str(os.getenv("ETL_PROMOTION_ENABLED", "false")).lower() not in {
        "true",
        "1",
        "yes",
    }:
        logging.info("ETL promotion is disabled; no batch registered")
        return None
    token = os.getenv("ETL_PROMOTER_INTERNAL_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ETL_PROMOTER_INTERNAL_TOKEN is required when promotion is enabled")
    dag_run = context.get("dag_run")
    run_id = str(getattr(dag_run, "run_id", ""))
    if not run_id:
        raise RuntimeError("Airflow run_id is unavailable")
    conf = (getattr(dag_run, "conf", None) or {}) if dag_run else {}
    requested_by = str(conf.get("requested_by") or "airflow")
    payload = {"dag_id": dag_id, "run_id": run_id, "requested_by": requested_by}
    if var_prefix:
        start, end, _ = resolve_run_window(var_prefix, context)
        payload.update(window_start=start.isoformat(), window_end=end.isoformat())
    url = os.getenv("ETL_PROMOTER_INTERNAL_URL", "http://etl-promoter:8080").rstrip("/")
    request = urllib.request.Request(
        f"{url}/v1/batches",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-ETL-Promoter-Token": token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError("ETL promoter registration failed") from exc
    logging.info("Registered promotion batch %s", result.get("batch_id"))
    return result


def cleanup_raw_files(paths):
    """Remove raw extraction files, but only when ETL_CLEANUP_RAW is enabled.

    Default is to keep them: raw files are the cheapest thing to store and
    the most expensive thing to regenerate (source APIs are slow and flaky),
    and the skip-if-exists checks in the DAGs depend on them surviving.
    """
    if str(get_var("ETL_CLEANUP_RAW", "false")).lower() not in ("true", "1", "yes"):
        logging.info("Keeping raw files (set ETL_CLEANUP_RAW=true to remove them)")
        return
    for file_path in paths:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Removed {file_path}")
            except OSError as e:
                logging.warning(f"Could not remove {file_path}: {e}")


def build_monthly_task_group(dag, task_prefix, var_prefix, etl_callable):
    """
    One sequential task which resolves its window at run time and invokes the
    source callable in month-sized chunks. This keeps historical backfills and
    scheduled refreshes on the existing DAG without parallel source bursts.
    """
    with TaskGroup(f"{task_prefix}_tasks", tooltip=f"{task_prefix} tasks", dag=dag) as task_group:
        PythonOperator(
            task_id="run_window",
            python_callable=run_monthly_window,
            op_kwargs={"var_prefix": var_prefix, "etl_callable": etl_callable},
            dag=dag,
        )

    return task_group
