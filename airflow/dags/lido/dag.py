
from datetime import datetime, timedelta
import os
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from lido.tasks.turtle_to_triple import task_make_cases_nt, task_make_laws_nt
from lido.tasks.laws_to_sqlite import process_law_triples
from lido.tasks.cases_to_sqlite import process_case_triples
from lido.config import *

os.makedirs(DIR_DATA_LIDO, exist_ok=True)

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'process-lido-for-postgres',
    default_args=default_args,
    description='Update postgresdb with data from lido export on data.overheid.nl',
    schedule_interval='@monthly',
    start_date=datetime(2025, 1, 1),
    tags=['linkextractor', 'lido'],
) as dag:
    
    # process lido.ttl
    download_lido_ttl = BashOperator(
        task_id='download_lido_ttl',
        bash_command=('curl -sSLf {url} -o {output}').format(
            url='https://linkeddata.overheid.nl/export/lido-export.ttl.gz',
            dir=FILE_LIDO_TTL_GZ
        )
    )

    check_lido_ttl = BashOperator(
        task_id='check_lido_ttl',
        bash_command=f'test -f {FILE_LIDO_TTL_GZ}'
    )
    
    # lido.ttl -> cases.nt, laws.nt
    make_laws_nt = task_make_laws_nt(dag)
    make_cases_nt = task_make_cases_nt(dag)

    check_laws_nt = BashOperator(
        task_id='check_laws_nt',
        bash_command=f'test -f {FILE_LAWS_NT}'
    )

    check_cases_nt = BashOperator(
        task_id='check_cases_nt',
        bash_command=f'test -f {FILE_CASES_NT}'
    )

    # laws.nt, cases.nt -> sqlite
    laws_to_sqlite = PythonOperator(
        task_id="laws_to_sqlite",
        python_callable=process_law_triples,
        op_args=[FILE_SQLITE_DB, FILE_LAWS_NT]
    )

    cases_to_sqlite = PythonOperator(
        task_id="cases_to_sqlite",
        python_callable=process_case_triples,
        op_args=[FILE_SQLITE_DB, FILE_CASES_NT]
    )
    
    check_stage_db = BashOperator(
        task_id='check_stage_db',
        bash_command=f'test -f {FILE_SQLITE_DB}'
    )

    # sqlite -> csv

    # csv -> server


    download_lido_ttl >> check_lido_ttl \
    >> [make_laws_nt, make_cases_nt] >> [check_laws_nt, check_cases_nt] \
    >> laws_to_sqlite >> cases_to_sqlite >> check_stage_db \
    
