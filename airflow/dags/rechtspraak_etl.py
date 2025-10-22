import argparse
import logging
import os
import sys
import time
import pandas as pd
import rechtspraak_extractor.rechtspraak as rex

from airflow import DAG
from airflow.models.variable import Variable
from airflow.operators.python import PythonOperator

# from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.task_group import TaskGroup
from calendar import monthrange
from csv import DictReader, DictWriter
from data_transformation.utils import *
from data_transformation import data_transformer
from data_loading import data_loader
from datetime import datetime, timedelta
from definitions.storage_handler import Storage, get_path_raw, CSV_RS_CASES
from definitions.mappings.attribute_name_maps import MAP_RS
from os.path import dirname, abspath
from rechtspraak_extractor.rechtspraak_metadata import get_rechtspraak_metadata
from rechtspraak_citations_extractor.citations_extractor import get_citations
from dotenv import load_dotenv, find_dotenv


default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}

dag = DAG(
    dag_id="rechtspraak_etl",
    default_args=default_args,
    description="Single file for everything",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule_interval=None,
)


def get_month_end(_date):
    # Extract the last day of the month from datetime.datetime variable
    # using monthrange() method
    _date_new = _date.date()
    last_day = monthrange(_date_new.year, _date_new.month)[1]
    # Convert to datetime and return
    return datetime.strptime(str(_date_new.replace(day=last_day)), "%Y-%m-%d")


def _store_dataframe_per_date(df, date, _filename, _path="data/processed/"):
    """
    Store the dataframe for a specific date in a CSV file.
    The filename is based on the date.
    """
    date_str = date.strftime("%Y-%m-%d")
    filename = f"{_filename}"
    if df is None:
        logging.info(f"No data to store for {date_str}")
        return
    # Store in directory data/processed/date_str
    filepath = os.path.join(_path, date_str, filename)
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # Store the dataframe in the CSV file
    df.to_csv(filepath, index=False)
    logging.info(f"Dataframe for {date_str} stored in {filepath}")


def _get_citations(_dataframe, LIDO_USERNAME, LIDO_PASSWORD, _threads, _filepath=None):
    """
    Get the citations from the dataframe.
    """
    logging.info("Getting citations from metadata_extraction")
    # Get citations from the metadata_extraction dataframe
    final_df = get_citations(_dataframe, LIDO_USERNAME, LIDO_PASSWORD, _threads)
    logging.info(f"Length of final_df: {len(final_df)}")
    final_df.to_csv(_filepath, index=False)
    return


def _metadata_extraction(base_extraction, _fake_headers=True, data_dir="data/raw/"):
    metadata_df = get_rechtspraak_metadata(
        save_file="n",
        dataframe=base_extraction,
        _fake_headers=_fake_headers,
        data_dir=data_dir,
    )
    return metadata_df


