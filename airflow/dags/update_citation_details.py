import ast
import os
import pandas as pd
import boto3
import logging

from airflow import DAG
from airflow.utils.task_group import TaskGroup
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from rechtspraak_citations_extractor.citations_extractor import get_citations
from rechtspraak_extractor.rechtspraak import get_rechtspraak
from rechtspraak_extractor.rechtspraak_metadata import get_rechtspraak_metadata
from data_transformation import data_transformer
from data_loading import data_loader
from boto3.dynamodb.conditions import Attr, Key
from concurrent.futures import ThreadPoolExecutor

default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}

dag = DAG(
    dag_id="update_citation_details",
    default_args=default_args,
    description="Update citation details in DynamoDB",
    catchup=False,
    start_date=datetime(2025,1,1),
    schedule_interval=None,
)

# DynamoDB client
# Load environment variables
load_dotenv()


def read_metadata_files(raw_data_path="data/raw/"):
    """
    Read all metadata_extraction_*.csv files from the data/raw/ directory.
    """
    metadata_files = []
    for root, dirs, files in os.walk(raw_data_path):
        for name in files:
            if name == "metadata_extraction_rechtspraak.csv":
                logging.info(f"Found file: {root}/{name}")
                metadata_files.append(os.path.join(root, name))
    if not metadata_files:
        logging.warning("No metadata files found in the specified directory.")
        return pd.DataFrame()
    metadata_df = pd.concat(
        [pd.read_csv(file) for file in metadata_files], ignore_index=True
    )

    return metadata_df


def merge_and_extract(eclis, metadata_df,  input_paths=["data/processed/extracted_citations.csv"]):
    """
    Merge the metadata dataframe with the ECLIs and extract citations.
    """
    ecli_df = pd.DataFrame({"ecli": eclis})
    merged_df = pd.merge(ecli_df, metadata_df, on="ecli", how="inner")
    missing_eclis = ecli_df[~ecli_df["ecli"].isin(merged_df["ecli"])]["ecli"].tolist()

    if not merged_df.empty:
        logging.info("Performing citation extraction on merged data.")
        citations_df = get_citations(
            merged_df, os.getenv("LIDO_USERNAME"), os.getenv("LIDO_PASSWORD"), threads=1
        )
        citations_df.to_csv("data/processed/citations_extraction.csv", index=False)
        logging.info("Citation extraction completed and saved.")

        logging.info("Transforming and uploading data to DynamoDB.")
        data_transformer.transform_data(
            caselaw_type="RS",
            input_paths=input_paths,
        )
        data_loader.load_data()

    return missing_eclis


def extract_missing_eclis(missing_eclis, output_path="data/processed/missing_citations_extraction.csv",
                          input_paths=["data/processed/missing_citations_extraction.csv"]):
    """
    Perform extraction for ECLIs that did not have any data.
    """
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
        citations_df.to_csv(
            output_path, index=False
        )

        logging.info("Transforming and uploading missing data to DynamoDB.")
        data_transformer.transform_data(
            caselaw_type="RS",
            input_paths=input_paths,
        )
        data_loader.load_data()


def process_failed_eclis():
    """
    Process all custom_rechtspraak_*_failed_eclis.csv files.
    """
    failed_files = [
        f
        for f in os.listdir("data/")
        if f.startswith("custom_rechtspraak_") and f.endswith("_failed_eclis.csv")
    ]
    for file in failed_files:
        logging.info(f"Processing failed ECLIs from {file}.")
        failed_eclis = pd.read_csv(os.path.join("data", file))["ecli"].tolist()
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


def query_dynamodb_for_ecli(ecli):
    """
    Query DynamoDB for a specific ECLI and check if legal_provisions_url is empty.
    """
    table = boto3.resource("dynamodb").Table(os.getenv("DDB_TABLE_NAME"))
    response = table.query(KeyConditionExpression=Key("ecli").eq(str(ecli)))
    item = response.get("Item", {})
    return item if not item.get("legal_provisions_url") else None


