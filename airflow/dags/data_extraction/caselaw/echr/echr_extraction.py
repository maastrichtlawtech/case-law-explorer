"""
Main ECHR extraction routine. Used by the echr_etl DAG.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from os import getenv
from os.path import basename, join

import echr_extractor as echr
import pandas as pd
from airflow.models.variable import Variable
from definitions.storage_handler import (
    CSV_ECHR_CASES,
    JSON_FULL_TEXT_ECHR,
    TXT_ECHR_EDGES,
    TXT_ECHR_NODES,
    Storage,
    get_path_raw,
)
from dotenv import find_dotenv, load_dotenv

env_file = find_dotenv()
load_dotenv(env_file, override=True)


def _output_paths(output_dir):
    """Extraction artifact paths: month-scoped under output_dir when given,
    otherwise the legacy global raw-dir locations."""
    if output_dir:
        return {
            "metadata": join(output_dir, CSV_ECHR_CASES),
            "full_text": join(output_dir, basename(JSON_FULL_TEXT_ECHR)),
            "nodes": join(output_dir, TXT_ECHR_NODES),
            "edges": join(output_dir, TXT_ECHR_EDGES),
            "missing_references": join(output_dir, "ECHR_missing_references.csv"),
        }
    return {
        "metadata": get_path_raw(CSV_ECHR_CASES),
        "full_text": JSON_FULL_TEXT_ECHR,
        "nodes": get_path_raw(TXT_ECHR_NODES),
        "edges": get_path_raw(TXT_ECHR_EDGES),
        "missing_references": get_path_raw("ECHR_missing_references.csv"),
    }


def _resolve_external_citations_enabled():
    return str(
        Variable.get(
            "ECHR_RESOLVE_EXTERNAL_CITATIONS",
            default_var=getenv("ECHR_RESOLVE_EXTERNAL_CITATIONS", "true"),
        )
    ).lower() in ("true", "1", "yes")


def _write_citation_artifacts(metadata, paths):
    nodes, edges, missing = echr.get_nodes_edges(
        df=metadata,
        save_file="n",
        resolve_external=_resolve_external_citations_enabled(),
    )
    nodes[["ecli"]].to_csv(paths["nodes"], index=False, header=False)
    with open(paths["edges"], "w") as f:
        for _, row in edges.iterrows():
            for target in row["references"]:
                f.write(f"{row['ecli']},{target}\n")
    missing.to_csv(paths["missing_references"], index=False)


def echr_extract(args, output_dir=None, skip_if_exists: bool = False) -> dict:
    """
    Run the ECHR extraction. Writes metadata CSV, full-text JSON, and
    node/edge txt files, and returns their paths. With no --start-date,
    continues from the ECHR_LAST_DATE Airflow Variable.
    """
    paths = _output_paths(output_dir)
    if skip_if_exists and os.path.exists(paths["metadata"]):
        if not all(
            os.path.exists(paths[name]) for name in ("edges", "missing_references")
        ):
            logging.info("Rebuilding missing ECHR citation artifacts from metadata")
            _write_citation_artifacts(pd.read_csv(paths["metadata"]), paths)
        logging.info(f"{paths['metadata']} exists, skipping extraction.")
        return paths

    # set up script arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start-id",
        help="id of the first case to be downloaded",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "--end-id",
        help="id of the last case to be downloaded",
        type=int,
        required=False,
        default=None,
    )
    parser.add_argument(
        "--count",
        help="The number of cases to be downloaded, starting from the start_id. "
        "WARNING:If count is provided, the end_id will be set to start_id+count, "
        "overwriting any given end_id value.",
        type=int,
        required=False,
        default=None,
    )
    parser.add_argument(
        "--start-date",
        help="Last modification date to look forward from",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--end-date",
        help="Last modification date to look back from",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--skip-missing-dates",
        help="This option makes the extraction not collect data for\
                         cases where there is no judgement date provided.",
        type=bool,
        default=False,
        required=False,
    )
    parser.add_argument("--fields", help="The fields to be extracted", required=False)
    parser.add_argument(
        "--fresh",
        help="Flag for running a complete download regardless of existing downloads",
        action="store_true",
    )
    parser.add_argument(
        "--language",
        nargs="+",
        help="The languages to be extracted",
        required=False,
        default=["ENG", "FRE"],
    )

    args, unknown = parser.parse_known_args(args)
    logging.info("--- PREPARATION ---")
    logging.info("OUTPUT:\t\t\t" + paths["metadata"])

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    else:
        # legacy global-path mode: refuse to clobber an existing extraction
        Storage().setup_pipeline(output_paths=[paths["metadata"]])

    # Explicitly dated monthly tasks do not need the shared incremental
    # checkpoint. Avoiding it also prevents parallel July/August tasks from
    # racing to create the same Airflow Variable.
    last_updated = args.start_date
    if not last_updated:
        try:
            # Getting date of last update from airflow database
            last_updated = Variable.get("ECHR_LAST_DATE")
        except Exception:
            last_updated = getenv("ECHR_START_DATE")
            Variable.set(key="ECHR_LAST_DATE", value=last_updated)

    today_date = str(datetime.today().date())
    logging.info("START DATE (LAST UPDATE):" + last_updated)

    logging.info("--- START ---")
    start = time.time()

    logging.info("--- Extract ECHR data")
    kwargs = {
        "start_id": args.start_id,
        "end_id": args.end_id,
        "count": args.count,
        "fields": args.fields,
        "language": args.language,
    }
    logging.info(kwargs)
    logging.info(
        f"Downloading {args.count if 'count' in args and args.count is not None else 'all'} ECHR documents"
    )
    if args.fresh:
        metadata, full_text = echr.get_echr_extra(
            **kwargs, start_date="1990-01-01", save_file="n"
        )
    elif args.start_date and args.end_date:
        logging.info(
            f"Starting from manually specified date: {args.start_date} and ending at end date: {args.end_date}"
        )
        metadata, full_text = echr.get_echr_extra(
            **kwargs, start_date=args.start_date, end_date=args.end_date, save_file="n"
        )
    elif args.start_date:
        logging.info(f"Starting from manually specified date: {args.start_date}")
        metadata, full_text = echr.get_echr_extra(
            **kwargs, start_date=args.start_date, save_file="n"
        )
    elif args.end_date:
        logging.info(f"Ending at manually specified end date {args.end_date}")
        metadata, full_text = echr.get_echr_extra(
            **kwargs, end_date=args.end_date, save_file="n"
        )
    else:
        logging.info("Starting from the last update the script can find")
        metadata, full_text = echr.get_echr_extra(
            **kwargs, start_date=last_updated, end_date=today_date, save_file="n"
        )

    logging.info("--- saving ECHR data")
    if metadata is not False:
        metadata.to_csv(paths["metadata"], index=False)
        with open(paths["full_text"], "w") as f:
            json.dump(full_text, f)
        logging.info("Adding Nodes and Edges lists to storage")
        # Getting nodes and edges, citation-based. For creating a citation graph
        # One "<source>,<target>" line per citation: the format the citation
        # graph loader parses. Missing references are retained for verification.
        _write_citation_artifacts(metadata, paths)
    else:
        logging.info("No ECHR data found")

    end = time.time()
    logging.info("--- DONE ---")
    logging.info(f"Time taken: {time.strftime('%H:%M:%S', time.gmtime(end - start))}")
    if not args.start_date:
        Variable.set(key="ECHR_LAST_DATE", value=args.end_date or today_date)
    return paths


if __name__ == "__main__":
    echr_extract(sys.argv[1:])
