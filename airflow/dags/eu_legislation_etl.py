"""Weekly EU legislation metadata sync and law-reference resolution DAG.

Runs after the weekly Cellar/Rechtspraak/ECtHR ETLs: discovers any newly cited
EU CELEX acts in `cle_v2.case_law_reference` that are missing from
`cle_v2.legislation`, fetches their official title/date/ELI/type from EUR-Lex
CELLAR's public SPARQL endpoint, inserts them idempotently, and resolves the
pending `case_law_reference.legislation_id` links.
"""

import logging
import os
from datetime import datetime

from airflow.operators.python import PythonOperator
from data_extraction.legislation.cellar_legislation_sync import sync_connection
from dotenv import find_dotenv, load_dotenv
from etl_factory import DEFAULT_ARGS, get_schedule

from airflow import DAG

dag = DAG(
    dag_id="eu_legislation_etl",
    default_args=DEFAULT_ARGS,
    description="Sync unresolved EU legislation CELEX acts from Cellar SPARQL and resolve case_law_reference",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule=get_schedule("EU_LEGISLATION", "0 6 * * 1"),
    max_active_runs=1,
    max_active_tasks=1,
)


def run_eu_legislation_sync(**_kwargs):
    import psycopg2

    load_dotenv(find_dotenv(), override=True)
    host = os.environ.get("POSTGRES_HOST", "db-dev")
    port = os.environ.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB", "cle_v2")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    dsn = os.environ.get(
        "POSTGRES_DSN",
        f"host={host} port={port} dbname={dbname} user={user} password={password}",
    )
    conn = psycopg2.connect(dsn)
    try:
        summary = sync_connection(conn)
    finally:
        conn.close()
    logging.info("EU legislation sync complete: %s", summary)
    return summary


sync_task = PythonOperator(
    task_id="sync_eu_legislation_from_cellar",
    python_callable=run_eu_legislation_sync,
    dag=dag,
)
