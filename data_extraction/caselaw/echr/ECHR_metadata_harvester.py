import sys
import requests
import time
import argparse
import pandas as pd
from os.path import dirname, abspath
from socket import timeout
import dateutil.parser

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

def read_echr_metadata(start_id=0, end_id=None, date=None, fields=None, verbose=True):
    """
    Read ECHR metadata into a Pandas DataFrame.
    :param start_id: integer index to start search from
    :param end_id: integer index to end search at where the default None fetches all results
    :param fields: list meta attribute names to return where the default None fetches all attributes
    :param verbose: boolean whether or not to print extra information
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
    # example url: "https://hudoc.echr.coe.int/app/query/results?query=(contentsitename=ECHR)%20AND%20(documentcollectionid2:%22JUDGMENTS%22%20OR%20documentcollectionid2:%22COMMUNICATEDCASES%22)&select=itemid,applicability,application,appno,article,conclusion,decisiondate,docname,documentcollectionid,%20documentcollectionid2,doctype,doctypebranch,ecli,externalsources,extractedappno,importance,introductiondate,%20isplaceholder,issue,judgementdate,kpdate,kpdateAsText,kpthesaurus,languageisocode,meetingnumber,%20originatingbody,publishedby,Rank,referencedate,reportdate,representedby,resolutiondate,%20resolutionnumber,respondent,respondentOrderEng,rulesofcourt,separateopinion,scl,sharepointid,typedescription,%20nonviolation,violation&sort=itemid%20Ascending&start=0&length=2"

    # get total number of results:
    url = META_URL.format(select=','.join(fields), start=0, length=1)
    r = requests.get(url)
    resultcount = r.json()['resultcount']

    print("available results: ", resultcount)

    if not end_id:
        end_id = resultcount
    end_id = start_id+end_id

    if not date:
        date = "22-02-1000"
    date = dateutil.parser.parse(date, dayfirst=True).date()

    print(f"Fetching {end_id} results and filtering for cases after {date}.", end_id, " results \
            and filtering for cases after ", date)

    timeout = 6
    retry = 3

    if start_id+end_id > 500:  # HUDOC does not allow fetching more than 500 items at the same time
        for i in range(start_id, end_id, 500):
            print(" - Fetching information from cases {} to {}.".format(i, i+500))

            # Fromat URL based on the incremented index
            url = META_URL.format(select=','.join(fields), start=i, length=500)
            if verbose:
                print(url)
            
            r = get_r(url, timeout, retry, verbose)

            if r is not None:
                # Get the results list
                temp_dict = r.json()['results']

                # Get every doc from the results list
                for result in temp_dict:
                    case_date = dateutil.parser.parse(result['columns']['judgementdate']).date()
                    if case_date <= date:
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

            # Get every doc from the results list
            for result in temp_dict:
                case_date = dateutil.parser.parse(result['columns']['judgementdate']).date()
                if case_date >= date:
                    data.append(result['columns'])

    print(f'{len(data)} results after filtering by date.')

    return pd.DataFrame.from_records(data), resultcount


# set up script arguments
parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
parser.add_argument('--count', help='How many cases to retreive. Some may not be saved due to \
    language and date filtering', type=int, required=False)
parser.add_argument('--date', help='DD-MM-YY. Save cases from after this date.', type=str, \
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
arg_end_id = args.count if args.count else None
date = args.date if args.date else None
df, resultcount = read_echr_metadata(end_id=arg_end_id, date=date, fields=['itemid', 'documentcollectionid2', \
                                                                           'languageisocode'], verbose=True)

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