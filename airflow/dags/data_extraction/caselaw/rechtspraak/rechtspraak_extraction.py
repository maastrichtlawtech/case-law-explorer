"""
Main RS extraction routine. Used by the rechtspaark_extraction DAG.
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
from os.path import dirname, abspath
from rechtspraak_citations_extractor.citations_extractor import get_citations
import rechtspraak_extractor.rechtspraak as rex
from rechtspraak_extractor.rechtspraak_metadata import get_rechtspraak_metadata
from airflow.models.variable import Variable
from dotenv import load_dotenv, find_dotenv

from definitions.storage_handler import Storage, get_path_raw, CSV_RS_CASES

env_file = find_dotenv()
load_dotenv(env_file, override=True)
LIDO_USERNAME = os.getenv('LIDO_USERNAME')
LIDO_PASSWORD = os.getenv('LIDO_PASSWORD')

try:
    RS_SETUP = eval(Variable.get('RS_SETUP'))
except:
    RS_SETUP = True
    Variable.set(key='RS_SETUP', value=True)

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))


def get_rs_setup_args():
    """
    RS database setup routine - for building entire DB from scratch.
    There are millions of cases, more than possible to extract at once.
    This method returns the start&end dates for extraction, as well as the amount - arguments for RS extractions.
    Index referenced in code is the index of last visited point in the var_list.
    Indexes stored via airflow DB. Proper usage will setup the entire database, with small increments, year by year.
    Only works when RS_SETUP in .env file is set to True.
    In case of rerunning the DB setup, don't forget to reset the airflow database.
    """
    amount = 1200000
    var_list = ['1995-01-01', '1996-01-01', '1997-01-01', '1998-01-01', '1999-01-01', '2000-01-01', '2001-01-01',
                '2002-01-01',
                '2003-01-01', '2004-01-01', '2005-01-01', '2006-01-01', '2007-01-01', '2008-01-01', '2009-01-01',
                '2010-01-01',
                '2011-01-01', '2012-01-01', '2013-01-01', '2014-01-01', '2015-01-01', '2016-01-01', '2017-01-01',
                '2018-01-01',~
                '2019-01-01', '2020-01-01', '2021-01-01', '2022-01-01', '2023-01-01']  # 29
    try:
        index = eval(Variable.get('RS_SETUP_INDEX'))  # start index
        next_index = index + 1  # end index
        if index >= len(var_list):  # if start is out, no extraction out
            starting = None
            ending = None
            Variable.set(key='RS_SETUP', value=False)
        else:  # starting is in
            starting = var_list[index]
            if next_index >= len(var_list):  # determine if end is there or no
                ending = None
            else:
                ending = var_list[next_index]
    except:
        logging.info("NO INDEX YET SET")
        next_index = 0
        ending = var_list[0]
        starting = None

    return starting, ending, amount, next_index


def _store_dataframe_per_date(df, date, _filename, _path='data/processed/'):
    """
    Store the dataframe for a specific date in a CSV file.
    The filename is based on the date.
    """
    date_str = date.strftime('%Y-%m-%d')
    filename = f"rechtspraak_{_filename}_{date_str}.csv"
    # Store in directory data/processed/date_str
    filepath = os.path.join(_path, date_str, filename)
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # Store the dataframe in the CSV file
    if df is None:
        logging.info(f"No data to store for {date_str}")
        return
    df.to_csv(filepath, index=False)
    logging.info(f"Dataframe for {date_str} stored in {filepath}")


def get_parser_args(args):
    # Gets arguments for extractions from args parser.
    start = args.starting_date
    end = args.ending_date
    amount = args.amount
    return start, end, amount


def rechtspraak_extract(args=None):
    logging.info('--- RECHTSPRAAK EXTRACTION ---')
    output_path = get_path_raw(CSV_RS_CASES)
    parser = argparse.ArgumentParser()
    parser.add_argument('--amount', help='number of documents to retrieve', type=int, required=False)
    parser.add_argument('--starting_date', help='Last modification date to look forward from', required=False)
    parser.add_argument('--ending_date', help='Last modification date ', required=False)
    args, unknown = parser.parse_known_args(args)

    if RS_SETUP:
        logging.info('RS DATABASE SETUP RUN')
        start, end, amount, next_index = get_rs_setup_args()
        start = eval(Variable.get('RS_START_DATE'))
        end = eval(Variable.get('RS_END_DATE'))
    else:
        start, end, amount = get_parser_args(args)

    logging.info('--- PREPARATION ---')
    logging.info('OUTPUT:\t\t\t' + output_path)
    storage = Storage()
    # Setting up storage. In case output exists - throws an Exception.
    # To make sure it doesnt crash airflow dags, needs to be caught.
    # This way the pipeline goes to the next steps of transformation and extraction, hopefully
    # eventually dealing with the already-existing output file
    try:
        storage.setup_pipeline(output_paths=[output_path])
    except Exception as e:
        logging.error(e)
        return

    try:
        # Getting date of last update from airflow database
        last_updated = Variable.get('RSPRAAK_LAST_DATE')
    except Exception as e:
        last_updated = os.getenv('RS_START_DATE')
        Variable.set(key='RSPRAAK_LAST_DATE', value=last_updated)

    today_date = str(datetime.today().date())
    logging.info('START DATE (LAST UPDATE):\t' + last_updated)
    logging.info('--- START ---')
    start_time = time.time()
    logging.info(f"Downloading {amount if amount else 'all'} Rechtspraak documents")

    if not amount:
        amount = 12


    if start and end:
        logging.info(f'Starting from manually specified dates: {start} - {end}')
        current_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        metadata_df_list = []
        # Check if there are files from previous runs per date

        while current_date < end_date:
            next_date = current_date + timedelta(days=1)
            logging.info(f'Processing date range: {current_date.date()} - {next_date.date()}')
            base_extraction = rex.get_rechtspraak(max_ecli=amount,
                                                  sd=str(current_date.date()),
                                                  ed=str(next_date.date()),
                                                  save_file='n')
            # Store the dataframe for the current date
            _store_dataframe_per_date(base_extraction,
                                      current_date,
                                      _filename='base',
                                      _path='data/processed/')
            metadata_df = get_rechtspraak_metadata(save_file='n',
                                                   dataframe=base_extraction,
                                                   _fake_headers=True,
                                                   data_dir='data/processed/')
            metadata_df_list.append(metadata_df)
            # Store the dataframe for the current date
            _store_dataframe_per_date(metadata_df,
                                      current_date,
                                      _filename='metadata',
                                      _path='data/processed/')
            current_date = next_date
        if metadata_df_list:
            metadata_df = pd.concat(metadata_df_list, ignore_index=True)
        else:
            logging.info("No new data to process")
            
    elif end:
        logging.info(f'Ending at manually specified date: {end}')
        current_date = datetime.strptime(last_updated, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        metadata_df_list = []

        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            logging.info(f'Processing date range: {current_date.date()} - {next_date.date()}')
            base_extraction = rex.get_rechtspraak(max_ecli=amount,
                                                  sd=str(current_date.date()),
                                                  ed=str(next_date.date()),
                                                  save_file='n')
            _store_dataframe_per_date(base_extraction,
                                      current_date,
                                      _filename='base',
                                      _path='data/processed/')
            metadata_df = get_rechtspraak_metadata(save_file='n',
                                                   dataframe=base_extraction,
                                                   _fake_headers=True,
                                                   data_dir='data/processed/')
            _store_dataframe_per_date(metadata_df,
                                      current_date,
                                      _filename='metadata',
                                      _path='data/processed/')
            metadata_df_list.append(metadata_df)
            current_date = next_date
        if metadata_df_list:
            metadata_df = pd.concat(metadata_df_list, ignore_index=True)
        
    elif start:
        logging.info(f'Starting from manually specified date: {start}')
        current_date = datetime.strptime(start, '%Y-%m-%d')
        today_date = datetime.today()
        metadata_df_list = []

        while current_date <= today_date:
            next_date = current_date + timedelta(days=1)
            logging.info(f'Processing date range: {current_date.date()} - {next_date.date()}')
            base_extraction = rex.get_rechtspraak(max_ecli=amount,
                                                  sd=str(current_date.date()),
                                                  ed=str(next_date.date()),
                                                  save_file='n')
            _store_dataframe_per_date(base_extraction,
                                      current_date,
                                      _filename='base',
                                      _path='data/processed/')
            metadata_df = get_rechtspraak_metadata(save_file='n',
                                                   dataframe=base_extraction,
                                                   _fake_headers=True,
                                                   data_dir='data/processed/')
            _store_dataframe_per_date(metadata_df,
                                      current_date,
                                      _filename='metadata',
                                      _path='data/processed/')
            metadata_df_list.append(metadata_df)
            current_date = next_date
        if metadata_df_list:
            metadata_df = pd.concat(metadata_df_list, ignore_index=True)
        else:
            logging.info("No new data to process")

    else:
        logging.info('Starting from the last update the script can find')
        current_date = datetime.strptime(last_updated, '%Y-%m-%d')
        today_date = datetime.today()
        metadata_df_list = []

        while current_date <= today_date:
            next_date = current_date + timedelta(days=1)
            logging.info(f'Processing date range: {current_date.date()} - {next_date.date()}')
            base_extraction = rex.get_rechtspraak(max_ecli=amount,
                                                  sd=str(current_date.date()),
                                                  ed=str(next_date.date()),
                                                  save_file='n')
            _store_dataframe_per_date(base_extraction,
                                      current_date,
                                      _filename='base',
                                      _path='data/processed/')
            metadata_df = get_rechtspraak_metadata(save_file='n',
                                                   dataframe=base_extraction,
                                                   _fake_headers=True,
                                                   data_dir='data/processed/')
            _store_dataframe_per_date(metadata_df,
                                      current_date,
                                      _filename='metadata',
                                      _path='data/processed/')
            if isinstance(metadata_df, pd.DataFrame):
                metadata_df_list.append(metadata_df)
            current_date = next_date
        if metadata_df_list:
            metadata_df = pd.concat(metadata_df_list, ignore_index=True)
        else:
            logging.info("No new data to process")
            
    logging.info(f"Length of metadata df is {len(metadata_df)}")
    get_citations(metadata_df, LIDO_USERNAME, LIDO_PASSWORD, 1)

    logging.info(f"Updating local storage ...")
    df_filepath = get_path_raw(CSV_RS_CASES)

    metadata_df.to_csv(df_filepath, index=False)

    end_time = time.time()
    logging.info("--- DONE ---")
    logging.info("Time taken: " + time.strftime('%H:%M:%S', time.gmtime(end_time - start_time)))
    Variable.set(key='RSPRAAK_LAST_DATE', value=today_date)
    if RS_SETUP:
        Variable.set(key='RS_SETUP_INDEX', value=next_index)
    
    # Check if there are any _failed_eclis.txt file in data and its subdirectories
    failed_files = []
    for root, dirs, files in os.walk('data'):
        for file in files:
            if file.endswith('_failed_eclis.txt'):
                failed_files.append(os.path.join(root, file))
    if failed_files:
        logging.info("There are some failed eclis files in the data directory:")
        for file in failed_files:
            logging.info(file)
    else:
        logging.info("There are no failed eclis files in the data directory.")


if __name__ == '__main__':
    # giving arguments to the function
    rechtspraak_extract()
