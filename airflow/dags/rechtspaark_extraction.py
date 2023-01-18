from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from data_extraction.caselaw.rechtspraak.rechtspraak_extraction import rechtspraak_extract

default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=2)
}
with DAG(
        dag_id='rechtspraak',
        default_args=default_args,
        description=' Still in process',
        start_date=datetime.now(),
        schedule_interval='@daily'

) as DAG:
    task1 = PythonOperator(
        task_id='rechtspraak_extraction',
        python_callable=rechtspraak_extract,
        op_args=[['local', '--amount 100']]
    )
