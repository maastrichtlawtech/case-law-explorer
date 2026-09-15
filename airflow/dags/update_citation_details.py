import ast
import logging
import os
from datetime import datetime, timedelta

import pandas as pd
from airflow.operators.python import PythonOperator
from data_loading import data_loader
from data_loading.clients.postgres import PostgresCLEClient
from data_transformation import data_transformer
from dotenv import find_dotenv, load_dotenv
from etl_factory import get_var
from rechtspraak_citations_extractor.citations_extractor import get_citations
from rechtspraak_extractor.rechtspraak import get_rechtspraak
from rechtspraak_extractor.rechtspraak_metadata import get_rechtspraak_metadata

from airflow import DAG

default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}

dag = DAG(
    dag_id="update_citation_details",
    default_args=default_args,
    description="Update citation details in Postgres (cle_v2)",
    catchup=False,
    start_date=datetime(2025, 1, 1),
    schedule=None,
)


def read_metadata_files(raw_data_path=None):
    """
    Read all metadata_extraction_*.csv files from the raw data directory.
    """
    if raw_data_path is None:
        raw_data_path = os.path.join(get_var("DATA_PATH", "/opt/airflow/data"), "raw")
    metadata_files = []
    for root, dirs, files in os.walk(raw_data_path):
        for name in files:
            if name == "metadata_extraction_rechtspraak.csv":
                logging.info(f"Found file: {root}/{name}")
                metadata_files.append(os.path.join(root, name))
    if not metadata_files:
        logging.warning("No metadata files found in the specified directory.")
        return pd.DataFrame()
    metadata_df = pd.concat([pd.read_csv(file) for file in metadata_files], ignore_index=True)

    return metadata_df


def merge_and_extract(eclis, metadata_df, input_paths=None):
    """
    Merge the metadata dataframe with the ECLIs and extract citations.
    """
    data_path = get_var("DATA_PATH", "/opt/airflow/data")
    if input_paths is None:
        input_paths = [os.path.join(data_path, "processed", "extracted_citations.csv")]

    ecli_df = pd.DataFrame({"ecli": eclis})
    merged_df = pd.merge(ecli_df, metadata_df, on="ecli", how="inner")
    missing_eclis = ecli_df[~ecli_df["ecli"].isin(merged_df["ecli"])]["ecli"].tolist()

    if not merged_df.empty:
        logging.info("Performing citation extraction on merged data.")
        citations_df = get_citations(
            merged_df, os.getenv("LIDO_USERNAME"), os.getenv("LIDO_PASSWORD"), threads=1
        )
        citations_extraction_path = os.path.join(data_path, "processed", "citations_extraction.csv")
        citations_df.to_csv(citations_extraction_path, index=False)
        logging.info("Citation extraction completed and saved.")

        logging.info("Transforming and uploading data to Postgres.")
        output_paths = data_transformer.transform_data(
            caselaw_type="RS",
            input_paths=input_paths,
        )
        data_loader.load_data(
            input_paths=output_paths, full_text_paths=[], citation_sources=[]
        )

    return missing_eclis


def extract_missing_eclis(
    missing_eclis,
    output_path=None,
    input_paths=None,
):
    """
    Perform extraction for ECLIs that did not have any data.
    """
    data_path = get_var("DATA_PATH", "/opt/airflow/data")
    if output_path is None:
        output_path = os.path.join(data_path, "processed", "missing_citations_extraction.csv")
    if input_paths is None:
        input_paths = [output_path]

    if missing_eclis:
        logging.info("Performing extraction for missing ECLIs.")
        base_extraction = get_rechtspraak(eclis=missing_eclis, save_file="n")
        metadata_df = get_rechtspraak_metadata(dataframe=base_extraction, save_file="n")
        citations_df = get_citations(
            metadata_df,
            os.getenv("LIDO_USERNAME"),
            os.getenv("LIDO_PASSWORD"),
            threads=1,
        )
        citations_df.to_csv(output_path, index=False)

        logging.info("Transforming and uploading missing data to Postgres.")
        output_paths = data_transformer.transform_data(
            caselaw_type="RS",
            input_paths=input_paths,
        )
        data_loader.load_data(
            input_paths=output_paths, full_text_paths=[], citation_sources=[]
        )


def process_failed_eclis():
    """
    Process all custom_rechtspraak_*_failed_eclis.csv files.
    """
    data_path = get_var("DATA_PATH", "/opt/airflow/data")
    failed_files = [
        f
        for f in os.listdir(data_path)
        if f.startswith("custom_rechtspraak_") and f.endswith("_failed_eclis.csv")
    ]
    for file in failed_files:
        logging.info(f"Processing failed ECLIs from {file}.")
        failed_eclis = pd.read_csv(os.path.join(data_path, file))["ecli"].tolist()
        extract_missing_eclis(failed_eclis)


