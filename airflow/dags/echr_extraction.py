"""
DEPRECATED: ECHR extraction DAG.
This DAG has been replaced by echr_etl.py which provides monthly task groups
and individual task retriggering capabilities.

Please use echr_etl.py instead.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'none',
    'retries': 0,
    'retry_delay': timedelta(minutes=1)
}

with DAG(
        dag_id='echr_extraction_deprecated',
        default_args=default_args,
        description='DEPRECATED: Use echr_etl.py instead',
        start_date=datetime(2025, 1, 1),
        schedule_interval=None,
        tags=['deprecated']

) as DAG:
    PythonOperator(
        task_id='deprecation_notice',
        python_callable=lambda: print("This DAG is deprecated. Please use echr_etl.py instead.")
    )
