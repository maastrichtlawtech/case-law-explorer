import rechtspraak_extractor as rex
from os.path import dirname, abspath
import sys
import time
from datetime import datetime
from definitions.storage_handler import Storage, get_path_raw, CSV_RS_CASES
import argparse
from dotenv import load_dotenv, find_dotenv
from airflow.models.variable import Variable
import rechtspraak_citations_extractor as rex_citations
import os

env_file = find_dotenv()
load_dotenv(env_file, override=True)
LIDO_USERNAME = os.getenv('LIDO_USERNAME')
LIDO_PASSWORD = os.getenv('LIDO_PASSWORD')
RS_SETUP = eval(os.getenv('RS_SETUP'))
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))


def get_rs_setup_args():
    amount = 1200000
    var_list = ['1995-01-01', '1996-01-01', '1997-01-01', '1998-01-01', '1999-01-01', '2000-01-01', '2001-01-01',
                '2002-01-01',
                '2003-01-01', '2004-01-01', '2005-01-01', '2006-01-01', '2007-01-01', '2008-01-01', '2009-01-01',
                '2010-01-01',
                '2011-01-01', '2012-01-01', '2013-01-01', '2014-01-01', '2015-01-01', '2016-01-01', '2017-01-01',
                '2018-01-01',
                '2019-01-01', '2020-01-01', '2021-01-01', '2022-01-01', '2023-01-01']
    try:
        index = eval(Variable.get('RS_SETUP_INDEX'))  # start index
        next_index = index + 1  # end index
        if index >= len(var_list):  # if start is out, no extraction out
            starting = None
            ending = None
        else:  # starting is in
            starting = var_list[index]
            if next_index >= len(var_list):  # determine if end is there or no
                ending = None
            else:
                ending = var_list[next_index]
    except:
        print("NO INDEX YET SET")
        next_index = 0
        ending = var_list[0]
        starting = None

    return starting, ending, amount, next_index


def get_parser_args(args):
    start = args.starting_date
    end = args.ending_date
    amount = args.amount
    return start, end, amount


def rechtspraak_extract(args=None):
    output_path = get_path_raw(CSV_RS_CASES)
    parser = argparse.ArgumentParser()
    parser.add_argument('--amount', help='number of documents to retrieve', type=int, required=False)
    parser.add_argument('--starting_date', help='Last modification date to look forward from', required=False)
    parser.add_argument('--ending_date', help='Last modification date ', required=False)
    args = parser.parse_args(args)

    if RS_SETUP:
        print('RS DATABASE SETUP RUN')
        start, end, amount, next_index = get_rs_setup_args()
    else:
        start, end, amount = get_parser_args(args)

    print('\n--- PREPARATION ---\n')
    print('OUTPUT:\t\t\t', output_path)
    storage = Storage()

    try:
        storage.setup_pipeline(output_paths=[output_path])
    except Exception as e:
        print(e)
        return

    try:
        last_updated = Variable.get('RSPRAAK_LAST_DATE')
    except Exception as e:
        print(e)
        last_updated = '1900-01-01'
        Variable.set(key='RSPRAAK_LAST_DATE', value=last_updated)

    today_date = str(datetime.today().date())
    print('\nSTART DATE (LAST UPDATE):\t', last_updated)
    print('\n--- START ---\n')
    start_time = time.time()
    print(f"Downloading {amount if amount else 'all'} Rechtspraak documents")

    if not amount:
        amount = 1200000


    if start and end:
        print(f'Starting from manually specified dates: {start} - {end}')
        df = rex.get_rechtspraak(max_ecli=amount, sd=start, save_file='n', ed=end)
        df_2 = rex.get_rechtspraak_metadata(save_file='n', dataframe=df)
    elif end:
        print(f'Ending at manually specified date: {end}')
        df = rex.get_rechtspraak(max_ecli=amount, ed=end, save_file='n')
        df_2 = rex.get_rechtspraak_metadata(save_file='n', dataframe=df)
    elif start:
        print(f'Starting from manually specified date: {start} ')
        df = rex.get_rechtspraak(max_ecli=amount, sd=start, save_file='n')
        df_2 = rex.get_rechtspraak_metadata(save_file='n', dataframe=df)
    else:
        print('Starting from the last update the script can find')
        df = rex.get_rechtspraak(max_ecli=amount, sd=last_updated, save_file='n', ed=today_date)
        df_2 = rex.get_rechtspraak_metadata(save_file='n', dataframe=df)
    print(f"Length of df_2 is {len(df_2)}")
    rex_citations.get_citations(df_2, LIDO_USERNAME, LIDO_PASSWORD, 2)

    print(f"\nUpdating local storage ...")
    df_filepath = get_path_raw(CSV_RS_CASES)

    df_2.to_csv(df_filepath, index=False)

    end_time = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end_time - start_time)))
    Variable.set(key='RSPRAAK_LAST_DATE', value=today_date)
    if RS_SETUP:
        Variable.set(key='RS_SETUP_INDEX',value=next_index)


if __name__ == '__main__':
    # giving arguments to the function
    rechtspraak_extract()
