from os.path import dirname, abspath
from os import getenv
import sys
import json

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import time
from datetime import datetime
from definitions.storage_handler import Storage, get_path_raw, JSON_FULL_TEXT_CELLAR, \
    CSV_CELLAR_CASES
import argparse
from helpers.csv_manipulator import drop_columns
import cellar_extractor as cell
from dotenv import load_dotenv,find_dotenv,set_key


env_file=find_dotenv()
load_dotenv(env_file,override=True)
WEBSERVICE_USERNAME = getenv('EURLEX_WEBSERVICE_USERNAME')
WEBSERVICE_PASSWORD = getenv('EURLEX_WEBSERVICE_PASSWORD')


def cellar_extract(args):
    output_path = get_path_raw(CSV_CELLAR_CASES)
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument('--amount', help='number of documents to retrieve', type=int, required=False)
    parser.add_argument('--concurrent-docs', default=200, type=int,
                        help='default number of documents to retrieve concurrently', required=False)
    parser.add_argument('--starting-date', help='Last modification date to look forward from', required=False)

    parser.add_argument('--fresh', help='Flag for running a complete download regardless of existing downloads',
                        action='store_true')
    args = parser.parse_args(args)

    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', args.storage)
    print('OUTPUT:\t\t\t', output_path)
    storage = Storage(location=args.storage)
    storage.setup_pipeline(output_paths=[output_path])
    last_updated = getenv("CELEX_LAST_UPDATE")
    today_date = str(datetime.today().date())
    print('\nSTART DATE (LAST UPDATE):\t', last_updated)
    print('\n--- START ---\n')
    start = time.time()
    print(f"Downloading {args.amount if 'amount' in args and args.amount is not None else 'all'} CELLAR documents")
    if args.amount is None:
        amount = 1000000
    else:
        amount = args.amount
    if args.fresh:
        df, json_file = cell.get_cellar_extra(save_file='n', max_ecli=amount, sd="1880-01-01", threads=15,
                                              username=WEBSERVICE_USERNAME, password=WEBSERVICE_PASSWORD)
    elif args.starting_date:
        print(f'Starting from manually specified date: {args.starting_date}')
        df, json_file = cell.get_cellar_extra(save_file='n', max_ecli=amount, sd=args.starting_date, threads=15,
                                              username=WEBSERVICE_USERNAME, password=WEBSERVICE_PASSWORD)
    else:
        print('Starting from the last update the script can find')
        df, json_file = cell.get_cellar_extra(save_file='n', max_ecli=amount, sd=last_updated,ed=today_date, threads=15,
                                              username=WEBSERVICE_USERNAME, password=WEBSERVICE_PASSWORD)

    if df == False:
        sys.exit()
    print(f"\nUpdating {args.storage} storage ...")
    storage.finish_pipeline()
    drop_columns(df)
    df_filepath = get_path_raw(CSV_CELLAR_CASES)
    df.to_csv(df_filepath, index=False)
    json_filepath = get_path_raw(JSON_FULL_TEXT_CELLAR)
    final_jsons = []
    for jsons in json_file:
        celex = jsons.get('celex')
        if not celex.startswith("8"):
            final_jsons.append(jsons)
    with open(json_filepath, 'w') as f:
        json.dump(final_jsons, f)

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
    set_key(env_file,"CELEX_LAST_UPDATE",today_date)
if __name__ == '__main__':

    cellar_extract(sys.argv[1:])
