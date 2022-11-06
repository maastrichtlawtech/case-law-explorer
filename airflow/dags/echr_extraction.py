from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from data_extraction.caselaw.echr.ECHR_metadata_harvester import echr_download

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
        python_callable=echr_download,
        op_args=[['local']]
    )