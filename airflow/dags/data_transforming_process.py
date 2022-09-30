from datetime import datetime, timedelta
import sys
from pprint import pprint
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from os.path import dirname, abspath
sys.path.append (dirname(dirname(abspath(__file__))))
from data_transformation.data_transformer import transform_data

default_args = {
    'owner': 'airflow',
    #'retries': 5,
    #'retry_delay': timedelta(minutes=1)
}

with DAG(
    dag_id='cellar_transformation',
    default_args = default_args,
    description ='works well',
    start_date=datetime.now(),
    schedule_interval='55 * * * *'

) as DAG:
    task1 = PythonOperator(
        task_id = 'data_transformation',
        python_callable = transform_data,
        op_args=[['local']]
    )