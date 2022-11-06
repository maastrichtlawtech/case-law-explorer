from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from data_extraction.caselaw.rechtspraak.rechtspraak_api import rechspraak_downloader
from rechtspraak_extractor import get_rechtspraak_metadata 
default_args = {
    'owner': 'none',
    'retries': 5,
    'retry_delay': timedelta(minutes=5)
}


with DAG(
        dag_id='rechtspaark_extraction',
        default_args=default_args,
        description=' Still in process',
        start_date=datetime.now(),
        schedule_interval='@daily'

) as DAG:
    task1 = PythonOperator(
        task_id='rechtspraak_extraction',
        python_callable=get_rechtspraak_metadata,
        op_kwargs={'max_ecli':'50',
                    'sd':'2022-08-01',
                    'save_file':'y'}
    )