def rechtspraak_etl(**kwargs):
    start_date = kwargs["start_date"]
    end_date = kwargs["end_date"]
    _data_path = kwargs["_data_path"]
    logging.info(f"Starting Rechtspraak ETL for {start_date} to {end_date}")
    start_time = time.time()
    logging.info("Checking if data already exists for this date range")
    # Check if data (base_extraction or metadata_extraction) already exists
    # for in the dir of start_date
    _filename_base = "base_extraction_rechtspraak.csv"
    _filename_metadata = "metadata_extraction_rechtspraak.csv"
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)
    LIDO_USERNAME = os.getenv("LIDO_USERNAME")
    LIDO_PASSWORD = os.getenv("LIDO_PASSWORD")
    _processed_data_path = os.path.join(_data_path, "processed")
    _raw_data_path = os.path.join(_data_path, "raw")
    if os.path.exists(
        os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d"), CSV_RS_CASES)
    ):
        logging.info(
            "Citation extraction already exists for this date range"
            "from previous run or leftover"
        )
        # Read data from the CSV file to a dataframe
        citation_extraction = pd.read_csv(
            os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d"), CSV_RS_CASES)
        )
        logging.info(f"Length of citation_extraction: {len(citation_extraction)}")
        logging.info("Moving to data transformation")
    elif os.path.exists(
        os.path.join(
            _raw_data_path, start_date.strftime("%Y-%m-%d"), _filename_metadata
        )
    ):
        logging.info(
            "Metadata extraction already exists for this date range"
            "from previous run or leftover"
        )
        logging.info("Starting citation extraction")
        # Read data from the CSV file to a dataframe
        metadata_extraction = pd.read_csv(
            os.path.join(
                _raw_data_path, start_date.strftime("%Y-%m-%d"), _filename_metadata
            )
        )
        logging.info(f"Length of metadata_extraction: {len(metadata_extraction)}")
        # Store the final dataframe in the CSV file
        df_filepath = os.path.join(
            _raw_data_path, start_date.strftime("%Y-%m-%d"), CSV_RS_CASES
        )
        # Get citations from the metadata_extraction dataframe
        _get_citations(
            metadata_extraction, LIDO_USERNAME, LIDO_PASSWORD, 1, df_filepath
        )
        logging.info("Citation extraction done, updating local storage")
        end_time = time.time()
        logging.info(
            "Time taken for rechtspraak extraction: "
            + time.strftime("%H:%M:%S", time.gmtime(end_time - start_time))
        )
    elif os.path.exists(
        os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d"), _filename_base)
    ) and not (
        os.path.exists(
            os.path.join(
                _raw_data_path, start_date.strftime("%Y-%m-%d"), _filename_metadata
            )
        )
    ):
        logging.info("Base extraction already exists for this date range")
        logging.info("Starting metadata extraction")
        # Read data from the CSV file to a dataframe
        base_extraction = pd.read_csv(
            os.path.join(
                _raw_data_path, start_date.strftime("%Y-%m-%d"), _filename_base
            )
        )
        metadata_df = _metadata_extraction(
            base_extraction,
            _fake_headers=True,
            data_dir=os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d")),
        )
        # Store the metadata dataframe in the CSV file
        _store_dataframe_per_date(
            metadata_df, start_date, _filename_metadata, _raw_data_path
        )
        logging.info("Metadata extraction done")
        logging.info("Starting citation extraction")
        df_filepath = os.path.join(
            _raw_data_path, start_date.strftime("%Y-%m-%d"), _filename_metadata
        )
        # Get citations from the metadata_extraction dataframe
        _get_citations(metadata_df, LIDO_USERNAME, LIDO_PASSWORD, 1, df_filepath)
        logging.info("Citation extraction done, updating local storage")
        end_time = time.time()
        logging.info(
            "Time taken for rechtspraak extraction: "
            + time.strftime("%H:%M:%S", time.gmtime(end_time - start_time))
        )
    else:
        logging.info("No previous data found for this date range")
        logging.info("--- EXTRACTION ---")
        base_extraction = rex.get_rechtspraak(
            max_ecli=Variable.get('RS_AMOUNT_TO_EXTRACT'),
            sd=start_date.strftime("%Y-%m-%d"),
            ed=end_date.strftime("%Y-%m-%d"),
            save_file="n",
        )
        # Store the base extraction dataframe in the CSV file
        _store_dataframe_per_date(
            base_extraction, start_date, _filename_base, _raw_data_path
        )
        logging.info("Base extraction done")
        logging.info("Starting metadata extraction")
        metadata_df = _metadata_extraction(
            base_extraction,
            _fake_headers=True,
            data_dir=os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d")),
        )
        # Store the metadata dataframe in the CSV file
        _store_dataframe_per_date(
            metadata_df, start_date, _filename_metadata, _raw_data_path
        )
        logging.info("Metadata extraction done")
        logging.info("Starting citation extraction")
        df_filepath = os.path.join(
            _raw_data_path, start_date.strftime("%Y-%m-%d"), CSV_RS_CASES
        )
        # Get citations from the metadata_extraction dataframe
        _get_citations(metadata_df, LIDO_USERNAME, LIDO_PASSWORD, 1, df_filepath)
        logging.info("Citation extraction done, updating local storage")
        end_time = time.time()
        logging.info(
            "Time taken for rechtspraak extraction: "
            + time.strftime("%H:%M:%S", time.gmtime(end_time - start_time))
        )
    # We check if there are any _failed_eclis.txt file in data/processed/
    # If they exist, we perform metadata_extraction in the follwing order -
    # 1. Read the data from the file to get the ECLIS.
    # 2. Merge the ECLIs with base_data file to obtain other information.
    # 3. Perform metadata extraction which likely will yield more _faile_eclis
    # 4. Perform citation extraction on available data
    # 5. Repeat the loop until there are no more on the _failed_eclis.txt file
    # We don't want to be stuck in an infinite loop, so we keep a counter and
    # stop after 5 iterations
    counter = 0
    failed_ecli_filename = "custom_rechtspraak_" + start_date.strftime("%Y-%m-%d") + "_failed_eclis.txt"
    while (os.path.exists(os.path.join("data", failed_ecli_filename))) and counter < 5:
        logging.info(f"Failed ECLIs file found, counter is {counter}")
        # Read data from the _failed_eclis.txt file which
        # contains one ECLI per line
        failed_ecli_df = pd.read_csv(
            os.path.join(
                "data", failed_ecli_filename
            ),
            header=None,
        )
        failed_ecli_df.columns = ["ECLI"]
        # Read base_dataframe from the CSV file to a dataframe
        base_extraction = pd.read_csv(
            os.path.join(
                _raw_data_path, start_date.strftime("%Y-%m-%d", _filename_base)
            )
        )
        # Merge the base_extraction dataframe with the
        # failed_ecli_df dataframe with ECLI as key
        try:
            failed_ecli_df = pd.merge(
                failed_ecli_df, base_extraction, how="inner", on="ECLI"
            )
            logging.info("Failed ECLIs merged with base_extraction")
        except Exception as e:
            logging.info(f"Error merging failed ECLIs with base_extraction: {e}")
            logging.info(
                "Failed ECLIs not merged with base_extraction, and\
                          will not be processed"
            )
            break
        # Remove the _failed_eclis.txt file
        try:
            os.remove(
                os.path.join(
                   "data", failed_ecli_filename
                )
            )
            logging.info("Failed ECLIs file removed")
            logging.info("Starting metadata extraction")
        except Exception as e:
            logging.info(f"Error removing failed ECLIs file: {e}")
            logging.info(
                "Failed ECLIs file not removed, and will not be\
                         processed"
            )
            break
        logging.info("Starting metadata extraction")
        # Perform metadata_extraction on the failed_ecli_df dataframe
        metadata_df = _metadata_extraction(
            failed_ecli_df,
            _fake_headers=True,
            data_dir=os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d")),
        )
        if metadata_df is None:
            logging.info("No metadata found for failed ECLIs")
            break
        # Store the metadata dataframe in the CSV file
        _store_dataframe_per_date(
            metadata_df, start_date, _filename_metadata, _raw_data_path
        )
        logging.info("Metadata extraction done")
        logging.info("Starting citation extraction")
        df_filepath = os.path.join(
            _raw_data_path, start_date.strftime("%Y-%m-%d"), CSV_RS_CASES
        )
        # Get citations from the metadata_extraction dataframe
        _get_citations(metadata_df, LIDO_USERNAME, LIDO_PASSWORD, 1, df_filepath)
        logging.info("Citation extraction done, updating local storage")
        counter += 1

    # Perform data transformation
    logging.info("Starting data transformation")
    input_paths = [
        os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d"), CSV_RS_CASES),
    ]
    data_transformer.transform_data(caselaw_type="RS", input_paths=input_paths)
    # Perform data loading
    data_loader.load_data()
    # Clean up the files
    logging.info("Cleaning up the files")
    # Remove the base extraction file
    if os.path.exists(
        os.path.join(
            "airflow", _raw_data_path, start_date.strftime("%Y-%m-%d"), _filename_base
        )
    ):
        logging.info("Removing base extraction file")
        os.remove(
            os.path.join(
                "airflow",
                _raw_data_path,
                start_date.strftime("%Y-%m-%d"),
                _filename_base,
            )
        )
    # Remove the metadata extraction file
    if os.path.exists(
        os.path.join(
            "airflow",
            _processed_data_path,
            start_date.strftime("%Y-%m-%d"),
            _filename_metadata,
        )
    ):
        logging.info("Removing metadata extraction file")
        os.remove(
            os.path.join(
                "airflow",
                _processed_data_path,
                start_date.strftime("%Y-%m-%d"),
                _filename_metadata,
            )
        )
    if os.path.exists(
        os.path.join(
            "airflow",
            _processed_data_path,
            start_date.strftime("%Y-%m-%d"),
            CSV_RS_CASES,
        )
    ):
        logging.info("Removing citation extraction file")
        os.remove(
            os.path.join(
                "airflow",
                _processed_data_path,
                start_date.strftime("%Y-%m-%d"),
                CSV_RS_CASES,
            )
        )
    logging.info("Files cleaned up")


