"""
Main cellar extraction routine. Used by the cellar_etl DAG.
"""

import argparse
import json
import logging
import os
import ssl
import sys
import time
from os import getenv
from os.path import basename, join

import cellar_extractor as cell
import requests
import urllib3
from airflow.models.variable import Variable
from definitions.storage_handler import (
    CSV_CELLAR_CASES,
    JSON_FULL_TEXT_CELLAR,
    TXT_CELLAR_EDGES,
    TXT_CELLAR_NODES,
    Storage,
    get_path_raw,
)
from dotenv import find_dotenv, load_dotenv
from helpers.csv_manipulator import drop_columns

env_file = find_dotenv()
load_dotenv(env_file, override=True)


def _output_paths(output_dir):
    """Extraction artifact paths: month-scoped under output_dir when given,
    otherwise the legacy global raw-dir locations."""
    if output_dir:
        return {
            "metadata": join(output_dir, CSV_CELLAR_CASES),
            "full_text": join(output_dir, basename(JSON_FULL_TEXT_CELLAR)),
            "nodes": join(output_dir, TXT_CELLAR_NODES),
            "edges": join(output_dir, TXT_CELLAR_EDGES),
        }
    return {
        "metadata": get_path_raw(CSV_CELLAR_CASES),
        "full_text": JSON_FULL_TEXT_CELLAR,
        "nodes": get_path_raw(TXT_CELLAR_NODES),
        "edges": get_path_raw(TXT_CELLAR_EDGES),
    }


def cellar_extract(args, output_dir=None, skip_if_exists: bool = False) -> dict:
    """
    Run the CELLAR extraction. Writes metadata CSV, full-text JSON, and
    node/edge txt files, and returns their paths. With no --starting-date,
    continues from the CELEX_LAST_DATE Airflow Variable.
    """
    paths = _output_paths(output_dir)
    if skip_if_exists and os.path.exists(paths["metadata"]):
        logging.info(f"{paths['metadata']} exists, skipping extraction.")
        return paths

    # Disable SSL verification for this task only: the CELLAR endpoint's
    # certificate chain fails validation from some networks. Runs inside the
    # forked task process, so other DAGs' HTTPS calls keep verification.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    ssl._create_default_https_context = ssl._create_unverified_context
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    os.environ["CURL_CA_BUNDLE"] = ""

    parser = argparse.ArgumentParser()
    parser.add_argument("--amount", help="number of documents to retrieve", type=int, required=False)
    parser.add_argument("--starting-date", help="Last modification date to look forward from", required=False)
    parser.add_argument("--ending-date", help="Last modification date to look forward from", required=False)
    # Airflow gives extra arguments ('celery worker'); ignore unknown args.
    args, unknown = parser.parse_known_args(args)

    logging.info("--- PREPARATION ---")
    logging.info("OUTPUT:\t\t\t" + paths["metadata"])
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    else:
        # legacy global-path mode: refuse to clobber an existing extraction
        Storage().setup_pipeline(output_paths=[paths["metadata"]])

    if args.starting_date:
        starting_date = args.starting_date
    else:
        try:
            starting_date = Variable.get("CELEX_LAST_DATE")
        except Exception:
            starting_date = getenv("CELLAR_START_DATE")
            Variable.set(key="CELEX_LAST_DATE", value=starting_date)

    logging.info(f"START DATE (LAST UPDATE):\t{starting_date}")
    logging.info("--- START ---")
    start = time.time()
    amount = args.amount if args.amount is not None else 1000000
    logging.info(f"Downloading {amount} CELLAR documents")

    # Session with SSL verification disabled, patched into cellar_extractor
    session = requests.Session()
    session.verify = False
    session.trust_env = False
    if hasattr(cell, "requests"):
        cell.requests.Session = lambda: session

    # No EUR-Lex webservice credentials. 2.x documents username and password as
    # deprecated and ignored, and enriches citations over SPARQL
    # unconditionally, so requiring them only refused to run over something the
    # library would not have read.
    #
    # save=False with return_data=True replaces save_file="n". The old spelling
    # still resolves to the same thing in 2.x, as a deprecated alias.
    metadata, full_text_json = cell.get_cellar_extra(
        save=False,
        return_data=True,
        max_ecli=amount,
        sd=starting_date,
        ed=args.ending_date,
        threads=15,
    )

    if isinstance(metadata, bool):
        # package returns False if no data was found
        logging.warning("Cellar extractor returned boolean value - no data found")
        return paths

    logging.info("Updating local storage ...")

    # We are only interested in european cases.
    # Cellar extractor extracts everything with an ecli
    # Drop_columns makes sure we only keep what we are interested in from the download.
    drop_columns(metadata)
    metadata.to_csv(paths["metadata"], index=False)

    # Additional check to drop non-european, irrelevant (for us) cases
    final_full_texts = [j for j in full_text_json if not j.get("celex").startswith("8")]
    with open(paths["full_text"], "w") as f:
        json.dump(final_full_texts, f)

    # Node and edge lists based on citations, for the citation graph
    nodes, edges = cell.get_nodes_and_edges_lists(metadata)
    if nodes is not False:
        with open(paths["nodes"], "w") as f:
            f.write("\n".join(nodes))
    else:
        logging.info("No nodes found")
    if edges is not False:
        with open(paths["edges"], "w") as f:
            f.write("\n".join(edges))
    else:
        logging.info("No edges found")

    end = time.time()
    logging.info("--- DONE ---")
    logging.info(f"Time taken: {time.strftime('%H:%M:%S', time.gmtime(end - start))}")
    # Start date for the next incremental download
    Variable.set(key="CELEX_LAST_DATE", value=args.ending_date)
    return paths


if __name__ == "__main__":
    cellar_extract(sys.argv[1:])
