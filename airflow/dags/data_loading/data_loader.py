# %%
from os.path import dirname, abspath, basename
import sys
sys.path.append(dirname(dirname(abspath(__file__))))
import os
from csv import DictReader
import csv, json
from data_loading.row_processors.dynamodb import DynamoDBRowProcessor,DynamoDBFullTextProcessor,DynamoDBRowCelexProcessor
from data_loading.row_processors.opensearch import OpenSearchRowProcessor
from data_loading.clients.dynamodb import DynamoDBClient
from data_loading.clients.opensearch import OpenSearchClient
from definitions.storage_handler import Storage, CSV_RS_CASES, CSV_LI_CASES, CSV_RS_OPINIONS, CSV_CASE_CITATIONS, \
    CSV_LEGISLATION_CITATIONS, get_path_processed, get_path_raw,CSV_CELLAR_CASES,CSV_ECHR_CASES, JSON_FULL_TEXT_CELLAR, \
    JSON_FULL_TEXT_ECHR
from fulltext_bucket_saving import upload_fulltext, bucket_name
import time
import argparse
from ctypes import c_long, sizeof
from dotenv import load_dotenv
load_dotenv()
#csv.field_size_l
# imit(sys.maxsize) #appears to be system dependent so is replaced with:
#from https://stackoverflow.com/questions/52475749/maximum-and-minimum-value-of-c-types-integers-from-python
signed = c_long(-1).value < c_long(0).value
bit_size = sizeof(c_long)*8
signed_limit = 2**(bit_size-1)
csv.field_size_limit(signed_limit-1 if signed else 2*signed_limit-1)


def load_data(argv):
    start = time.time()

    input_paths = [
        get_path_processed(CSV_RS_CASES),
        get_path_processed(CSV_RS_OPINIONS),
        get_path_processed(CSV_ECHR_CASES),
        get_path_processed(CSV_CELLAR_CASES)
    ]
    full_text_paths = [
        JSON_FULL_TEXT_CELLAR,
        JSON_FULL_TEXT_ECHR
    ]

    # parse input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument(
        '-delete', '--delete',
        choices=['ddb', 'os'],
        help='delete content from DynamoDB table'
    )
    args = parser.parse_args(argv)
    storage = Storage(location=args.storage)
    print(f'INPUT/OUTPUT DATA STORAGE FOR METADATA: {args.storage}')
    print('INPUT/OUTPUT DATA STORAGE FOR  FULL TEXT:\t',bucket_name)
  
    print('INPUT:\t\t\t\t', [basename(input_path) for input_path in input_paths])

    # set up clients
    ddb_client_ecli = DynamoDBClient(os.getenv('DDB_TABLE_NAME'))
    ddb_client_celex = DynamoDBClient(os.getenv('DDB_TABLE_NAME_CELEX'))
    ddb_full_text_client = DynamoDBClient(os.getenv('DDB_FULL_TEXT_TABLE_NAME'))


    # evaluate input arguments
    if args.delete == 'ddb':
        # remove all items from table without deleting table itself
        ddb_client_ecli.truncate_table()
        ddb_client_celex.truncate_table()
        ddb_full_text_client.truncate_table()
    else:
        # process each input csv
        for input_path in input_paths:
            if not os.path.exists(input_path):
                print(f"FILE {input_path} DOES NOT EXIST")
                continue

            # prepare storage
            print(f'\n--- PREPARATION {basename(input_path)} ---\n')
            storage.fetch_data([input_path])
            last_updated = storage.fetch_last_updated([input_path])
            print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())
            print(f'\n--- START {basename(input_path)} ---\n')
            print(f'Processing {basename(input_path)} ...')

            # initialize row processors and counters

            case_counter = 0
            ddb_item_counter = 0
            os_item_counter = 0
            if get_path_processed(CSV_CELLAR_CASES) in input_path:
                ddb_rp = DynamoDBRowCelexProcessor(input_path,ddb_client_celex.table)
            else:
                ddb_rp = DynamoDBRowProcessor(input_path,ddb_client_ecli.table)
            # process csv by row
            with open(input_path, 'r', newline='',encoding="utf8") as in_file:
                reader = DictReader(in_file)
                for row in reader:
                     # skip empty rows and remove empty attributes
                     if row != '':
                        # atts = list(row.items())
                        # for att in atts:
                            # if att[1] == '':
                            #     row.pop(att[0])
                        # process row
                        ddb_item_counter += ddb_rp.upload_row(row)

                    # log progress
                        case_counter += 1
                        if case_counter % 1000 == 0:
                            print(case_counter, 'rows processed.')

            print(f'{case_counter} cases ({ddb_item_counter} ddb items and {os_item_counter} os items) added.')
            if args.storage =="aws":
                os.remove(input_path)
        upload_fulltext(storage=args.storage,files_location_paths=full_text_paths)
    end = time.time()         # celex, item_id
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

if __name__ == '__main__':
    load_data(sys.argv[1:])