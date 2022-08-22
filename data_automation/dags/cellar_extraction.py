from datetime import datetime, timedelta
import sys
sys.path.append('data_extraction/caselaw/cellar')
import cellar_extraction
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
    dag_id='cellar extraction',
    default_args = default_args,
    description =' Still in process',
    start_date=datetime(2022,7,20),
    schedule_interval='@daily'

) as DAG:
    task_extraction = BashOperator(
        task_id = 'cellar_extraction',
        #python_command = cellar_extraction.
        # op_kwargs={'age': 10}
    )

    task2 = BashOperator(
        task_id = '',
        #python_command = cellar_transformation.
    )

    task2 = BashOperator(
        task_id='',
        #python_command = csv_extractor
    )