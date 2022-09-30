from datetime import datetime, timedelta
import sys
sys.path.append('data_extraction/caselaw/cellar')
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from os.path import dirname, abspath
sys.path.append (dirname(dirname(abspath(__file__))))
from data_extraction.caselaw.cellar.cellar_extraction import cellar_extract
from data_transformation.data_transformer import transform_data
default_args = {
    'owner': 'airflow',
    #'retries': 5,
    #'retry_delay': timedelta(minutes=1)
}


with DAG(
    dag_id='cellar_extraction',
    default_args = default_args,
    description ='local working need to check aws',
    start_date=datetime(2022,9,24,hour=10,minute=15),
    schedule_interval='10 * * * *'

) as DAG:
    task1 = PythonOperator(
        task_id='cellar_extraction',
        python_callable=cellar_extract,
        op_args=[['local','--amount','50']]
    )
    task2 = PythonOperator(
        task_id='cellar_transformation',
        python_callable=transform_data,
        op_args =[['local']]
    )
    task1 >> task2

