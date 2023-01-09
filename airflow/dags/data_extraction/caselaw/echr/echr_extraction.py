import echr_extractor as echr
from os.path import dirname, abspath, join
from os import getenv
import sys
import json
import shutil

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import time, glob
from datetime import datetime
from definitions.storage_handler import DIR_ECHR, Storage,get_path_raw, \
    ECHR_ARCHIVE_DIR,CSV_ECHR_CASES,JSON_FULL_TEXT_ECHR
import argparse
from helpers.csv_manipulator import drop_columns
from dotenv import load_dotenv




def echr_extract(args):
    #set up the output path 
    run_date = datetime.now().isoformat(timespec='seconds')
    output_path = join(DIR_ECHR, run_date.replace(':', '_') + '.json')

    # set up script arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument('--start-id', help='id of the first case to be downloaded',type=int, required=False,default=0)
    parser.add_argument('--end-id', help='id of the last case to be downloaded',type=int, required=False,default=None)
    parser.add_argument('--count', help='The number of cases to be downloaded, starting from the start_id.\
                         WARNING:If count is provided, the end_id will be set to start_id+count, overwriting any given end_id value.',\
                         type=int, required=False, default=None)
    parser.add_argument('--start-date', help='Last modification date to look forward from', required=False,default=None)
    parser.add_argument('--end-date', help='Last modification date to look back from', required=False,default=None)
    parser.add_argument('--skip-missing-dates', help='This option makes the extraction not collect data for\
                         cases where there is no judgement date provided.',type=bool, default=False, required=False)
    parser.add_argument('--fields', help='The fields to be extracted', required=False)
    # parser.add_argument('--output-path', help='path to output file', required=False,default=output_path)
    parser.add_argument('--fresh', help='Flag for running a complete download regardless of existing downloads',
                        action='store_true')
    
    args = parser.parse_args(args)

    # set up locations
    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', args.storage)
    print('OUTPUT:\t\t\t', output_path)

    # set up storage handler
    storage = Storage(location=args.storage)
    storage.setup_pipeline(output_paths=[output_path])

    last_updated = storage.pipeline_last_updated
    print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

    print('\n--- START ---')
    start = time.time()
    
        
    print("--- Extract ECHR data")
    kwargs={
        'start_id': args.start_id,
        'end_id': args.end_id,
        'count': args.count,
        'skip_missing_dates': args.skip_missing_dates,
        'fields': args.fields,
        # 'start_date': args.start_date,
        'end_date': args.end_date

    }
    print(kwargs)
    # df = echr.get_echr_extra(**kwargs)
    print(f"Downloading {args.count if 'count' in args and args.count is not None else 'all'} ECHR documents")
    if args.count is None:
        kwargs['count'] = 1000000
    else:
        kwargs['count'] = args.count

    if args.fresh:
        df, json_file = echr.get_echr_extra(**kwargs, start_date="1990-01-01")
    elif args.start_date:
        print(f'Starting from manually specified date: {args.start_date}')
        df, json_file = echr.get_echr_extra(**kwargs, start_date=args.start_date)
    else:
        print('Starting from the last update the script can find')
        df, json_file = echr.get_echr_extra(**kwargs, start_date=last_updated.isoformat())
    
    json_files = (glob.glob(DIR_ECHR + "/" + "*.json"))
    if len(json_files) > 0:  # Have to first check if there already is a file or no
        source = json_files[0]
        outsource = source.replace(DIR_ECHR, ECHR_ARCHIVE_DIR)
        shutil.move(source, outsource)

    open(output_path, 'w')
    print(f"\nUpdating {args.storage} storage ...")
    storage.finish_pipeline()
    print("--- saving ECHR data")
    df_filepath = get_path_raw(CSV_ECHR_CASES)
    if df is not False:
        df.to_csv(df_filepath, index=False)
        json_filepath = get_path_raw(JSON_FULL_TEXT_ECHR)
        for json_file in json_files:
            print(json)
            break
        with open(json_filepath, 'w') as f:
            json.dump(json_file, f)
    else:
        print("No ECHR data found")
    

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))


if __name__ == '__main__':
    # giving arguments to the funtion
    echr_extract(sys.argv[1:])
