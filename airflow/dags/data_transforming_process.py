from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from data_transformation.data_transformer import transform_data

default_args = {
    'owner': 'airflow',
    # 'retries': 5,
    # 'retry_delay': timedelta(minutes=1)
}

with DAG(
        dag_id='data_transformation',
        default_args=default_args,
        description='works well',
        start_date=datetime.now()

) as DAG:
    task1 = PythonOperator(
        task_id='data_transformation',
        python_callable=transform_data,
        op_args=[['local']]
    )
