from datetime import datetime, timedelta
import sys
sys.path.append('data_extraction/caselaw/cellar')
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from os.path import dirname, abspath
sys.path.append (dirname(dirname(abspath(__file__))))
from data_extraction.caselaw.cellar.cellar_extraction import cellar_extract
default_args = {
    'owner': 'airflow',
    #'retries': 5,
    #'retry_delay': timedelta(minutes=1)
}
import pendulum
# def extraction():
#     cellar_extract(['local','--amount','50'])
# def test(args):
#     import argparse
#     parser = argparse.ArgumentParser(description='Description of your program')
#     parser.add_argument('-f','--foo', help='Description for foo argument', required=True)
#     parser.add_argument('-b','--bar', help='Description for bar argument', required=True)
#     args = vars(parser.parse_args(args))
#     if args['foo'] == 'Hello':
#         # code here
#         print('hello')

#     if args['bar'] == 'World':
#         # code here
#         print('world')

# if __name__ =='__main__':
#     test(args)


with DAG(
    dag_id='cellar_extraction',
    default_args = default_args,
    description =' Still in process',
    start_date=datetime(2022,9,24,hour=10,minute=15),
    schedule_interval='10 * * * *'

) as DAG:
    task1 = PythonOperator(
        task_id='cellar_extraction',
        python_callable=cellar_extract,
        op_args=[['local']]
    )

