import logging
import os
from datetime import datetime

from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from data_extraction.caselaw.rechtspraak.rechtspraak_extraction import (
    rechtspraak_extract,
)
from data_loading import data_loader
from data_transformation import data_transformer
from dotenv import find_dotenv, load_dotenv
from etl_factory import (
    DEFAULT_ARGS,
    build_monthly_task_group,
    cleanup_raw_files,
    get_optional_int,
    get_schedule,
    register_promotion,
)
from lido_sqlite_paths import get_lido_sqlite_paths

from airflow import DAG

dag = DAG(
    dag_id="rechtspraak_etl",
    default_args=DEFAULT_ARGS,
    description="Scheduled and manually windowed Rechtspraak ETL",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule=get_schedule("RS", "0 2 * * 1"),
    max_active_runs=1,
    max_active_tasks=1,
)


def rechtspraak_etl(**kwargs):
    start_date = kwargs["start_date"]
    end_date = kwargs["end_date"]
    _data_path = kwargs["_data_path"]
    force_refresh = kwargs.get("force_refresh", False)
    logging.info(f"Starting Rechtspraak ETL for {start_date} to {end_date}")

    # Setup environment
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)

    date_str = start_date.strftime("%Y-%m-%d")
    month_dir = os.path.join(_data_path, "raw", date_str)

    # Check if data already exists for this date range (all outputs)
    citation_file = os.path.join(month_dir, "RS_cases.csv")
    metadata_file = os.path.join(month_dir, "metadata_extraction_rechtspraak.csv")
    base_file = os.path.join(month_dir, "base_extraction_rechtspraak.csv")
    if not force_refresh and all(
        os.path.exists(f) for f in [citation_file, metadata_file, base_file]
    ):
        logging.info(f"All output files exist in {month_dir}, skipping extraction.")
    else:
        # Run extraction for this month
        _, lido_sqlite_db_path = get_lido_sqlite_paths(_data_path)
        result_paths = rechtspraak_extract(
            starting_date=date_str,
            ending_date=end_date.strftime("%Y-%m-%d"),
            amount=get_optional_int("RS_AMOUNT_TO_EXTRACT") or 1_000_000,
            output_dir=month_dir,
            skip_if_exists=not force_refresh,
            lido_sqlite_db_path=str(lido_sqlite_db_path),
        )
        citation_file = result_paths["citations"]
        metadata_file = result_paths["metadata"]
        base_file = result_paths["base"]
        logging.info(f"Extraction complete for {start_date} to {end_date}")

    # Transform into a month-scoped processed dir, then load exactly those
    # outputs. RS full text and citations arrive via the CSV itself, so no
    # full-text JSONs or edge files to load.
    logging.info("Starting data transformation")
    processed_paths = data_transformer.transform_data(
        caselaw_type="RS",
        input_paths=[citation_file],
        output_dir=os.path.join(_data_path, "processed", date_str),
    )

    logging.info("Starting data loading")
    data_loader.load_data(input_paths=processed_paths, full_text_paths=[], citation_sources=[])

    cleanup_raw_files([citation_file, metadata_file, base_file])
    logging.info("Rechtspraak ETL completed successfully")


with dag:
    etl_tasks = build_monthly_task_group(dag, "rechtspraak_etl", "RS", rechtspraak_etl)
    terminal = etl_tasks

    # Only chain segmentation on when there is a segmentation service to call.
    #
    # This used to be unconditional, so a deployment without one finished its
    # extraction and load and then failed anyway on a task that could not have
    # worked, leaving the whole run looking broken over an optional step.
    #
    # The check is the environment variable rather than segmentation.config,
    # because that module falls back to a default URL when the variable is
    # unset, and a default pointing at a service nobody deployed fails at
    # request time instead of reading as unconfigured.
    if os.getenv("SEGMENTATION_API_URL", "").strip():
        trigger_segmentation = TriggerDagRunOperator(
            task_id="trigger_case_segmentation",
            trigger_dag_id="case_segmentation",
            wait_for_completion=False,
        )
        etl_tasks >> trigger_segmentation
        terminal = trigger_segmentation
    else:
        logging.info(
            "SEGMENTATION_API_URL is not set, so rechtspraak_etl does not "
            "trigger case_segmentation."
        )

    promotion = PythonOperator(
        task_id="register_promotion",
        python_callable=register_promotion,
        op_kwargs={"dag_id": "rechtspraak_etl", "var_prefix": "RS"},
    )
    terminal >> promotion
