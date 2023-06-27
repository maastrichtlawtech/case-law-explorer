"""
Main cellar extraction routine. Used by the cellar_extraction DAG.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from os import getenv
from os.path import dirname, abspath

import cellar_extractor as cell
from airflow.models.variable import Variable
from dotenv import load_dotenv, find_dotenv

from definitions.storage_handler import Storage, get_path_raw, JSON_FULL_TEXT_CELLAR, \
    CSV_CELLAR_CASES, TXT_CELLAR_EDGES, TXT_CELLAR_NODES
from helpers.csv_manipulator import drop_columns

env_file = find_dotenv()
load_dotenv(env_file, override=True)
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))

WEBSERVICE_USERNAME = getenv('EURLEX_WEBSERVICE_USERNAME')
WEBSERVICE_PASSWORD = getenv('EURLEX_WEBSERVICE_PASSWORD')


def cellar_extract(args):
    """
    This function runs the cellar extraction!
    In case of airflow deployment, it will extract from the date of the last airflow cellar extraction time.
    Otherwise it will extract all documents from 1900, except if the user uses a starting-date argument.
    """
    output_path = get_path_raw(CSV_CELLAR_CASES)

    parser = argparse.ArgumentParser()
    parser.add_argument('--amount', help='number of documents to retrieve', type=int, required=False)
    parser.add_argument('--concurrent-docs', default=200, type=int,
                        help='default number of documents to retrieve concurrently', required=False)
    parser.add_argument('--starting-date', help='Last modification date to look forward from', required=False)
    parser.add_argument('--fresh', help='Flag for running a complete download regardless of existing downloads',
                        action='store_true')

    # Airflow gives extra arguments ( 'celery worker').
    # To make sure it doesn't crash the code, the unknown arg catching has to be added
    args, unknown = parser.parse_known_args(args)

    print('\n--- PREPARATION ---\n')
    print('OUTPUT:\t\t\t', output_path)
    storage = Storage()

    try:
        # Now Storage will throw an exception when the output_path is occupied
        # to make sure airflow doesn't crash it needs to be caught
        # This way the pipeline goes to the next steps of transformation and extraction, hopefully
        # eventually dealing with the already-existing output file
        storage.setup_pipeline(output_paths=[output_path])
    except Exception as e:
        print(e)
        return

    today_date = str(datetime.today().date())
    try:
        # Getting date of last update from airflow database
        last_updated = Variable.get('CELEX_LAST_DATE')
        print("database connection works")
    except:
        last_updated = '1900-01-01'
        # If doesn't exist, set to 1900-01-01,
        # internet didn't exist back then, so I don't think they could update the database
        Variable.set(key='CELEX_LAST_DATE', value=last_updated)

    print('\nSTART DATE (LAST UPDATE):\t', last_updated)
    print('\n--- START ---\n')
    start = time.time()
    print(f"Downloading {args.amount if 'amount' in args and args.amount is not None else 'all'} CELLAR documents")

    if args.amount is None:
        amount = 1000000
    else:
        amount = args.amount
    # Running the extraction, different options based on passed on arguments
    if args.fresh:
        metadata, full_text_json = cell.get_cellar_extra(save_file='n', max_ecli=amount, sd="1880-01-01", threads=15,
                                                         username=WEBSERVICE_USERNAME, password=WEBSERVICE_PASSWORD)
    elif args.starting_date:
        print(f'Starting from manually specified date: {args.starting_date}')
        metadata, full_text_json = cell.get_cellar_extra(save_file='n', max_ecli=amount, sd=args.starting_date,
                                                         threads=15,
                                                         username=WEBSERVICE_USERNAME, password=WEBSERVICE_PASSWORD)
    else:
        print('Starting from the last update the script can find')
        metadata, full_text_json = cell.get_cellar_extra(save_file='n', max_ecli=amount, sd=last_updated, ed=today_date,
                                                         threads=15,
                                                         username=WEBSERVICE_USERNAME, password=WEBSERVICE_PASSWORD)

    if isinstance(metadata, bool):
        # package returns False if no data was found
        sys.exit(0)
    print(f"\nUpdating local storage ...")

    # We are only interested in european cases.
    # Cellar extractor extracts everything with an ecli
    # Drop_columns makes sure we only keep what we are interested in from the download.
    drop_columns(metadata)

    # saving the metadata dataframe
    df_filepath = get_path_raw(CSV_CELLAR_CASES)
    metadata.to_csv(df_filepath, index=False)

    json_filepath = JSON_FULL_TEXT_CELLAR
    final_full_texts = []

    for jsons in full_text_json:
        # Additional check present below, to make sure we don't keep non-european, irrelevant (for us) cases
        celex = jsons.get('celex')
        if not celex.startswith("8"):
            final_full_texts.append(jsons)

    # Saving json file, containing the full text data
    with open(json_filepath, 'w') as f:
        json.dump(final_full_texts, f)

    # This method will get the lists of nodes and edges, based on citations
    # The lists will allow to create a citation graph
    nodes, edges = cell.get_nodes_and_edges_lists(metadata)
    if nodes is not False:
        nodes = '\n'.join(nodes)
        with open(get_path_raw(TXT_CELLAR_NODES), 'w') as f:
            f.write(nodes)
    else:
        print("No nodes found")
    if edges is not False:
        edges = '\n'.join(edges)
        with open(get_path_raw(TXT_CELLAR_EDGES), 'w') as f:
            f.write(edges)
    else:
        print("No edges found")

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
    # Settings the date of current download, as the start date of next download via airflow database
    Variable.set(key='CELEX_LAST_UPDATE', value=today_date)


if __name__ == '__main__':
    cellar_extract(sys.argv[1:])