def create_tasks():
    start_date = Variable.get("RS_START_DATE")
    end_date = Variable.get("RS_END_DATE")
    if not start_date or not end_date:
        raise ValueError("start_date and end_date are required in the DAG run conf.")
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    # Identify the number of months between start_date and end_date
    # and create a task for each month
    logging.info("Creating tasks for Rechtspraak ETL")
    months = pd.date_range(start_date, end_date, freq="M")
    logging.info(f"Extractin for {months} months")
    with TaskGroup(
        "rechtspraak_etl_tasks", tooltip="Rechtspraak ETL tasks", dag=dag
    ) as task_group:
        while start_date <= end_date:
            month_end = get_month_end(start_date)
            if month_end > end_date:
                month_end = end_date
            logging.info(f"Creating task for {start_date} to {month_end}")
            PythonOperator(
                task_id=f"rechtspraak_etl_{start_date.strftime('%Y-%m')}",
                python_callable=rechtspraak_etl,
                op_kwargs={
                    "start_date": start_date,
                    "end_date": month_end,
                    "_data_path": Variable.get("DATA_PATH"),
                },
                dag=dag,
            )
            start_date = month_end + timedelta(days=1)
    return task_group


with dag:
    create_tasks()
    # initializer = PythonOperator(
    #     task_id="initializer",
    #     python_callable=create_tasks,
    #     provide_context=True,
    # )
    # initializer
