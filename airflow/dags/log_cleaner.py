"""
EC2 log cleanup DAG.
This dag cleans up all of the logs on the EC2 instance, as logs tend up to get quite big in size.
"""

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
        description='fully implemented',
        start_date=datetime.now(),
        schedule_interval='@monthly'

) as DAG:
    task1 = PythonOperator(
        task_id='log_cleaner',
        python_callable=log_clean
    )
