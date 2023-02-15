from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from data_extraction.caselaw.echr.echr_extraction import echr_extract
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
        dag_id='echr_extraction',
        default_args=default_args,
        description=' Still in process',
        start_date=datetime.now(),
        schedule_interval='@daily'

) as DAG:
    task1 = PythonOperator(
        task_id='echr_extraction',
        python_callable=echr_extract,
        op_args=[['local','--count 100']]
    )
    task2 = TriggerDagRunOperator(
        trigger_dag_id='data_transformation',
        task_id='data_transformation'
    )
    task3 = TriggerDagRunOperator(
        trigger_dag_id='data_loading',
        task_id='data_loading'
    )
task1 >> task2 >> task3
