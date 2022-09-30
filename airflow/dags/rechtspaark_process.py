from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from data_extraction.caselaw.rechtspraak.rechtspraak_api import rechspraak_downloader
from data_transformation.data_transformer import transform_data
default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
    dag_id='rechtspaark_process',
    default_args = default_args,
    description =' Still in process',
    start_date=datetime(2022,9,24,hour=10,minute=15),
    schedule_interval='@daily'

) as DAG:
    task1 = PythonOperator(
        task_id='Rechtspraak_data_extract',
        python_callable=rechspraak_downloader,
        op_args=[['--max', '10', '--starting-date', '2022-08-28']]
    )
    task2 = PythonOperator(
        task_id='Rechtspraak_data_transformation',
        python_callable=transform_data,
        op_args =[['local']]
    )

    task1 >> task2