def extract_year_from_ecli(ecli):
    """
    Extract the year from the ECLI string.
    """
    try:
        return ecli.split(":")[3]
    except IndexError:
        logging.warning(f"Failed to extract year from ECLI: {ecli}")
        return None


def query_postgres_for_ecli(client, ecli):
    """
    Look up an ECLI in Postgres and return it only if it still needs legal
    provisions resolved (replaces the old DynamoDB legal_provisions_url check).
    """
    if client.resolve_case_id(ecli=str(ecli)) is None:
        return None
    return None if client.has_legal_provisions(str(ecli)) else {"ecli": str(ecli)}


def process_eclis(
    eclis,
    metadata_files_path=None,
    processed_citations_path=None,
):
    """
    Process a batch of ECLIs to extract metadata, perform citation extraction, and update Postgres.
    """
    data_path = get_var("DATA_PATH", "/opt/airflow/data")
    if metadata_files_path is None:
        metadata_files_path = os.path.join(data_path, "raw")
    if processed_citations_path is None:
        processed_citations_path = os.path.join(data_path, "processed", "extracted_citations.csv")

    min_year = int(get_var("UPDATE_CITATION_MIN_YEAR", "2020"))

    missing_eclis = []
    with PostgresCLEClient() as client:
        for ecli in eclis:
            year = extract_year_from_ecli(ecli)
            if not year or int(year) < min_year:
                logging.warning(f"ECLI {ecli} is from before {min_year}, skipping.")
                continue
            record = query_postgres_for_ecli(client, ecli)
            if record is None:
                logging.info(
                    f"ECLI {ecli} not found in Postgres or already has legal provisions resolved."
                )
                # Write to a file for later processing
                eclis_not_found_path = os.path.join(data_path, "eclis_not_found.csv")
                with open(eclis_not_found_path, "a") as f:
                    f.write(f"{ecli}\n")
                continue

            # Check only subdirectories corresponding to the year
            year_metadata_files = []
            for root, dirs, files in os.walk(metadata_files_path):
                if year in root:
                    for name in files:
                        if name == "metadata_extraction_rechtspraak.csv":
                            logging.info(f"Found metadata file for ECLI: {ecli} in {root}.")
                            year_metadata_files.append(os.path.join(root, name))

            if not year_metadata_files:
                logging.warning(f"No metadata files found for year {year} and ECLI {ecli}.")
                missing_eclis.append(ecli)
                continue

            metadata_df = pd.concat(
                [pd.read_csv(file) for file in year_metadata_files], ignore_index=True
            )
            ecli_df = pd.DataFrame({"ecli": [ecli]})
            merged_df = pd.merge(ecli_df, metadata_df, on="ecli", how="inner")

            if not merged_df.empty:
                logging.info(f"Performing citation extraction for ECLI: {ecli}.")
                logging.info(
                    "Dropping the following columns - citations_incoming, citations_outgoing, legislations_cited, bwb_id,opschrift"
                )
                merged_df = merged_df.drop(
                    columns=[
                        "citations_incoming",
                        "citations_outgoing",
                        "legislations_cited",
                        "bwb_id",
                        "opschrift",
                    ],
                    errors="ignore",
                )
                citations_df = get_citations(
                    merged_df,
                    os.getenv("LIDO_USERNAME"),
                    os.getenv("LIDO_PASSWORD"),
                    threads=1,
                )
                citations_df.to_csv(
                    processed_citations_path,
                    mode="a",
                    # header=not os.path.exists(processed_citations_path),
                    index=False,
                )
            else:
                logging.warning(f"No metadata found for ECLI: {ecli}.")
                missing_eclis.append(ecli)
    logging.info(f"Transforming and uploading data for ECLI: {ecli}.")
    output_paths = data_transformer.transform_data(
        caselaw_type="RS", input_paths=[processed_citations_path]
    )
    data_loader.load_data(input_paths=output_paths, full_text_paths=[], citation_sources=[])
    return missing_eclis


def _extract_field_set(cell, field):
    """
    Parse a citations_df cell -- a string holding a list of dicts, e.g.
    "[{'target_ecli': 'ECLI:NL:HR:2020:1234', ...}]" -- and collect the
    values of `field` into a set. Non-string/empty/unparseable cells yield
    an empty set. (The lambdas this replaces iterated the string character
    by character, so they always produced empty sets; parsing follows the
    same ast.literal_eval approach citation_update.py uses.)
    """
    if not (isinstance(cell, str) and cell.strip()):
        return {}
    try:
        items = ast.literal_eval(cell)
    except (ValueError, SyntaxError):
        return {}
    return {i[field] for i in items if isinstance(i, dict) and i.get(field)}


