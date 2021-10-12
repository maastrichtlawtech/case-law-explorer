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
    CSV_LEGISLATION_CITATIONS, get_path_processed, get_path_raw
import time
import argparse
csv.field_size_limit(sys.maxsize)

start = time.time()

input_paths = [
    get_path_processed(CSV_RS_CASES),
    #get_path_processed(CSV_RS_OPINIONS),
    #get_path_processed(CSV_LI_CASES),
    #get_path_raw(CSV_CASE_CITATIONS),
    #get_path_raw(CSV_LEGISLATION_CITATIONS)
]

# parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    'storage',
    choices=['local', 'aws'],
    help='location to take input data from and save output data to'
)
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
args = parser.parse_args()
print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('INPUT:\t\t\t\t', [basename(input_path) for input_path in input_paths])

# set up clients
if args.partial != 'os':
    ddb_client = DynamoDBClient(os.getenv('DDB_TABLE_NAME'), args.storage)
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

        # prepare storage
        print(f'\n--- PREPARATION {basename(input_path)} ---\n')
        storage = Storage(location=args.storage)
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
        with open(input_path, 'r', newline='') as in_file:
            reader = DictReader(in_file)
            for row in reader:
                # skip empty rows and remove empty attributes
                if row != '' and case_counter >= 2871000:
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
