from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from data_extraction.caselaw.cellar.cellar_extraction import cellar_extract
default_args = {
    'owner': 'airflow',
    # 'retries': 5,
    # 'retry_delay': timedelta(minutes=1)
}

with DAG(
        dag_id='cellar_extraction',
        default_args=default_args,
        description='local working need to check aws',
        start_date=datetime.now(),
        schedule_interval='10 * * * *'

) as DAG:
    task1 = PythonOperator(
        task_id='cellar_extraction',
        python_callable=cellar_extract,
        op_args=['local']
    )
