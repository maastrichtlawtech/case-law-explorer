import ast
import logging
import os
from datetime import datetime, timedelta

import boto3
import pandas as pd
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv
from rechtspraak_citations_extractor.citations_extractor import get_citations

from airflow import DAG

load_dotenv()
default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}

dag = DAG(
    dag_id="update_citations",
    default_args=default_args,
    description="Update citation details in DynamoDB",
    catchup=False,
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
)


def scan_entire_table():
    # Initialize DynamoDB connection inside the function
    ddb_table_name = os.getenv("DDB_TABLE_NAME")
    if not ddb_table_name:
        raise ValueError("DDB_TABLE_NAME environment variable is not set")

    dynamodb = boto3.resource(
        "dynamodb",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="eu-central-1",
    )
    table = dynamodb.Table(ddb_table_name)

    items = []
    scan_kwargs = {"ProjectionExpression": "ecli, ItemType"}
    response = table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"], **scan_kwargs)
        items.extend(response.get("Items", []))

    return items, table


def _scan_and_update():
    items, table = scan_entire_table()
    logging.info(f"Total items found: {len(items)}")
    # logging.info(f"{items}")
    for item in items:
        if item["ecli"] is not None:
            logging.info(f"Processing item with ECLI: {item}")
            _ecli = item["ecli"]
            if item["ItemType"] == "DATA":
                df = pd.DataFrame([{"ecli": _ecli}])
                citations_df = get_citations(
                    df,
                    username=os.getenv("LIDO_USERNAME"),
                    password=os.getenv("LIDO_PASSWORD"),
                    extract_opschrift=True,
                )
                if (
                    citations_df["legislations_cited"].isnull().any()
                    or (citations_df["legislations_cited"] == "<NA>").any()
                    or citations_df["citations_outgoing"].isnull().any()
                    or (citations_df["citations_outgoing"] == "<NA>").any()
                    or citations_df["citations_incoming"].isnull().any()
                    or (citations_df["citations_incoming"] == "<NA>").any()
                ):
                    continue
                else:
                    key = {"ecli": _ecli, "ItemType": "DATA"}
                    # Extract target_ecli value from citations_df['citations_incoming'] and citations_df['citations_outgoing'] which is stored as a dictionary
                    # and store it as a string set
                    citations_incoming = []
                    for item in citations_df["citations_incoming"]:
                        item = ast.literal_eval(item)
                        for _item in item:
                            if isinstance(_item, dict) and "target_ecli" in _item:
                                citations_incoming.append(_item["target_ecli"])
                            else:
                                citations_incoming.append("")
                    # Convert citations_incoming to a string set
                    # Create a string set from list of dictionaries with key as "target_ecli"
                    citations_outgoing = []
                    for item in citations_df["citations_outgoing"]:
                        item = ast.literal_eval(item)
                        for _item in item:
                            if isinstance(_item, dict) and "target_ecli" in _item:
                                citations_outgoing.append(_item["target_ecli"])
                            else:
                                citations_outgoing.append("")
                    legislations_cited = []
                    legislations_url = []
                    legilsation_url_lido = []
                    for item in citations_df["legislations_cited"]:
                        item = ast.literal_eval(item)
                        for _item in item:
                            if isinstance(_item, dict):
                                if "legal_provision" in _item:
                                    legislations_cited.append(_item["legal_provision"])
                                else:
                                    legislations_cited.append("")
                                if "legal_provision_url" in _item:
                                    legislations_url.append(_item["legal_provision_url"])
                                else:
                                    legislations_url.append("")
                                if "legal_provision_url_lido" in _item:
                                    legilsation_url_lido.append(_item["legal_provision_url_lido"])
                                else:
                                    legilsation_url_lido.append("")
                    # Convert opschrift from list to string set
                    opschrift = []
                    for item in citations_df["opschrift"]:
                        for _item in item:
                            print(_item)
                            if isinstance(_item, str):
                                opschrift.append(_item)
                            else:
                                opschrift.append("")
                    bwb_id = set(
                        item if isinstance(item, str) else ""
                        for item in citations_df["bwb_id"].tolist()
                    )
                    response = table.update_item(
                        Key=key,
                        UpdateExpression="SET cited_by = :newval, legal_provision = :legislations, citing = :citing, opschrift = :opschrift, bwb_id = :bwb_id, legal_provision_url = :url, legal_provision_url_lido = :legilsation_url_lido",
                        ExpressionAttributeValues={
                            ":newval": set(citations_incoming),
                            ":legislations": set(legislations_cited),
                            ":citing": set(citations_outgoing),
                            ":opschrift": set(opschrift),
                            ":bwb_id": bwb_id,
                            ":url": set(legislations_url),
                            ":legilsation_url_lido": set(legilsation_url_lido),
                        },
                        ReturnValues="UPDATED_NEW",
                    )
                    logging.info(f"Response from update: {response}")
            else:
                continue


with dag:
    task1 = PythonOperator(
        task_id="update_citations",
        python_callable=_scan_and_update,
    )

task1
