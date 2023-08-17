"""
Main ECHR extraction routine. Used by the echr_extraction DAG.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from os.path import dirname, abspath
from os import getenv
import echr_extractor as echr
from airflow.models.variable import Variable
from dotenv import load_dotenv, find_dotenv

from definitions.storage_handler import Storage, get_path_raw, \
    CSV_ECHR_CASES, JSON_FULL_TEXT_ECHR, TXT_ECHR_EDGES, TXT_ECHR_NODES

env_file = find_dotenv()
load_dotenv(env_file, override=True)
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import pandas as pd

def echr_extract(args):
    # set up the output path

    output_path = get_path_raw(CSV_ECHR_CASES)

    # set up script arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-id', help='id of the first case to be downloaded', type=int, required=False, default=0)
    parser.add_argument('--end-id', help='id of the last case to be downloaded', type=int, required=False, default=None)
    parser.add_argument('--count', help='The number of cases to be downloaded, starting from the start_id. '
                                        'WARNING:If count is provided, the end_id will be set to start_id+count, '
                                        'overwriting any given end_id value.',
                        type=int, required=False, default=None)
    parser.add_argument('--start-date', help='Last modification date to look forward from', required=False,
                        default=None)
    parser.add_argument('--end-date', help='Last modification date to look back from', required=False, default=None)
    parser.add_argument('--skip-missing-dates', help='This option makes the extraction not collect data for\
                         cases where there is no judgement date provided.', type=bool, default=False, required=False)
    parser.add_argument('--fields', help='The fields to be extracted', required=False)
    parser.add_argument('--fresh', help='Flag for running a complete download regardless of existing downloads',
                        action='store_true')
    parser.add_argument('--language', nargs='+', help='The languages to be extracted',
                        required=False, default=["ENG", "FRE"])

    args, unknown = parser.parse_known_args(args)
    print('args')
    print(args)
    print('unknown')
    print(unknown)
    # set up locations
    print('\n--- PREPARATION ---\n')
    print('OUTPUT:\t\t\t', output_path)

    # set up storage handler
    storage = Storage()
    try:
        # Now Storage will throw an exception when the output_path is occupied
        # to make sure airflow doesn't crash it needs to be caught
        # This way the pipeline goes to the next steps of transformation and extraction, hopefully
        # eventually dealing with the already-existing output file
        storage.setup_pipeline(output_paths=[output_path])
        pass
    except Exception as e:
        print(e)
        return
    try:
        # Getting date of last update from airflow database
        last_updated = Variable.get('ECHR_LAST_DATE')
    except:
        last_updated = getenv('ECHR_START_DATE')
        Variable.set(key='ECHR_LAST_DATE', value=last_updated)

    today_date = str(datetime.today().date())
    print('\nSTART DATE (LAST UPDATE):\t', last_updated)

    print('\n--- START ---')
    start = time.time()

    print("--- Extract ECHR data")
    kwargs = {
        'start_id': args.start_id,
        'end_id': args.end_id,
        'count': args.count,
        'fields': args.fields,
        'language': args.language

    }
    print(kwargs)
    print(f"Downloading {args.count if 'count' in args and args.count is not None else 'all'} ECHR documents")
    if args.fresh:
        metadata, full_text = echr.get_echr_extra(**kwargs, start_date="1990-01-01", save_file="n")

    elif args.start_date and args.end_date:
        print(f'Starting from manually specified date: {args.start_date} and ending at end date: {args.end_date}')
        metadata, full_text = echr.get_echr_extra(**kwargs, start_date=args.start_date,end_date=args.end_date, save_file="n")
    elif args.start_date:
        print(f'Starting from manually specified date: {args.start_date}')
        metadata, full_text = echr.get_echr_extra(**kwargs, start_date=args.start_date,
                                                  save_file="n")
    elif args.end_date:
        print(f'Ending at manually specified end date {args.end_date}')
        metadata, full_text = echr.get_echr_extra(**kwargs,  end_date=args.end_date,
                                                  save_file="n")
    else:
        print('Starting from the last update the script can find')
        metadata, full_text = echr.get_echr_extra(**kwargs, start_date=last_updated,
                                                  end_date=today_date, save_file="n")


    print("--- saving ECHR data")
    df_filepath = get_path_raw(CSV_ECHR_CASES)
    if metadata is not False:
        metadata.to_csv(df_filepath, index=False)
        json_filepath = JSON_FULL_TEXT_ECHR
        with open(json_filepath, 'w') as f:
            json.dump(full_text, f)
        print("Adding Nodes and Edges lists to storage")
        # Getting nodes and edges, citation-based. For creating a citation graph
        nodes, edges = echr.get_nodes_edges(dataframe=metadata, save_file="n")
        # get only the ecli column in nodes
        nodes = nodes[['ecli']]

        # df_nodes_path = get_path_raw(CSV_ECHR_CASES_NODES)
        # df_edges_path = get_path_raw(CSV_ECHR_CASES_EDGES)
        nodes_txt = get_path_raw(TXT_ECHR_NODES)
        edges_txt = get_path_raw(TXT_ECHR_EDGES)
         #nodes.to_csv(df_nodes_path, index=False)
        # edges.to_csv(df_edges_path, index=False)
        # save to text file from dataframe
        nodes.to_csv(nodes_txt, index=False, header=False, sep='\t')
        edges.to_csv(edges_txt, index=False, header=False, sep='\t')



    else:
        print("No ECHR data found")

    print(f"\nUpdating local storage ...")

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
    Variable.set(key='ECHR_LAST_DATE', value=today_date)


if __name__ == '__main__':
    # giving arguments to the funtion
    echr_extract(sys.argv[1:])
