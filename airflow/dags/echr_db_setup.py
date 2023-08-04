"""
ECHR DB setup DAG.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from data_extraction.caselaw.echr.db_setup import setup_db

default_args = {
    'owner': 'none',
    'retries': 0
}
with DAG(
        dag_id='echr_db_setup',
        default_args=default_args,
        description='fully implemented',
        start_date=datetime.now(),
        schedule_interval=None

) as DAG:
    task1 = PythonOperator(
        task_id='echr_db_setup',
        python_callable=setup_db
    )
    task2 = TriggerDagRunOperator(
        trigger_dag_id='data_transformation',
        task_id='data_transformation',
        wait_for_completion=True
    )
    task3 = TriggerDagRunOperator(
        trigger_dag_id='data_loading',
        task_id='data_loading',
        wait_for_completion=True
    )

# Extraction -> Transformation -> Loading
task1 >> task2 >> task3
