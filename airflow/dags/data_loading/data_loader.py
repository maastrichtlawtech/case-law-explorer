"""
Main data loader. Upload Cellar, ECHR and RS case metadata, full text, and
citation graph edges into Postgres (cle_v2 schema, issue #42).

"""

import csv
import os
import sys
import time
from csv import DictReader
from ctypes import c_long, sizeof
from os.path import abspath, basename, dirname

from data_loading.case_text_loader import load_fulltext
from data_loading.citation_graph_loader import load_citation_graph
from data_loading.clients.postgres import PostgresCLEClient
from data_loading.row_processors.postgres import (
    PostgresCelexProcessor,
    PostgresItemIdProcessor,
    PostgresRSProcessor,
)
from definitions.storage_handler import (
    CSV_CELLAR_CASES,
    CSV_ECHR_CASES,
    CSV_RS_CASES,
    JSON_FULL_TEXT_CELLAR,
    JSON_FULL_TEXT_ECHR,
    get_path_processed,
)
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
sys.path.append(dirname(dirname(abspath(__file__))))

signed = c_long(-1).value < c_long(0).value
bit_size = sizeof(c_long) * 8
signed_limit = 2 ** (bit_size - 1)
csv.field_size_limit(signed_limit - 1 if signed else 2 * signed_limit - 1)


def load_data(input_paths=None):
    start = time.time()
    if input_paths is None:
        input_paths = [
            get_path_processed(CSV_RS_CASES),
            get_path_processed(CSV_ECHR_CASES),
            get_path_processed(CSV_CELLAR_CASES),
        ]
    full_text_paths = [JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR]
    print("INPUT/OUTPUT DATA STORAGE FOR METADATA + FULL TEXT + CITATIONS: Postgres (cle_v2)")
    print("INPUT:\t\t\t\t", [basename(input_path) for input_path in input_paths])

    with PostgresCLEClient() as client:
        for input_path in input_paths:
            if not os.path.exists(input_path):
                print(f"FILE {input_path} DOES NOT EXIST")
                continue
            print(f"\n--- PREPARATION {basename(input_path)} ---\n")
            print(f"\n--- START {basename(input_path)} ---\n")
            print(f"Processing {input_path} ...")

            case_counter = 0
            row_counter = 0
            if get_path_processed(CSV_CELLAR_CASES) in input_path:
                row_processor = PostgresCelexProcessor(input_path, client)
            elif get_path_processed(CSV_ECHR_CASES) in input_path:
                row_processor = PostgresItemIdProcessor(input_path, client)
            else:
                row_processor = PostgresRSProcessor(input_path, client)

            with open(input_path, "r", newline="", encoding="utf8") as in_file:
                reader = DictReader(in_file)
                for row in tqdm(reader, desc="Processing rows", unit="rows"):
                    row_counter += row_processor.upload_row(row)
                    case_counter += 1

            print(f"{case_counter} cases processed ({row_counter} rows upserted).")

        load_fulltext(client, full_text_paths)
        load_citation_graph(client)
    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime("%H:%M:%S", time.gmtime(end - start)))


if __name__ == "__main__":
    load_data()
