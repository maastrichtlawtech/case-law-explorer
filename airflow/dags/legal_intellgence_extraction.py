from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from data_extraction.caselaw.legal_intelligence.legal_intelligence_extractor import li_extract

default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
        dag_id='legal_intelligence_extraction',
        default_args=default_args,
        description=' Still in process',
        start_date=datetime.now(),
        schedule_interval='@daily'

) as DAG:
    task1 = PythonOperator(
        task_id='legal_intelligence_extraction',
        python_callable=li_extract,
        op_args=[['local']]
    )
