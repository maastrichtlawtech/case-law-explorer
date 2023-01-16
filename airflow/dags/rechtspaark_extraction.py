from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

from data_extraction.caselaw.rechtspraak.rechtspraak import get_rechtspraak
from data_extraction.caselaw.rechtspraak.rechtspraak_metadata import get_rechtspraak_metadata

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
        python_callable=get_rechtspraak,

        # op_kwargs={'max_ecli': 50,
        #            'sd': '2022-08-01',
        #             'save_file': 'y'}
    )
   # task2 = PythonOperator(
    #    task_id='rechtspraak_metadata_extraction',
   #     python_callable=get_rechtspraak_metadata,
   #     op_kwargs={'save_file': 'n'}
  #  )
