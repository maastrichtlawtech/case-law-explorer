"""
RS extraction DAG.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from data_extraction.caselaw.rechtspraak.rechtspraak_extraction import rechtspraak_extract

default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=2)
}
with DAG(
        dag_id='rechtspraak',
        default_args=default_args,
        description='fully implemented',
        start_date=datetime.now(),
        schedule_interval='@weekly'

) as DAG:
    task1 = PythonOperator(
        task_id='rechtspraak_extraction',
        python_callable=rechtspraak_extract
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
