"""
Main RS extraction routine. Used by the rechtspaark_extraction DAG.
"""

import logging
import os
from datetime import datetime, timedelta

import pandas as pd
import rechtspraak_extractor.rechtspraak as rex
from definitions.storage_handler import CSV_RS_CASES
from dotenv import find_dotenv, load_dotenv
from rechtspraak_extractor.rechtspraak_metadata import get_rechtspraak_metadata

env_file = find_dotenv()
load_dotenv(env_file, override=True)


def rechtspraak_extract(
    starting_date: str, ending_date: str, amount: int, output_dir: str, skip_if_exists: bool = True
) -> dict:
    """
    Extracts Rechtspraak data for the given date range and saves outputs in output_dir.
    Returns a dict with paths to base, metadata, and citation files.
    """
    # Prepare output file paths
    base_file = os.path.join(output_dir, "base_extraction_rechtspraak.csv")
    metadata_file = os.path.join(output_dir, "metadata_extraction_rechtspraak.csv")
    citation_file = os.path.join(output_dir, CSV_RS_CASES)

    # Check if all outputs exist
    if skip_if_exists and all(os.path.exists(f) for f in [base_file, metadata_file, citation_file]):
        logging.info(f"All output files exist in {output_dir}, skipping extraction.")
        return {"base": base_file, "metadata": metadata_file, "citations": citation_file}

    os.makedirs(output_dir, exist_ok=True)
    metadata_df_list = []
    current_date = datetime.strptime(starting_date, "%Y-%m-%d")
    end_date = datetime.strptime(ending_date, "%Y-%m-%d")

    # Extract per day in the range
    while current_date < end_date:
        next_date = current_date + timedelta(days=1)
        logging.info(f"Processing date range: {current_date.date()} - {next_date.date()}")
        base_extraction = rex.get_rechtspraak(
            max_ecli=amount, sd=str(current_date.date()), ed=str(next_date.date()), save_file="n"
        )
        # Store the dataframe for the current date
        base_file_day = os.path.join(output_dir, f"base_{current_date.date()}.csv")
        if base_extraction is not None:
            base_extraction.to_csv(base_file_day, index=False)
        metadata_df = get_rechtspraak_metadata(
            save_file="n", dataframe=base_extraction, _fake_headers=True, data_dir=output_dir
        )
        metadata_file_day = os.path.join(output_dir, f"metadata_{current_date.date()}.csv")
        if metadata_df is not None:
            metadata_df.to_csv(metadata_file_day, index=False)
            metadata_df_list.append(metadata_df)
        current_date = next_date
    # Concatenate all metadata
    if metadata_df_list:
        metadata_df = pd.concat(metadata_df_list, ignore_index=True)
        metadata_df.to_csv(metadata_file, index=False)
    else:
        metadata_df = pd.DataFrame()
        metadata_df.to_csv(metadata_file, index=False)
    # Concatenate all base extractions
    base_files = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("base_") and f.endswith(".csv")
    ]
    if base_files:
        base_df = pd.concat([pd.read_csv(f) for f in base_files], ignore_index=True)
        base_df.to_csv(base_file, index=False)
    else:
        pd.DataFrame().to_csv(base_file, index=False)
    # No LIDO call. Citations and law references come from the pg_lido database
    # that the lido_postgres DAG builds from the monthly LIDO export, so
    # resolving them a second time over the LIDO web service would be asking a
    # remote API for data already held locally.
    #
    # This still writes the same file under the same key, because it is the
    # dataset the transformer reads rather than a citations sidecar: the name
    # is from when get_citations returned the metadata frame with
    # citations_incoming, citations_outgoing and legislations_cited added to
    # it. Those three columns are now absent, which is the intended
    # consequence; MAP_RS simply finds nothing to map.
    metadata_df.to_csv(citation_file, index=False)
    return {"base": base_file, "metadata": metadata_file, "citations": citation_file}
