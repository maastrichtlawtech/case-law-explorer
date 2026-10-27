from datetime import datetime, timedelta

from airflow.operators.python import PythonOperator
from segmentation.config import CASE_SEGMENTS_DATASET
from summarization.tasks.call_summarization_api import call_summarization_api
from summarization.tasks.fetch_cases_needing_summary import fetch_cases_needing_summary
from summarization.tasks.write_summary import write_summary

from airflow import DAG

default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=5)}

with DAG(
    dag_id="case_summarization",
    default_args=default_args,
    description="Summarize segmented cases via legal-summarizer-service, write cle_v2.case_summary_version",
    start_date=datetime(2026, 1, 1),  # required by Airflow even for dataset-scheduled DAGs
    schedule=[CASE_SEGMENTS_DATASET],  # runs whenever case_segmentation produces new segments
    catchup=False,
    tags=["caselaw", "summarization"],
) as dag:
    fetch = PythonOperator(
        task_id="fetch_cases_needing_summary",
        python_callable=fetch_cases_needing_summary,
    )

    summarize = PythonOperator(
        task_id="call_summarization_api",
        python_callable=call_summarization_api,
    )

    write = PythonOperator(
        task_id="write_summary",
        python_callable=write_summary,
    )

    fetch >> summarize >> write
