import logging
import os
import time
from calendar import monthrange
from datetime import datetime, timedelta

from airflow.models.variable import Variable
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

# Import ECHR extraction function
from data_extraction.caselaw.echr.echr_extraction import echr_extract
from data_loading import data_loader
from data_transformation import data_transformer
from definitions.storage_handler import (
    CSV_ECHR_CASES,
    JSON_FULL_TEXT_ECHR,
    TXT_ECHR_EDGES,
    TXT_ECHR_NODES,
)
from dotenv import find_dotenv, load_dotenv

from airflow import DAG

default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}

dag = DAG(
    dag_id="echr_etl",
    default_args=default_args,
    description="ECHR ETL with monthly task groups",
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


def echr_etl(**kwargs):
    """Main ECHR ETL function for a specific month"""
    start_date = kwargs["start_date"]
    end_date = kwargs["end_date"]
    _data_path = kwargs["_data_path"]

    logging.info(f"Starting ECHR ETL for {start_date} to {end_date}")
    start_time = time.time()

    # Setup environment
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)

    _raw_data_path = os.path.join(_data_path, "raw")

    # Check if data already exists for this date range
    date_str = start_date.strftime("%Y-%m-%d")
    output_path = os.path.join(_raw_data_path, date_str, CSV_ECHR_CASES)

    if os.path.exists(output_path):
        logging.info(f"ECHR data already exists for {date_str}")
        logging.info("Moving to data transformation")
    else:
        logging.info("No previous data found for this date range")
        logging.info("--- EXTRACTION ---")

        # Create date-specific directory
        os.makedirs(os.path.join(_raw_data_path, date_str), exist_ok=True)

        # Prepare arguments for ECHR extraction
        extraction_args = [
            "--start-date",
            start_date.strftime("%Y-%m-%d"),
            "--end-date",
            end_date.strftime("%Y-%m-%d"),
            "--count",
            str(eval(Variable.get("ECHR_AMOUNT_TO_EXTRACT", default_var="1000"))),
        ]

        # Run ECHR extraction
        try:
            echr_extract(extraction_args)
            logging.info("ECHR extraction completed")
        except Exception as e:
            logging.error(f"ECHR extraction failed: {e}")
            raise

        end_time = time.time()
        logging.info(
            f"Time taken for ECHR extraction: {time.strftime('%H:%M:%S', time.gmtime(end_time - start_time))}"
        )

    # Perform data transformation
    logging.info("Starting data transformation")
    input_paths = [output_path]
    data_transformer.transform_data(caselaw_type="ECHR", input_paths=input_paths)

    # Perform data loading
    logging.info("Starting data loading")
    data_loader.load_data()

    # Clean up files
    logging.info("Cleaning up files")
    cleanup_files = [
        os.path.join(_raw_data_path, date_str, CSV_ECHR_CASES),
        os.path.join(_raw_data_path, date_str, JSON_FULL_TEXT_ECHR),
        os.path.join(_raw_data_path, date_str, TXT_ECHR_EDGES),
        os.path.join(_raw_data_path, date_str, TXT_ECHR_NODES),
    ]

    for file_path in cleanup_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Removed {file_path}")
            except Exception as e:
                logging.warning(f"Could not remove {file_path}: {e}")

    logging.info("ECHR ETL completed successfully")


def create_tasks():
    """Create monthly task groups for ECHR ETL"""
    start_date = eval(Variable.get("ECHR_START_DATE"))
    end_date = eval(Variable.get("ECHR_END_DATE"))

    if not start_date or not end_date:
        raise ValueError("ECHR_START_DATE and ECHR_END_DATE are required in Airflow variables.")

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    logging.info("Creating tasks for ECHR ETL")
    logging.info(f"Extracting for period: {start_date} to {end_date}")

    with TaskGroup("echr_etl_tasks", tooltip="ECHR ETL tasks", dag=dag) as task_group:
        current_date = start_date
        while current_date <= end_date:
            month_end = get_month_end(current_date)
            if month_end > end_date:
                month_end = end_date

            logging.info(f"Creating task for {current_date} to {month_end}")

            PythonOperator(
                task_id=f"echr_etl_{current_date.strftime('%Y-%m')}",
                python_callable=echr_etl,
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
