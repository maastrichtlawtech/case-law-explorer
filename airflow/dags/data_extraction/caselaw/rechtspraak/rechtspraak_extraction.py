import rechtspraak_extractor as rex
from os.path import dirname, abspath
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import time
from datetime import datetime
from definitions.storage_handler import  Storage, get_path_raw, CSV_RS_CASES
import argparse
from dotenv import load_dotenv,find_dotenv
from airflow.models.variable import Variable
env_file=find_dotenv()
load_dotenv(env_file,override=True)

def rechtspraak_extract(args):
    output_path = get_path_raw(CSV_RS_CASES)
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument('--amount', help='number of documents to retrieve', type=int, required=False)
    parser.add_argument('--starting-date', help='Last modification date to look forward from', required=False)

    args = parser.parse_args(args)

    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', args.storage)
    print('OUTPUT:\t\t\t', output_path)
    storage = Storage(location=args.storage)
    storage.setup_pipeline(output_paths=[output_path])

    try:
        last_updated = Variable.get('RSPRAAK_LAST_DATE')
    except:
        last_updated = '1900-01-01'
        Variable.set(key='RSPRAAK_LAST_DATE', value=last_updated)


    today_date = str(datetime.today().date())
    print('\nSTART DATE (LAST UPDATE):\t', last_updated)
    print('\n--- START ---\n')
    start = time.time()
    print(f"Downloading {args.amount if 'amount' in args and args.amount is not None else 'all'} Rechtspraak documents")
    if args.amount is None:
        amount = 1000000
    else:
        amount = args.amount
    if args.starting_date:
        print(f'Starting from manually specified date: {args.starting_date}')
        df = rex.get_rechtspraak(max_ecli=amount,sd=args.starting_date,save_file='n')
        df_2 = rex.get_rechtspraak_metadata(save_file='n',dataframe=df)
    else:
        print('Starting from the last update the script can find')
        df = rex.get_rechtspraak(max_ecli=amount,sd=last_updated, save_file='n',ed=today_date)
        df_2 = rex.get_rechtspraak_metadata(save_file='n', dataframe=df)

    print(f"\nUpdating {args.storage} storage ...")
    df_filepath = get_path_raw(CSV_RS_CASES)
    df_2.to_csv(df_filepath, index=False)
    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
    Variable.set(key='RSPRAAK_LAST_DATE', value=today_date)

if __name__ == '__main__':
    # giving arguments to the funtion
    rechtspraak_extract(sys.argv[1:])