"""
Main data loader. Upload Cellar, ECHR and RS case metadata, full_text, nodes and edges onto the AWS storage.

"""
import csv
import os
import sys
import time
from csv import DictReader
from ctypes import c_long, sizeof
from os.path import dirname, abspath, basename

from dotenv import load_dotenv

from data_loading.clients.dynamodb import DynamoDBClient
from data_loading.fulltext_bucket_saving import upload_fulltext, bucket_name
from data_loading.nodes_and_edges_loader import upload_nodes_and_edges
from tqdm import tqdm
from data_loading.row_processors.dynamodb import DynamoDB_RS_Processor, \
    DynamoDBRowCelexProcessor, DynamoDBRowItemidProcessor
from definitions.storage_handler import CSV_RS_CASES, \
    get_path_processed, CSV_CELLAR_CASES, CSV_ECHR_CASES, \
    JSON_FULL_TEXT_CELLAR, \
    JSON_FULL_TEXT_ECHR

load_dotenv()
sys.path.append(dirname(dirname(abspath(__file__))))

# csv.field_size_l
# imit(sys.maxsize) #appears to be system dependent so is replaced with:
# from https://stackoverflow.com/questions/52475749/maximum-and-minimum-value-of-c-types-integers-from-python

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
            get_path_processed(CSV_CELLAR_CASES)
        ]
    full_text_paths = [
        JSON_FULL_TEXT_CELLAR,
        JSON_FULL_TEXT_ECHR
    ]
    print(f'INPUT/OUTPUT DATA STORAGE FOR METADATA: local')
    print('INPUT/OUTPUT DATA STORAGE FOR  FULL TEXT:\t', bucket_name)

    print('INPUT:\t\t\t\t', [basename(input_path) for input_path in input_paths])

    # set up clients
    ddb_client_ecli = DynamoDBClient(os.getenv('DDB_TABLE_NAME'))
    ddb_client_celex = DynamoDBClient(os.getenv('DDB_TABLE_NAME_CELEX'))
    ddb_client_echr = DynamoDBClient(os.getenv('DDB_NAME_ECHR'))

    # process each input csv
    for input_path in input_paths:
        if not os.path.exists(input_path):
            print(f"FILE {input_path} DOES NOT EXIST")
            continue
        # prepare storage
        print(f'\n--- PREPARATION {basename(input_path)} ---\n')
        print(f'\n--- START {basename(input_path)} ---\n')
        print(f'Processing {input_path} ...')

        # initialize row processors and counters

        case_counter = 0
        ddb_item_counter = 0
        os_item_counter = 0
        if get_path_processed(CSV_CELLAR_CASES) in input_path:
            ddb_rp = DynamoDBRowCelexProcessor(input_path, ddb_client_celex.table)
        elif get_path_processed(CSV_ECHR_CASES) in input_path:
            ddb_rp = DynamoDBRowItemidProcessor(input_path, ddb_client_echr.table)
        else:
            ddb_rp = DynamoDB_RS_Processor(input_path, ddb_client_ecli.table)
        # process csv by row
        with open(input_path, 'r', newline='', encoding="utf8") as in_file:
            reader = DictReader(in_file)
            for row in tqdm(
                reader, 
                desc="Processing rows", 
                unit="rows"
            ):
                ddb_item_counter += ddb_rp.upload_row(row)
                case_counter += 1

        print(f'{case_counter} cases ({ddb_item_counter} ddb items and {os_item_counter} os items) added.')
        # if os.path.exists(input_path):
        #     os.remove(input_path)
    upload_fulltext(storage='aws', files_location_paths=full_text_paths)
    upload_nodes_and_edges()
    end = time.time()  # celex, item_id
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))


if __name__ == '__main__':
    load_data()
