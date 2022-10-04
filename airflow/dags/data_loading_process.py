from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from data_loading.data_loader import load_data

default_args = {
    'owner': 'airflow',
    # 'retries': 5,
    # 'retry_delay': timedelta(minutes=1)
}

with DAG(
        dag_id='data_loading',
        default_args=default_args,
        description='seems to be working :)',
        start_date=datetime.now(),
        schedule_interval='10 * * * *'

) as DAG:
    task1 = PythonOperator(
        task_id='data_loading',
        python_callable=load_data,
        op_args=[['aws']]
    )
