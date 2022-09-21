from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator

default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
    dag_id='rechtspaark_process',
    default_args = default_args,
    description =' Still in process',
    start_date=datetime(2022,7,20),
    schedule_interval='@daily'

) as DAG:
    task1 = BashOperator(
        task_id='rechtspraak_dump_downloader',
        bash_command='python ./data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader local'
    )
    task2 = BashOperator(
        task_id='rechtspraak_dump_unzipper',
        bash_command='python ./data_extraction/caselaw/rechtspraak/rechtspraak_dump_unzipper'
    )
    task3 = BashOperator(
        task_id='rechtspraak_dump_downloader',
        bash_command='python ./data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader local'
    )
