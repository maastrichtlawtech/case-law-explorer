import echr_extractor as echr
from os.path import dirname, abspath, join
from os import getenv
import sys
import json
import shutil

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import time, glob
from datetime import datetime
from definitions.storage_handler import DIR_ECHR, Storage, \
    CSV_ECHR_CASES
import argparse
from helpers.csv_manipulator import drop_columns
from dotenv import load_dotenv




def echr_extract(args):
    # set up script arguments
    run_date = datetime.now().isoformat(timespec='seconds')
    output_path = join(DIR_ECHR, run_date.replace(':', '_') + '.json')
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument('--start-id', help='id of the first case to be downloaded',type=int, required=False,default=0)
    parser.add_argument('--end-id', help='id of the last case to be downloaded',type=int, required=False,default=None)
    parser.add_argument('--count', help='The number of cases to be downloaded, starting from the start_id.\
                         WARNING:If count is provided, the end_id will be set to start_id+count, overwriting any given end_id value.',\
                         type=int, required=False, default=None)
    parser.add_argument('--starting-date', help='Last modification date to look forward from', required=False,default=None)
    parser.add_argument('--ending-date', help='Last modification date to look back from', required=False,default=None)
    
    parser.add_argument('--ending-date', help='Last modification date to look back from', required=False)
    parser.add_argument('--skip-missing-dates', help='This option makes the extraction not collect data for\
                         cases where there is no judgement date provided.',type=bool, default=False, required=False)
    parser.add_argument('--fields', help='The fields to be extracted', required=False)

    parser.add_argument('--output-path', help='path to output file', required=False,default=output_path)
    args = parser.parse_args(args)

    # set up locations
    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', args.storage)
    print('OUTPUT:\t\t\t', CSV_ECHR_CASES)
    storage = Storage(location=args.storage)
    storage.setup_pipeline(output_paths=[CSV_ECHR_CASES])

    last_updated = storage.pipeline_last_updated
    print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

    print('\n--- START ---')
    start = time.time()

    print("--- Extract ECHR data")
    df = echr.get_echr_extra(start_id=args.start_id, end_id=args.end_id,
                             start_date=args.starting_date, count=args.count,
                             end_date=args.ending_date,
                             skip_missing_dates=True, fields=args.fields,
                             skip_missing_dates_only=args.skip_missing_dates,
                             save_file="n")

    print(f'ECHR data shape: {df.shape}')
    print(f'Columns extracted: {list(df.columns)}')

    print("--- Filter ECHR data")
    # df_eng = df.loc[df['languageisocode'] == 'ENG']

    # print(f'df before language filtering: {df.shape}')
    # print(f'df after language filtering: {df_eng.shape}')

    print("--- Load ECHR data")

    df.to_csv(CSV_ECHR_CASES)

    print(f"\nUpdating {args.storage} storage ...")
    storage.finish_pipeline()

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))


if __name__ == '__main__':
    # giving arguments to the funtion
    echr_extract(sys.argv[1:])
