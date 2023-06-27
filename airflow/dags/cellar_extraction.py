"""
CELLAR extraction DAG.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from data_extraction.caselaw.cellar.cellar_extraction import cellar_extract

default_args = {
    'owner': 'airflow',
    # 'retries': 5,
    # 'retry_delay': timedelta(minutes=1)
}

with DAG(
        dag_id='cellar_extraction',
        default_args=default_args,
        description='fully implemented',
        start_date=datetime.now(),
        schedule_interval='10 1 * * *'

) as DAG:
    task1 = PythonOperator(
        task_id='cellar_extraction',
        python_callable=cellar_extract,
        op_args=[['--amount', '100', '--starting-date', '2023-03-03']]
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
