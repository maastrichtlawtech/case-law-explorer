from datetime import datetime, timedelta

from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator
from segmentation.tasks.call_segmentation_api import call_segmentation_api
from segmentation.tasks.fetch_unsegmented_cases import fetch_unsegmented_cases
from segmentation.tasks.write_segments import write_segments

from airflow import DAG

CASE_SEGMENTS_DATASET = Dataset("cle_v2://case_segment")

default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=5)}

with DAG(
    dag_id="case_segmentation",
    default_args=default_args,
    description="Segment case full text via legal-summarizer-service, write cle_v2.case_segment",
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,  # triggered after the *_etl DAGs, same pattern as echr_db_setup.py
    catchup=False,
    tags=["caselaw", "summarization"],
) as dag:
    fetch = PythonOperator(
        task_id="fetch_unsegmented_cases",
        python_callable=fetch_unsegmented_cases,
    )

    segment = PythonOperator(
        task_id="call_segmentation_api",
        python_callable=call_segmentation_api,
    )

    write = PythonOperator(
        task_id="write_segments",
        python_callable=write_segments,
        outlets=[CASE_SEGMENTS_DATASET],
    )

    fetch >> segment >> write
