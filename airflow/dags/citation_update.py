import ast
import logging
import os
from datetime import datetime, timedelta

import pandas as pd
from airflow.operators.python import PythonOperator
from data_loading.clients.postgres import PostgresCLEClient
from dotenv import load_dotenv
from rechtspraak_citations_extractor.citations_extractor import get_citations

from airflow import DAG

load_dotenv()
default_args = {"owner": "none", "retries": 1, "retry_delay": timedelta(minutes=2)}

dag = DAG(
    dag_id="update_citations",
    default_args=default_args,
    description="Update citation details in Postgres (cle_v2)",
    catchup=False,
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
)


def _scan_and_update():
    """Re-run LIDO citation resolution for every known RS ecli and upsert the
    result into case_citation / case_law_reference (issue #42: replaces the
    DynamoDB whole-table scan + set-attribute update)."""
    with PostgresCLEClient() as client:
        eclis = client.list_rs_eclis()
        logging.info(f"Total eclis found: {len(eclis)}")

        eclis_to_scan = [ecli for ecli in eclis if not client.has_lido_resolution(ecli)]
        logging.info(
            f"{len(eclis_to_scan)} eclis need LIDO citation resolution "
            f"({len(eclis) - len(eclis_to_scan)} already resolved, skipped)"
        )

        for _ecli in eclis_to_scan:
            logging.info(f"Processing ECLI: {_ecli}")
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
            ):
                continue

            source_case_id = client.resolve_case_id(ecli=_ecli)
            if source_case_id is None:
                logging.warning(f"ECLI {_ecli} not found in cases table, skipping")
                continue

            # citations_outgoing: this case cites target_ecli -> case_citation rows.
            # (citations_incoming is the mirror image of another case's own
            # outgoing edge and is intentionally not written here, to avoid
            # double-writing the same edge from both directions.)
            for item in citations_df["citations_outgoing"]:
                item = ast.literal_eval(item)
                for _item in item:
                    if not (isinstance(_item, dict) and "target_ecli" in _item and _item["target_ecli"]):
                        continue
                    target_ecli = _item["target_ecli"]
                    target_case_id = client.resolve_case_id(ecli=target_ecli)
                    client.upsert_citation(
                        source_case_id=source_case_id,
                        target_case_id=target_case_id,
                        target_ecli_raw=target_ecli if target_case_id is None else None,
                        relation_type="cites",
                        source_dataset="LIDO",
                    )

            # legislations_cited -> case_law_reference (bwb scheme)
            for item, bwb_id in zip(citations_df["legislations_cited"], citations_df["bwb_id"]):
                item = ast.literal_eval(item)
                for _item in item:
                    if isinstance(_item, dict) and _item.get("legal_provision"):
                        client.upsert_law_reference(
                            case_id=source_case_id,
                            raw_reference=_item["legal_provision"],
                            raw_resource=bwb_id if isinstance(bwb_id, str) else None,
                            source_dataset="LIDO",
                        )


with dag:
    task1 = PythonOperator(
        task_id="update_citations",
        python_callable=_scan_and_update,
    )

task1
