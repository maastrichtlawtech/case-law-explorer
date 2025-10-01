import logging
import os
from calendar import monthrange
from datetime import datetime, timedelta
from airflow.models.variable import Variable
from airflow.operators.python import PythonOperator

# from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.task_group import TaskGroup
from data_extraction.caselaw.rechtspraak.rechtspraak_extraction import (
    rechtspraak_extract,
)
from data_loading import data_loader
from data_transformation import data_transformer
from dotenv import find_dotenv, load_dotenv
from rechtspraak_citations_extractor.citations_extractor import get_citations
from rechtspraak_extractor.rechtspraak_metadata import get_rechtspraak_metadata

from airflow import DAG

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

    # Setup environment
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)

    _raw_data_path = os.path.join(_data_path, "raw")
    month_dir = os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d"))

    # Check if data already exists for this date range (all outputs)
    citation_file = os.path.join(month_dir, "RS_cases.csv")
    metadata_file = os.path.join(month_dir, "metadata_extraction_rechtspraak.csv")
    base_file = os.path.join(month_dir, "base_extraction_rechtspraak.csv")
    if all(os.path.exists(f) for f in [citation_file, metadata_file, base_file]):
        logging.info(f"All output files exist in {month_dir}, skipping extraction.")
    else:
        # Run extraction for this month
        result_paths = rechtspraak_extract(
            starting_date=start_date.strftime("%Y-%m-%d"),
            ending_date=end_date.strftime("%Y-%m-%d"),
            amount=eval(Variable.get("RS_AMOUNT_TO_EXTRACT")),
            output_dir=month_dir,
            skip_if_exists=True,
        )
        citation_file = result_paths["citations"]
        metadata_file = result_paths["metadata"]
        base_file = result_paths["base"]
        logging.info(f"Extraction complete for {start_date} to {end_date}")

    # Perform data transformation
    logging.info("Starting data transformation")
    input_paths = [citation_file]
    data_transformer.transform_data(caselaw_type="RS", input_paths=input_paths)

    # Perform data loading
    logging.info("Starting data loading")
    data_loader.load_data()

    # Clean up files (optional, as before)
    logging.info("Cleaning up files")
    cleanup_files = [citation_file, metadata_file, base_file]
    for file_path in cleanup_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Removed {file_path}")
            except Exception as e:
                logging.warning(f"Could not remove {file_path}: {e}")
    logging.info("Rechtspraak ETL completed successfully")


def create_tasks():
    """Create monthly task groups for Rechtspraak ETL"""
    start_date = eval(Variable.get("RS_START_DATE"))
    end_date = eval(Variable.get("RS_END_DATE"))

    if not start_date or not end_date:
        raise ValueError("RS_START_DATE and RS_END_DATE are required in Airflow variables.")

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    logging.info("Creating tasks for Rechtspraak ETL")
    logging.info(f"Extracting for period: {start_date} to {end_date}")

    with TaskGroup("rechtspraak_etl_tasks", tooltip="Rechtspraak ETL tasks", dag=dag) as task_group:
        current_date = start_date
        while current_date <= end_date:
            month_end = get_month_end(current_date)
            if month_end > end_date:
                month_end = end_date

            logging.info(f"Creating task for {current_date} to {month_end}")

            PythonOperator(
                task_id=f"rechtspraak_etl_{current_date.strftime('%Y-%m')}",
                python_callable=rechtspraak_etl,
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
    # initializer = PythonOperator(
    #     task_id="initializer",
    #     python_callable=create_tasks,
    #     provide_context=True,
    # )
    # initializer
