
from datetime import datetime, timedelta
from airflow import DAG
from airflow.utils.task_group import TaskGroup
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

from dags.lido.tasks.swap_postres import task_create_staging_tables, task_load_csv, task_swap_tables
from lido.tasks.bwbidlist_to_sqlite import task_bwbidlist_to_sqlite
from lido.tasks.prepare_bwbidlist import task_bwbidlist_xml_to_json, task_unzip_bwbidlist
from lido.tasks.init_sqlite import task_init_sqlite
from lido.tasks.turtle_to_triple import task_make_cases_nt, task_make_laws_nt
from lido.tasks.laws_to_sqlite import process_law_triples
from lido.tasks.cases_to_sqlite import process_case_triples
from lido.config import URL_LIDO_TTL_GZ, FILE_LIDO_TTL_GZ, FILE_LAWS_NT, FILE_CASES_NT, \
    DIR_DATA_BWB, URL_BWB_IDS_ZIP, FILE_BWB_IDS_ZIP, FILE_SQLITE_DB, \
    TBL_CASES, FILE_CASES_CSV, TBL_LAWS, FILE_LAWS_CSV, TBL_CASE_LAW, FILE_CASE_LAW_CSV, \
    TBL_LAW_ALIAS, FILE_LAW_ALIAS_CSV

