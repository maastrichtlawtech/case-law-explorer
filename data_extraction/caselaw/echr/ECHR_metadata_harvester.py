import sys
import requests
import time
import argparse
import pandas as pd
import dateutil.parser
from datetime import datetime
from os.path import dirname, abspath
from socket import timeout

current_dir = dirname(dirname(abspath(__file__)))
correct_dir = ('\\').join(current_dir.replace('\\', '/').split('/')[:-2])
sys.path.append(correct_dir)
from definitions.storage_handler import Storage, CSV_ECHR_CASES
from definitions.mappings.attribute_name_maps import MAP_ECHR

def get_r(url, timeout, retry, verbose):
    """
    Get data from a URL. If this is uncuccessful it is attempted again up to a number of tries
    given by retry. If it is still unsuccessful the batch is skipped.
    :param url: string data source URL
    :param timeout: numerical time to wait for a response
    :param retry: integer number of times to retry upon failure
    :param verbose: boolean whether or not to print extra information
    """
    count = 0
    max_attempts = 20
    while count < max_attempts:
        try:
            r = requests.get(url, timeout=timeout)
            return r
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout):
            count += 1
            if verbose: 
                print(f"Timeout. Retry attempt {count}.")
            if count > retry:
                if verbose:
                    print(f"Unable to connect to {url}. Skipping this batch.")
                return None
    return None

def read_echr_metadata(start_id=0, end_id=None, start_datetime=None, end_datetime=None, verbose=True, skip_missing_dates=True):
    """
    Read ECHR metadata into a Pandas DataFrame.
    :param start_id: integer index to start search from
    :param end_id: integer index to end search at where the default None fetches all results
    :param start_datetime: datetime from which to save cases
    :param end_datetime: datetime before which to save cases
    :param fields: list meta attribute names to return where the default None fetches all attributes
    :param verbose: boolean whether or not to print extra information
    :param skip_missing_dates: boolean whether or not to save cases with missing dates
    """
    data = []
    fields = MAP_ECHR.keys()
    META_URL = 'http://hudoc.echr.coe.int/app/query/results' \
        '?query=(contentsitename=ECHR) AND ' \
               '(documentcollectionid2:"JUDGMENTS" OR \
                 documentcollectionid2:"COMMUNICATEDCASES") AND' \
               '(languageisocode:"ENG")' \
        '&select={select}' + \
        '&sort=itemid Ascending' + \
        '&start={start}&length={length}'

    META_URL = META_URL.replace(' ', '%20')
    META_URL = META_URL.replace('"', '%22')
    # An example url: "https://hudoc.echr.coe.int/app/query/results?query=(contentsitename=ECHR)%20AND%20(documentcollectionid2:%22JUDGMENTS%22%20OR%20documentcollectionid2:%22COMMUNICATEDCASES%22)&select=itemid,applicability,application,appno,article,conclusion,decisiondate,docname,documentcollectionid,%20documentcollectionid2,doctype,doctypebranch,ecli,externalsources,extractedappno,importance,introductiondate,%20isplaceholder,issue,judgementdate,kpdate,kpdateAsText,kpthesaurus,languageisocode,meetingnumber,%20originatingbody,publishedby,Rank,referencedate,reportdate,representedby,resolutiondate,%20resolutionnumber,respondent,respondentOrderEng,rulesofcourt,separateopinion,scl,sharepointid,typedescription,%20nonviolation,violation&sort=itemid%20Ascending&start=0&length=2".

    # get total number of results:
    url = META_URL.format(select=','.join(fields), start=0, length=1)
    r = requests.get(url)
    resultcount = r.json()['resultcount']
    print("available results: ", resultcount)
    if not end_id:
        end_id = resultcount
    end_id = start_id+end_id
    if not start_datetime:
        start_datetime = dateutil.parser.parse("01-01-1000 00:00:00", dayfirst=True)
    if not end_datetime:
        end_date = datetime.datetime.now()
    print(f'Fetching {end_id-start_id} results from index {start_id} to index {end_id} and \
          filtering for cases after {start_datetime} and before {end_datetime}.')
    timeout = 6
    retry = 3
    if start_id+end_id > 500:  # HUDOC does not allow fetching more than 500 items at the same time
        for i in range(start_id, end_id, 500):
            print(" - Fetching information from cases {} to {}.".format(i, i+500))

            # Format URL based on the incremented index.
            url = META_URL.format(select=','.join(fields), start=i, length=500)
            if verbose:
                print(url)

            # Get the response.
            r = get_r(url, timeout, retry, verbose)
            if r is not None:
                # Get the results list
                temp_dict = r.json()['results']
                # Get every document from the results list.
                for result in temp_dict:
                    try:
                        case_datetime = dateutil.parser.parse(result['columns']['judgementdate'], dayfirst=True)
                        if start_datetime <= case_datetime <= end_datetime:
                            data.append(result['columns'])
                    except dateutil.parser._parser.ParserError:
                        if not skip_missing_dates:
                            data.append(result['columns'])
    else:
        # Format URL based on start and length
        url = META_URL.format(select=','.join(fields), start=start_id, length=end_id)
        if verbose:
            print(url)

        r = get_r(url, timeout, retry, verbose)
        if r is not None:
            # Get the results list
            temp_dict = r.json()['results']

            # Get every document from the results list.
            for result in temp_dict:
                try:
                    case_datetime = dateutil.parser.parse(result['columns']['judgementdate'])
                    if start_datetime <= case_datetime <= end_datetime:
                        data.append(result['columns'])
                except dateutil.parser._parser.ParserError:
                    if not skip_missing_dates:
                        data.append(result['columns'])
    print(f'{len(data)} results after filtering by date.')
    return pd.DataFrame.from_records(data), resultcount


# set up script arguments
parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
parser.add_argument('--start_id', help='The index from which to start searching through cases.', \
                    type=int, required=False)
parser.add_argument('--count', help='How many cases to retreive. Some may not be saved due to \
                    language and date filtering', type=int, required=False)
parser.add_argument('--start_datetime', help='DD/MM/YYYY HH:MM:SS. Save cases from after this datetime.', type=str, \
                    required=False)
parser.add_argument('--end_datetime', help='DD-MM-YYYY HH:MM:SS. Save cases from before this datetime.', type=str, \
                    required=False)
args = parser.parse_args()

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
arg_start_id = args.start_id if args.start_id else 0
arg_end_id = args.count if args.count else None
try:
    arg_start_datetime = dateutil.parser.parse(args.start_datetime, dayfirst=True) if args.start_datetime else None
    arg_end_datetime = dateutil.parser.parse(args.end_datetime, dayfirst=True) if args.end_datetime else None
except dateutil.parser._parser.ParserError:
    print("The date formats are incorrect, they should be dd/mm/yyyy HH:MM:DD")
    sys.exit(2)
df, resultcount = read_echr_metadata(start_id=arg_start_id, end_id=arg_end_id, \
                                     start_datetime=arg_start_datetime, end_datetime=arg_end_datetime)
print(f'ECHR data shape: {df.shape}')
print(f'Columns extracted: {list(df.columns)}')
print("--- Load ECHR data")
df.to_csv(CSV_ECHR_CASES)
print(f"\nUpdating {args.storage} storage ...")
storage.finish_pipeline()
end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

# Example python3 data_extraction/caselaw/echr/ECHR_metadata_harvester.py local --count=104
# Avarage time for 35k cases: 00:04:50
