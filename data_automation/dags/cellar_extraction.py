from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
    dag_id='our_first_shit',
    default_args = default_args,
    description =' LMAO ded',
    start_date=datetime(2022,7,20),
    schedule_interval='@daily'

) as DAG:
    task1 = BashOperator(
        task_id = 'cellar_extraction',
        bash_command = 'python ./data_extraction/caselaw/cellar/cellar_extraction.py local'
    )

    task2 = BashOperator(
        task_id = '',
        bash_command='python ./data_extraction/caselaw/cellar/cellar_extraction.py local'
    )

    task2 = BashOperator(
        task_id='',
        bash_command='python ./data_extraction/caselaw/cellar/cellar_extraction.py local'
    )