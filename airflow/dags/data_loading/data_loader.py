# %%
from os.path import dirname, abspath, basename
import sys
sys.path.append(dirname(dirname(abspath(__file__))))
import os
from csv import DictReader
import csv
from data_loading.row_processors.dynamodb import DynamoDBRowProcessor
from data_loading.row_processors.opensearch import OpenSearchRowProcessor
from data_loading.clients.dynamodb import DynamoDBClient
from data_loading.clients.opensearch import OpenSearchClient
from definitions.storage_handler import Storage, CSV_RS_CASES, CSV_LI_CASES, CSV_RS_OPINIONS, CSV_CASE_CITATIONS, \
    CSV_LEGISLATION_CITATIONS, get_path_processed, get_path_raw,CSV_CELLAR_CASES
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
        get_path_processed(CSV_LI_CASES),
        get_path_processed(CSV_CELLAR_CASES),

        get_path_raw(CSV_CASE_CITATIONS),
        get_path_raw(CSV_LEGISLATION_CITATIONS)
    ]

    # parse input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument(
        '-partial', '--partial',
        choices=['ddb', 'os'],
        help='load data only to either DynamoDB or OpenSearch, not both'
    )
    parser.add_argument(
        '-delete', '--delete',
        choices=['ddb', 'os'],
        help='delete content from DynamoDB table/OpenSearch index'
    )
    args = parser.parse_args(argv)
    storage = Storage(location=args.storage)
    print(f'INPUT/OUTPUT DATA STORAGE: {args.storage}')
    print('INPUT:\t\t\t\t', [basename(input_path) for input_path in input_paths])

    # set up clients
    if args.partial is not None:
        if args.partial != 'os':
            ddb_client = DynamoDBClient(os.getenv('DDB_TABLE_NAME'))
        if args.partial != 'ddb':
            os_client = OpenSearchClient(
                domain_name=os.getenv('OS_DOMAIN_NAME'),
                index_name=os.getenv('OS_INDEX_NAME'),
                instance_type='t3.small.search',
                instance_count=1,
                storage_size=40
            )
    else:
        ddb_client = DynamoDBClient(os.getenv('DDB_TABLE_NAME'))
        args.partial="ddb"

    if args.partial != 'os':
        ddb_client = DynamoDBClient(os.getenv('DDB_TABLE_NAME'))
    if args.partial != 'ddb':
        os_client = OpenSearchClient(
            domain_name=os.getenv('OS_DOMAIN_NAME'),
            index_name=os.getenv('OS_INDEX_NAME'),
            instance_type='t3.small.search',
            instance_count=1,
            storage_size=40
        )


    # evaluate input arguments
    if args.delete == 'ddb':
        # remove all items from table without deleting table itself
        ddb_client.truncate_table()

    elif args.delete == 'os':
        # delete OpenSearch index
        os_client.es.indices.delete(os_client.index_name)

    else:
        # process each input csv
        for input_path in input_paths:
            broken=False
            try:
                with open(input_path, 'r', newline='') as in_file:
                    b = 2
            except:
                print(f"No such file found as {input_path}")
                broken=True
            if broken:
                continue

            # prepare storage
            print(f'\n--- PREPARATION {basename(input_path)} ---\n')
            storage.fetch_data([input_path])
            last_updated = storage.fetch_last_updated([input_path])
            print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())
            print(f'\n--- START {basename(input_path)} ---\n')
            print(f'Processing {basename(input_path)} ...')

            # initialize row processors and counters
            if args.partial != 'os':
                ddb_rp = DynamoDBRowProcessor(input_path, ddb_client.table)
            if args.partial != 'ddb':
                os_rp = OpenSearchRowProcessor(input_path, os_client)
            case_counter = 0
            ddb_item_counter = 0
            os_item_counter = 0

            # process csv by row
            with open(input_path, 'r', newline='',encoding="utf8") as in_file:
                reader = DictReader(in_file)
                for row in reader:
                     # skip empty rows and remove empty attributes
                     if row != '':

                        atts = list(row.items())
                        for att in atts:
                            if att[1] == '':
                                row.pop(att[0])

                        # process row
                        if args.partial != 'os':
                            ddb_item_counter += ddb_rp.upload_row(row)
                        if args.partial != 'ddb':
                            os_item_counter += os_rp.upload_row(row)

                    # log progress
                        case_counter += 1
                        if case_counter % 1000 == 0:
                            print(case_counter, 'rows processed.')

            if args.partial != 'ddb':
                os_client.es.indices.refresh(os_client.index_name)
            print(f'{case_counter} cases ({ddb_item_counter} ddb items and {os_item_counter} os items) added.')

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
    #table = ddb_client.table
    ##table.delete()
    #print(ddb_client.table.scan())
if __name__ == '__main__':
    load_data(sys.argv[1:])