def update_base_metadata(**kwargs):
    files_path = kwargs["files_path"]
    processed_citations_path = kwargs["processed_citations_path"]
    logging.info(f"Processing files in {files_path}")
    # Extract the subdirectory (like 2021-04-01) name from the files_path
    dir_name = os.path.basename(os.path.normpath(files_path))
    _path = os.path.join(processed_citations_path, f"{dir_name}_extracted_citations.csv")
    if os.path.exists(_path):
        return 0
    for file in os.listdir(files_path):
        name = os.fsencode(file).decode("utf-8")
        logging.info(f"Processing file: {name}")
        if name == "base_extraction_rechtspraak.csv":
            logging.info(f"Found file: {files_path}/{name}")
            base_extraction_df = pd.read_csv(os.path.join(files_path, name))
            # replace id with ecli
            base_extraction_df.rename(columns={"id": "ecli"}, inplace=True)
            metadata_df = pd.read_csv(
                os.path.join(files_path, "metadata_extraction_rechtspraak.csv")
            )
            # Merge without duplicate columns like summary_x or summary_y
            # Check if the columns are already present in the base_extraction_df
            if "summary" in base_extraction_df.columns:
                base_extraction_df.drop(columns=["summary"], inplace=True)
            merged_df = pd.merge(base_extraction_df, metadata_df, on="ecli", how="inner")
            # If full_text column is empty, update link column with None
            merged_df.loc[merged_df["full_text"].isnull(), "link"] = None
            if not merged_df.empty:
                logging.info(
                    "Dropping the following columns - citations_incoming, citations_outgoing, legislations_cited, bwb_id,opschrift"
                )
                merged_df = merged_df.drop(
                    columns=[
                        "citations_incoming",
                        "citations_outgoing",
                        "legislations_cited",
                        "bwb_id",
                        "opschrift",
                    ],
                    errors="ignore",
                )
            try:
                # perform citation extraction
                citations_df = get_citations(
                    merged_df,
                    os.getenv("LIDO_USERNAME"),
                    os.getenv("LIDO_PASSWORD"),
                    threads=1,
                )
            except Exception as e:
                logging.info(f"Error in citation extraction: {e}")
                continue

            # Keep only target_ecli value from citations_outgoing/citations_incoming
            # column with the following structure
            # [{"target_ecli": "ECLI:NL:HR:2020:1234",
            # "target_ecli_url": "http://linkeddata.overheid.nl/cases/id/ECLI:NL:HR:2020:1234"}]
            # and store the extracted target_ecli in this structure
            # {"ECLI:NL:HR:2020:1234", "ECLI:NL:HR:2020:1234"}
            # legislations_cited follows the equivalent structure keyed by legal_provision.
            citations_df["legislations_cited"] = citations_df["legislations_cited"].apply(
                lambda x: _extract_field_set(x, "legal_provision")
            )
            citations_df["citations_outgoing"] = citations_df["citations_outgoing"].apply(
                lambda x: _extract_field_set(x, "target_ecli")
            )
            citations_df["citations_incoming"] = citations_df["citations_incoming"].apply(
                lambda x: _extract_field_set(x, "target_ecli")
            )
            # Save the citations_df to a CSV file
            citations_df.to_csv(
                _path,
                mode="w",
                index=False,
            )
            output_paths = data_transformer.transform_data(
                caselaw_type="RS",
                input_paths=[_path],
            )
            data_loader.load_data(
                input_paths=output_paths,
                full_text_paths=[],
                citation_sources=[],
            )


def run_update_citation_details(**kwargs):
    """
    Scan the raw data directory at runtime (never at DAG-parse time) and
    process each month subdirectory, optionally restricted to a configured
    list of month names.
    """
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)
    logging.info("Starting update_citation_details process by scanning raw data directory")

    data_path = get_var("DATA_PATH", "/opt/airflow/data")
    raw_data_path = os.path.join(data_path, "raw")
    processed_citations_path = os.path.join(data_path, "processed")

    months_filter = get_var("UPDATE_CITATION_MONTHS", "")
    allowed_months = {m.strip() for m in months_filter.split(",") if m.strip()}

    if not os.path.isdir(raw_data_path):
        logging.warning(f"Raw data path {raw_data_path} does not exist, nothing to process.")
        return

    subdirs = [
        d for d in os.listdir(raw_data_path) if os.path.isdir(os.path.join(raw_data_path, d))
    ]

    for subdir in subdirs:
        if allowed_months and subdir not in allowed_months:
            continue
        logging.info(f"Processing month subdirectory: {subdir}")
        update_base_metadata(
            files_path=os.path.join(raw_data_path, subdir),
            processed_citations_path=processed_citations_path,
        )
    logging.info("All month subdirectories processed successfully.")


with dag:
    update_citation_details_task = PythonOperator(
        task_id="update_citation_details_tasks",
        python_callable=run_update_citation_details,
        dag=dag,
    )
