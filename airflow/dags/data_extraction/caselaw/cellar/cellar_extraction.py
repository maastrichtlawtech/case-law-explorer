import json
from os.path import dirname, abspath, join
import sys
import shutil
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import time, glob
from datetime import datetime,timedelta
from definitions.storage_handler import CELLAR_DIR, Storage,CELLAR_ARCHIVE_DIR
import argparse
from helpers.sparql import get_all_eclis, get_raw_cellar_metadata
from cellar_text_extraction import transform_cellar

def cellar_extract(args):
    # set up storage location
    if "airflow" in args:
        run_date = (datetime.now()+timedelta(hours=2)).isoformat(timespec='seconds')
        output_path = join(CELLAR_DIR, run_date.replace(':', '_') + '.json')
        args.remove("airflow")
    else:
        # We set the filename to the current date/time for later reference if we want to incrementally build.
        run_date = datetime.now().isoformat(timespec='seconds')
        output_path = join(CELLAR_DIR, run_date.replace(':', '_') + '.json')

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
    last_updated = storage.pipeline_last_updated
    print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())
    print('\n--- START ---\n')
    start = time.time()
    print(f"Downloading {args.amount if 'amount' in args and args.amount is not None else 'all'} CELLAR documents")
    if args.fresh:
        print('Starting a fresh download')
        eclis = get_all_eclis()
    elif args.starting_date:
        print(f'Starting from manually specified date: {args.starting_date}')
        eclis = get_all_eclis(
            starting_date=args.starting_date
        )
    else:
        print('Starting from the last update the script can find')
        eclis = get_all_eclis(
            starting_date=last_updated.isoformat()
        )
    print(f"Found {len(eclis)} ECLIs")

    if args.amount:
        eclis = eclis[:args.amount]

    all_eclis = {}

    for i in range(0, len(eclis), args.concurrent_docs):
        new_eclis = get_raw_cellar_metadata(eclis[i:(i + args.concurrent_docs)])
        all_eclis = {**all_eclis, **new_eclis}

    json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))
    if len(json_files)>0: # Have to first check if there already is a file or no
        source=json_files[0]
        outsource=source.replace(CELLAR_DIR,CELLAR_ARCHIVE_DIR)
        shutil.move(source,outsource)

    with open(output_path, 'w') as f:
        json.dump(all_eclis, f)

    """ Code for getting individual ECLIs
    all_eclis = {}
    new_eclis = {}

    # Check if ECLI already exists
    print(f'Checking for duplicate ECLIs')
    duplicate = 0;
    temp_eclis = []
    for i in range(0, len(eclis)):
    	temp_path = join(CELLAR_DIR, eclis[i] + '.json')
    	if exists(temp_path):
    	    duplicate = 1
    	temp_eclis.append(eclis[i])


    if duplicate == 1:
    	print(f'Duplicate data found. Ignoring duplicate data.')
    else:
    	print(f'No duplicate data found.')

    if len(temp_eclis) > 0:
        for i in range(0, len(temp_eclis), args.concurrent_docs):
        	new_eclis = get_raw_cellar_metadata(temp_eclis[i:(i + args.concurrent_docs)])
        	# all_eclis = {**all_eclis, **new_eclis}
        	temp_path = join(CELLAR_DIR, temp_eclis[i] + '.json')

        	with open(temp_path, 'w') as f:
        		json.dump(new_eclis, f, indent=4)
        	new_eclis.clear()
    """
    print("Downloading full text and others...")
    if (transform_cellar(output_path, 15)):
        print("Additional extraction successful!")
    else:
        print("Something went wrong with the additional cellar extraction!")
    print(f"\nUpdating {args.storage} storage ...")
    storage.finish_pipeline()

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

if __name__ == '__main__':
    #giving arguments to the funtion
    cellar_extract(sys.argv[1:])