default_args = {
    'owner': 'airflow',
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'lido_postgres',
    default_args=default_args,
    description='Update postgresdb with data from lido export on data.overheid.nl',
    schedule_interval='0 0 8 * *', # every month on the 8th at mindnight
    start_date=datetime(2025, 6, 1),
    tags=['caselaw', 'lido'],
) as dag:

    with TaskGroup('prepare_lido') as prepare_lido:
        # reset_lido_data = BashOperator(
        #     task_id='reset_lido_data',
        #     # rm files but keep dirs
        #     bash_command=(f'rm {DIR_DATA_LIDO}/*')
        # )

        # process lido.ttl
        download_lido_ttl = BashOperator(
            task_id='download_lido_ttl',
            bash_command=('curl -sSLf {url} -o {output}').format(
                url=URL_LIDO_TTL_GZ,
                output=FILE_LIDO_TTL_GZ
            )
        )
        # download_lido_ttl = EmptyOperator(task_id="skip_download_lido_ttl")

        check_lido_ttl = BashOperator(
            task_id='check_lido_ttl',
            bash_command=f'test -s {FILE_LIDO_TTL_GZ}'
        )

        # lido.ttl -> cases.nt, laws.nt
        make_laws_nt = task_make_laws_nt(dag)
        # make_laws_nt = EmptyOperator(task_id="skip_make_laws_nt")
        make_cases_nt = task_make_cases_nt(dag)
        # make_cases_nt = EmptyOperator(task_id="skip_make_cases_nt")

        check_laws_nt = BashOperator(
            task_id='check_laws_nt',
            bash_command=f'test -s {FILE_LAWS_NT}'
        )

        check_cases_nt = BashOperator(
            task_id='check_cases_nt',
            bash_command=f'test -s {FILE_CASES_NT}'
        )

        download_lido_ttl >> check_lido_ttl \
            >> make_laws_nt >> check_laws_nt \
            >> make_cases_nt >> check_cases_nt

    with TaskGroup('prepare_bwb') as prepare_bwb:

        reset_bwb_data = BashOperator(
            task_id='reset_bwb_data',
            # rm files but keep dirs
            bash_command=(f'rm -f {DIR_DATA_BWB}/*')
        )

        download_bwbidlist = BashOperator(
            task_id='download_bwbidlist',
            bash_command=('curl -sSLf {url} -o {output}').format(
                url=URL_BWB_IDS_ZIP,
                output=FILE_BWB_IDS_ZIP
            )
        )

        unzip_bwbidlist = PythonOperator(
            task_id='unzip_bwbidlist',
            python_callable=task_unzip_bwbidlist
        )

        bwbidlist_xml_to_json = PythonOperator(
            task_id='bwbidlist_xml_to_json',
            python_callable=task_bwbidlist_xml_to_json
        )

        reset_bwb_data \
            >> download_bwbidlist \
            >> unzip_bwbidlist \
            >> bwbidlist_xml_to_json

    with TaskGroup('to_sqlite') as to_sqlite:

        reset_sqlite_db = BashOperator(
            task_id='reset_sqlite_db',
            # rm files but keep dirs
            bash_command=f'rm {FILE_SQLITE_DB} || true'
        )

        # init sqlite
        init_sqlite_db = PythonOperator(
            task_id="init_sqlite_db",
            python_callable=task_init_sqlite,
        )

        check_sqlite_db = BashOperator(
            task_id='check_sqlite_db',
            bash_command=f'test -s {FILE_SQLITE_DB}'
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

        bwbidlist_to_sqlite = PythonOperator(
            task_id='bwbidlist_to_sqlite',
            python_callable=task_bwbidlist_to_sqlite
        )

        reset_sqlite_db \
            >> init_sqlite_db >> check_sqlite_db \
            >> laws_to_sqlite \
            >> cases_to_sqlite \
            >> bwbidlist_to_sqlite

    with TaskGroup('sqlite_to_csv') as sqlite_to_csv:

        reset_csvs = BashOperator(
            task_id='reset_csvs',
            # rm files but keep dirs
            bash_command=f'rm -f {FILE_CASES_CSV} {FILE_LAWS_CSV} {FILE_CASE_LAW_CSV} {FILE_LAW_ALIAS_CSV}'
        )

        legal_case_to_csv = BashOperator(
            task_id='legal_case_to_csv',
            bash_command=f'sqlite3 {FILE_SQLITE_DB} -header -csv "SELECT * FROM {TBL_CASES};" > {FILE_CASES_CSV}'
        )

        law_element_to_csv = BashOperator(
            task_id='law_element_to_csv',
            bash_command=f'sqlite3 {FILE_SQLITE_DB} -header -csv "SELECT * FROM {TBL_LAWS};" > {FILE_LAWS_CSV}'
        )

        case_law_to_csv = BashOperator(
            task_id='case_law_to_csv',
            bash_command=f'sqlite3 {FILE_SQLITE_DB} -header -csv "SELECT * FROM {TBL_CASE_LAW};" > {FILE_CASE_LAW_CSV}'
        )

        law_alias_to_csv = BashOperator(
            task_id='law_alias_to_csv',
            bash_command=f'sqlite3 {FILE_SQLITE_DB} -header -csv "SELECT * FROM {TBL_LAW_ALIAS};" > {FILE_LAW_ALIAS_CSV}'
        )

        reset_csvs \
            >> legal_case_to_csv \
            >> law_element_to_csv \
            >> case_law_to_csv \
            >> law_alias_to_csv

    with TaskGroup('csv_to_postgres') as csv_to_postgres:

        create_staging_tables = PythonOperator(
            task_id="create_staging_tables",
            python_callable=task_create_staging_tables
        )

        load_cases_csv = PythonOperator(
            task_id="load_cases_csv",
            python_callable=task_load_csv,
            op_args=[FILE_CASES_CSV, TBL_CASES]
        )

        load_laws_csv = PythonOperator(
            task_id="load_laws_csv",
            python_callable=task_load_csv,
            op_args=[FILE_LAWS_CSV, TBL_LAWS]
        )

        load_case_law_csv = PythonOperator(
            task_id="load_case_law_csv",
            python_callable=task_load_csv,
            op_args=[FILE_CASE_LAW_CSV, TBL_CASE_LAW]
        )

        load_law_alias_csv = PythonOperator(
            task_id="load_law_alias_csv",
            python_callable=task_load_csv,
            op_args=[FILE_LAW_ALIAS_CSV, TBL_LAW_ALIAS]
        )

        swap_tables = PythonOperator(
            task_id="swap_tables",
            python_callable=task_swap_tables
        )

        create_staging_tables \
            >> load_cases_csv \
            >> load_laws_csv \
            >> load_case_law_csv \
            >> load_law_alias_csv \
            >> swap_tables


    prepare_bwb >> to_sqlite
    prepare_lido >> to_sqlite

    to_sqlite >> sqlite_to_csv >> csv_to_postgres
