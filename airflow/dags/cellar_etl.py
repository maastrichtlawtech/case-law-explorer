import logging
import os
import ssl
import time
from calendar import monthrange
from datetime import datetime, timedelta

import urllib3
from airflow.models.variable import Variable
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from dotenv import find_dotenv, load_dotenv

from data_extraction.caselaw.cellar.cellar_extraction import cellar_extract
from data_loading import data_loader
from data_transformation import data_transformer
from definitions.storage_handler import (
    CSV_CELLAR_CASES,
    JSON_FULL_TEXT_CELLAR,
    TXT_CELLAR_EDGES,
    TXT_CELLAR_NODES,
)

from airflow import DAG

# Disable SSL verification globally
# This is necessary for cellar extraction to work with certain SSL configurations
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# Import Cellar extraction function


default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}

dag = DAG(
    dag_id="cellar_etl",
    default_args=default_args,
    description="Cellar ETL with monthly task groups",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule_interval=None,
)


def get_month_end(_date):
    """Extract the last day of the month from datetime.datetime variable using monthrange() method"""
    _date_new = _date.date()
    last_day = monthrange(_date_new.year, _date_new.month)[1]
    return datetime.strptime(str(_date_new.replace(day=last_day)), "%Y-%m-%d")


def _store_dataframe_per_date(df, date, _filename, _path="data/processed/"):
    """Store the dataframe for a specific date in a CSV file."""
    date_str = date.strftime("%Y-%m-%d")
    filename = f"{_filename}"
    if df is None:
        logging.info(f"No data to store for {date_str}")
        return
    filepath = os.path.join(_path, date_str, filename)
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df.to_csv(filepath, index=False)
    logging.info(f"Dataframe for {date_str} stored in {filepath}")


def cellar_etl(**kwargs):
    """Main Cellar ETL function for a specific month"""
    start_date = kwargs["start_date"]
    end_date = kwargs["end_date"]
    _data_path = kwargs["_data_path"]

    logging.info(f"Starting Cellar ETL for {start_date} to {end_date}")
    start_time = time.time()

    # Disable SSL verification for this ETL run
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    os.environ["CURL_CA_BUNDLE"] = ""

    # Setup environment
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)

    _raw_data_path = os.path.join(_data_path, "raw")

    # Check if data already exists for this date range
    date_str = start_date.strftime("%Y-%m-%d")
    output_path = os.path.join(_raw_data_path, date_str, CSV_CELLAR_CASES)

    if os.path.exists(output_path):
        logging.info(f"Cellar data already exists for {date_str}")
        logging.info("Moving to data transformation")
    else:
        logging.info("No previous data found for this date range")
        logging.info("--- EXTRACTION ---")

        # Create date-specific directory
        os.makedirs(os.path.join(_raw_data_path, date_str), exist_ok=True)

        # Prepare arguments for Cellar extraction
        extraction_args = [
            "--starting-date",
            start_date.strftime("%Y-%m-%d"),
            "--amount",
            str(eval(Variable.get("CELLAR_AMOUNT_TO_EXTRACT", default_var="1000"))),
            "--ending-date",
            end_date.strftime("%Y-%m-%d"),
        ]

        # Run Cellar extraction
        try:
            cellar_extract(extraction_args)
            logging.info("Cellar extraction completed")
        except Exception as e:
            logging.error(f"Cellar extraction failed: {e}")
            raise

        end_time = time.time()
        logging.info(
            f"Time taken for Cellar extraction: {time.strftime('%H:%M:%S', time.gmtime(end_time - start_time))}"
        )

    # Perform data transformation
    logging.info("Starting data transformation")
    input_paths = [output_path]
    data_transformer.transform_data(caselaw_type="CELLAR", input_paths=input_paths)

    # Perform data loading
    logging.info("Starting data loading")
    data_loader.load_data()

    # Clean up files
    logging.info("Cleaning up files")
    cleanup_files = [
        os.path.join(_raw_data_path, date_str, CSV_CELLAR_CASES),
        os.path.join(_raw_data_path, date_str, JSON_FULL_TEXT_CELLAR),
        os.path.join(_raw_data_path, date_str, TXT_CELLAR_EDGES),
        os.path.join(_raw_data_path, date_str, TXT_CELLAR_NODES),
    ]

    for file_path in cleanup_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Removed {file_path}")
            except Exception as e:
                logging.warning(f"Could not remove {file_path}: {e}")

    logging.info("Cellar ETL completed successfully")


def create_tasks():
    """Create monthly task groups for Cellar ETL"""
    start_date = eval(Variable.get("CELLAR_START_DATE"))
    end_date = eval(Variable.get("CELLAR_END_DATE"))

    if not start_date or not end_date:
        raise ValueError("CELLAR_START_DATE and CELLAR_END_DATE are required in Airflow variables.")

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    logging.info("Creating tasks for Cellar ETL")
    logging.info(f"Extracting for period: {start_date} to {end_date}")

    with TaskGroup("cellar_etl_tasks", tooltip="Cellar ETL tasks", dag=dag) as task_group:
        current_date = start_date
        while current_date <= end_date:
            month_end = get_month_end(current_date)
            if month_end > end_date:
                month_end = end_date

            logging.info(f"Creating task for {current_date} to {month_end}")

            PythonOperator(
                task_id=f"cellar_etl_{current_date.strftime('%Y-%m')}",
                python_callable=cellar_etl,
                op_kwargs={
                    "start_date": current_date,
                    "end_date": month_end,
                    "_data_path": Variable.get("DATA_PATH"),
                },
                dag=dag,
            )

            current_date = month_end + timedelta(days=1)

    return task_group


with dag:
    create_tasks()
