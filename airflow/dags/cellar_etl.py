import logging
import os
from datetime import datetime

from data_extraction.caselaw.cellar.cellar_extraction import cellar_extract
from data_loading import data_loader
from data_transformation import data_transformer
from dotenv import find_dotenv, load_dotenv
from etl_factory import (
    DEFAULT_ARGS,
    build_monthly_task_group,
    cleanup_raw_files,
    get_var,
)

from airflow import DAG

dag = DAG(
    dag_id="cellar_etl",
    default_args=DEFAULT_ARGS,
    description="Cellar ETL with monthly task groups",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule=None,
)


def cellar_etl(**kwargs):
    """Main Cellar ETL function for a specific month"""
    start_date = kwargs["start_date"]
    end_date = kwargs["end_date"]
    _data_path = kwargs["_data_path"]

    logging.info(f"Starting Cellar ETL for {start_date} to {end_date}")

    # Setup environment
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)

    date_str = start_date.strftime("%Y-%m-%d")
    month_dir = os.path.join(_data_path, "raw", date_str)

    extraction_args = [
        "--starting-date",
        date_str,
        "--amount",
        str(int(get_var("CELLAR_AMOUNT_TO_EXTRACT", "1000"))),
        "--ending-date",
        end_date.strftime("%Y-%m-%d"),
    ]
    raw_paths = cellar_extract(
        extraction_args, output_dir=month_dir, skip_if_exists=True
    )
    logging.info("Cellar extraction completed")

    # Transform into a month-scoped processed dir, then load exactly those
    # outputs plus this month's full text and citation edges.
    logging.info("Starting data transformation")
    processed_paths = data_transformer.transform_data(
        caselaw_type="CELLAR",
        input_paths=[raw_paths["metadata"]],
        output_dir=os.path.join(_data_path, "processed", date_str),
    )

    logging.info("Starting data loading")
    data_loader.load_data(
        input_paths=processed_paths,
        full_text_paths=[raw_paths["full_text"]],
        citation_sources=["EURLEX"],
        edge_dir=month_dir,
    )

    cleanup_raw_files(
        [
            raw_paths["metadata"],
            raw_paths["full_text"],
            raw_paths["nodes"],
            raw_paths["edges"],
        ]
    )
    logging.info("Cellar ETL completed successfully")


with dag:
    build_monthly_task_group(dag, "cellar_etl", "CELLAR", cellar_etl)
