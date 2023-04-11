from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from helpers.log_cleanup import log_clean

default_args = {
    'owner': 'airflow'

}

with DAG(
        dag_id='log_cleaner',
        default_args=default_args,
        description='testing',
        start_date=datetime.now(),
        schedule_interval='1 1 1 * *'

) as DAG:
    task1 = PythonOperator(
        task_id='log_cleaner',
        python_callable=log_clean
    )
