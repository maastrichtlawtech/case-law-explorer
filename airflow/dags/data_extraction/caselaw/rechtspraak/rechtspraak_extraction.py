"""
Main RS extraction routine. Used by the rechtspaark_extraction DAG.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from os.path import abspath, dirname

import pandas as pd
import rechtspraak_extractor.rechtspraak as rex
from airflow.models.variable import Variable
from definitions.storage_handler import CSV_RS_CASES
from dotenv import find_dotenv, load_dotenv
from rechtspraak_citations_extractor.citations_extractor import get_citations
from rechtspraak_extractor.rechtspraak_metadata import get_rechtspraak_metadata

env_file = find_dotenv()
load_dotenv(env_file, override=True)
LIDO_USERNAME = os.getenv("LIDO_USERNAME")
LIDO_PASSWORD = os.getenv("LIDO_PASSWORD")

try:
    RS_SETUP = eval(Variable.get("RS_SETUP"))
except Exception:
    RS_SETUP = True
    Variable.set(key="RS_SETUP", value=True)

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))


def get_rs_setup_args():
    """
    RS database setup routine - for building entire DB from scratch.
    There are millions of cases, more than possible to extract at once.
    This method returns the start&end dates for extraction, as well as the amount - arguments for RS extractions.
    Index referenced in code is the index of last visited point in the var_list.
    Indexes stored via airflow DB. Proper usage will setup the entire database, with small increments, year by year.
    Only works when RS_SETUP in .env file is set to True.
    In case of rerunning the DB setup, don't forget to reset the airflow database.
    """
    amount = 1200000
    var_list = [
        "1995-01-01",
        "1996-01-01",
        "1997-01-01",
        "1998-01-01",
        "1999-01-01",
        "2000-01-01",
        "2001-01-01",
        "2002-01-01",
        "2003-01-01",
        "2004-01-01",
        "2005-01-01",
        "2006-01-01",
        "2007-01-01",
        "2008-01-01",
        "2009-01-01",
        "2010-01-01",
        "2011-01-01",
        "2012-01-01",
        "2013-01-01",
        "2014-01-01",
        "2015-01-01",
        "2016-01-01",
        "2017-01-01",
        "2018-01-01",
        ~"2019-01-01",
        "2020-01-01",
        "2021-01-01",
        "2022-01-01",
        "2023-01-01",
    ]  # 29
    try:
        index = eval(Variable.get("RS_SETUP_INDEX"))  # start index
        next_index = index + 1  # end index
        if index >= len(var_list):  # if start is out, no extraction out
            starting = None
            ending = None
            Variable.set(key="RS_SETUP", value=False)
        else:  # starting is in
            starting = var_list[index]
            if next_index >= len(var_list):  # determine if end is there or no
                ending = None
            else:
                ending = var_list[next_index]
    except Exception:
        logging.info("NO INDEX YET SET")
        next_index = 0
        ending = var_list[0]
        starting = None

    return starting, ending, amount, next_index


def _store_dataframe_per_date(df, date, _filename, _path="data/processed/"):
    """
    Store the dataframe for a specific date in a CSV file.
    The filename is based on the date.
    """
    date_str = date.strftime("%Y-%m-%d")
    filename = f"rechtspraak_{_filename}_{date_str}.csv"
    # Store in directory data/processed/date_str
    filepath = os.path.join(_path, date_str, filename)
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # Store the dataframe in the CSV file
    if df is None:
        logging.info(f"No data to store for {date_str}")
        return
    df.to_csv(filepath, index=False)
    logging.info(f"Dataframe for {date_str} stored in {filepath}")


def get_parser_args(args):
    # Gets arguments for extractions from args parser.
    start = args.starting_date
    end = args.ending_date
    amount = args.amount
    return start, end, amount


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
    # Get citations
    if not metadata_df.empty:
        citations_df = get_citations(
            metadata_df, os.getenv("LIDO_USERNAME"), os.getenv("LIDO_PASSWORD"), 1
        )
        citations_df.to_csv(citation_file, index=False)
    else:
        pd.DataFrame().to_csv(citation_file, index=False)
    return {"base": base_file, "metadata": metadata_file, "citations": citation_file}


if __name__ == "__main__":
    # giving arguments to the function
    rechtspraak_extract()
