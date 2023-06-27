"""
Data transformation DAG.
Does not actually run itself but !!it has to be active on airflow!!.
Only externally triggered by the extraction dags.
"""

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
        description='fully implemented',
        start_date=datetime.now(),
        schedule_interval=None

) as DAG:
    task1 = PythonOperator(
        task_id='data_transformation',
        python_callable=transform_data
    )