def process_eclis(eclis, metadata_files_path="data/raw/", processed_citations_path="data/processed/extracted_citations.csv"):
    """
    Process a batch of ECLIs to extract metadata, perform citation extraction, and update DynamoDB.
    """
    missing_eclis = []
    for ecli in eclis:
        year = extract_year_from_ecli(ecli)
        if not year or int(year) < 2020:
            logging.warning(f"ECLI {ecli} is from before 2020, skipping.")
            continue
        record = query_dynamodb_for_ecli(ecli)
        if record is None:
            logging.info(f"ECLI {ecli} not found in DynamoDB.")
            # Write to a file for later processing
            with open("data/eclis_not_found.csv", "a") as f:
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
            logging.info("Dropping the following columns - citations_incoming, citations_outgoing, legislations_cited, bwb_id,opschrift")
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
    data_transformer.transform_data(
        caselaw_type="RS", input_paths=[processed_citations_path]
    )
    data_loader.load_data()
    return missing_eclis


def update_base_metadata(**kwargs):
    files_path = kwargs["files_path"]
    processed_citations_path = kwargs["processed_citations_path"]
    logging.info(f"Processing files in {files_path}")
    # Extract the subdirectory (like 2021-04-01) name from the files_path
    dir_name = os.path.basename(os.path.normpath(files_path))
    _path = processed_citations_path + dir_name + "_extracted_citations.csv"
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
            merged_df = pd.merge(
                base_extraction_df, metadata_df, on="ecli", how="inner"
            )
            # If full_text column is empty, update link column with None
            merged_df.loc[
                merged_df["full_text"].isnull(), "link"
            ] = None
            try:
                # perform citation extraction
                citations_df = get_citations(
                    merged_df,
                    os.getenv("LIDO_USERNAME"),
                    os.getenv("LIDO_PASSWORD"),
                    threads=6,
                )
            except Exception as e:
                logging.info(f"Error in citation extraction: {e}")
                continue
            citations_df["legislations_cited"] = citations_df[
                "legislations_cited"
            ].apply(
                lambda x: {
                    i["legal_provision"]
                    for i in ast.literal_eval(x) if isinstance(x, str) and "legal_provision" in i
                } if isinstance(x, str) else {}
            )
            # Keep only target_ecli value from citations_outgoing column with the following structure
            # [{"target_ecli": "ECLI:NL:HR:2020:1234",
            # "target_ecli_url": "http://linkeddata.overheid.nl/cases/id/ECLI:NL:HR:2020:1234"}]
            # and store the extracted target_ecli in this structure
            # {"ECLI:NL:HR:2020:1234", "ECLI:NL:HR:2020:1234"}
            citations_df["citations_outgoing"] = citations_df[
                "citations_outgoing"
            ].apply(
                lambda x: {
                    i["target_ecli"]
                    for i in eval(x) if isinstance(x, str) and "target_ecli" in i
                } if x is not None else x
            )
            citations_df["legislations_cited"] = citations_df[
                "legislations_cited"
            ].apply(
                lambda x: {
                    i["legal_provision"]
                    for i in eval(x) if isinstance(x, str) and "legal_provision" in i
                } if x is not None else x
            )
            citations_df["citations_incoming"] = citations_df[
                "citations_incoming"
            ].apply(
                lambda x: {
                    i["target_ecli"]
                    for i in eval(x) if isinstance(x, str) and "target_ecli" in i
                } if x is not None else x
            )
            # Save the citations_df to a CSV file
            citations_df.to_csv(
                _path,
                mode="w",
                index=False,
            )
            data_transformer.transform_data(
                caselaw_type="RS",
                input_paths=[
                    _path
                ],
            )
            data_loader.load_data(input_paths=[
                processed_citations_path + str(dir_name) + "_extracted_citations_clean.csv"
                ],
            )


def create_tasks():
    env_file = find_dotenv()
    load_dotenv(env_file, override=True)
    logging.info("Starting update_citation_details process by creating tasks for each month")
    # Find the number of subdirectories in the data/raw/ directory
    subdirs = [
        d
        for d in os.listdir("data/raw/")
        if os.path.isdir(os.path.join("data/raw/", d))
    ]
    # Create a task for each subdirectory
    with TaskGroup(
        "update_citation_details_tasks", tooltip="Update citation details", dag=dag
    ) as task_group:
        for subdir in subdirs:
            PythonOperator(
                task_id=f"process_{subdir}",
                python_callable=update_base_metadata,
                op_kwargs={
                    "files_path": f"data/raw/{subdir}/",
                    "processed_citations_path": f"data/processed/",
                },
                dag=dag,
            )
    logging.info("All tasks created successfully.")
    return task_group

with dag:
    create_tasks()
