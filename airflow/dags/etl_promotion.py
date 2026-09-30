"""Monitor and promote verified db-dev ETL batches into production.

Production access remains isolated in the etl-promoter service. This DAG is
the Airflow control plane: it can be paused, run manually, and inspected like
the source DAGs while only calling the promoter's narrow internal API.
"""

from datetime import datetime

from airflow.operators.python import PythonOperator
from etl_factory import DEFAULT_ARGS, get_schedule
from promotion_client import check_promoter_ready, promote_source_batches

from airflow import DAG


dag = DAG(
    dag_id="etl_promotion",
    default_args=DEFAULT_ARGS,
    description="Verify and promote mature db-dev ETL batches into production",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule=get_schedule("ETL_PROMOTION", "0 6 * * 4"),
    max_active_runs=1,
    is_paused_upon_creation=True,
)


with dag:
    readiness = PythonOperator(
        task_id="check_promoter_ready",
        python_callable=check_promoter_ready,
    )

    for task_id, source_dag_id in (
        ("promote_rechtspraak", "rechtspraak_etl"),
        ("promote_cellar", "cellar_etl"),
        ("promote_echr", "echr_etl"),
        ("promote_lido", "lido_sqlite_build"),
    ):
        promotion = PythonOperator(
            task_id=task_id,
            python_callable=promote_source_batches,
            op_kwargs={"source_dag_id": source_dag_id},
        )
        readiness >> promotion
