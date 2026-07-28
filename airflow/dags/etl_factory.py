"""
Shared machinery for the monthly caselaw ETL DAGs (rechtspraak_etl,
cellar_etl, echr_etl). Each DAG supplies its own extraction logic; the
month iteration, task-group wiring, config lookup, and raw-file cleanup
policy live here so the three DAGs stay in sync.
"""

import logging
import os
from calendar import monthrange
from datetime import datetime, timedelta

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
    One PythonOperator per month between {var_prefix}_START_DATE and
    {var_prefix}_END_DATE (Airflow Variables, .env fallback). Each task
    calls etl_callable(start_date=..., end_date=..., _data_path=...).
    """
    start_date = get_var(f"{var_prefix}_START_DATE")
    end_date = get_var(f"{var_prefix}_END_DATE", datetime.now().strftime("%Y-%m-%d"))

    if not start_date or not end_date:
        raise ValueError(
            f"{var_prefix}_START_DATE and {var_prefix}_END_DATE are required in Airflow variables."
        )

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    logging.info(f"Creating {task_prefix} tasks for {start_date} to {end_date}")

    with TaskGroup(f"{task_prefix}_tasks", tooltip=f"{task_prefix} tasks", dag=dag) as task_group:
        current_date = start_date
        while current_date <= end_date:
            month_end = min(get_month_end(current_date), end_date)

            PythonOperator(
                task_id=f"{task_prefix}_{current_date.strftime('%Y-%m')}",
                python_callable=etl_callable,
                op_kwargs={
                    "start_date": current_date,
                    "end_date": month_end,
                    "_data_path": get_data_path(),
                },
                dag=dag,
            )

            current_date = month_end + timedelta(days=1)

    return task_group
