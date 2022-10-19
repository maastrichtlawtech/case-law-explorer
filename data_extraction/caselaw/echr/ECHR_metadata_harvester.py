import sys
import requests
import time
import argparse
import pandas as pd
from os.path import dirname, abspath
from socket import timeout

current_dir = dirname(dirname(abspath(__file__)))
correct_dir = ('\\').join(current_dir.replace('\\', '/').split('/')[:-2])
sys.path.append(correct_dir)
from definitions.storage_handler import Storage, CSV_ECHR_CASES
from definitions.mappings.attribute_name_maps import MAP_ECHR

# TODO find a better way to do this.....
class ContinueException(Exception): pass
def r_get_timeout(url, timeout, retry, verbose):
    returned = False
    count = 0

    while not returned:
        try:
            r = requests.get(url, timeout=timeout)
            returned = True
        except requests.exceptions.ReadTimeout:
            count += 1
            if verbose:
                print(f'Timeout!! Retry {count}...')
            if count > retry:
                raise ContinueException()
            else:
                pass

    return r
    
def read_echr_metadata(start_id=0, end_id=None, fields=None, verbose=True):
    """
    Read ECHR metadata into a Pandas DataFrame.
    :param start_id: result index to start search from
    :param end_id: result index to end search at (default None fetches all results)
    :param fields: list of meta attribute names to return (default None fetches all attributes)
    :param verbose: bool whether or not to print fetched URLs
    :return:
    """

    data = []
    fields = MAP_ECHR.keys()
    META_URL = 'http://hudoc.echr.coe.int/app/query/results' \
        '?query=(contentsitename=ECHR) AND ' \
               '(documentcollectionid2:"JUDGMENTS" OR documentcollectionid2:"COMMUNICATEDCASES") AND' \
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
    end_id = start_id + end_id

    if start_id+end_id > 500:  # HUDOC does not allow fetching more than 500 items at the same time
        for i in range(start_id, end_id, 500):
            print(" - Fetching information from cases {} to {}.".format(i, i+500))

            # Fromat URL based on the incremented index
            url = META_URL.format(select=','.join(fields), start=i, length=500)
            if verbose:
                print(url)
            r = requests.get(url)
            
            #try:
            #    r_get_timeout(url=url, timeout=10, retry=3, verbose=verbose)
            #except ContinueException:
            #    continue

            # try:
            #     r = requests.get(url, timeout=10)
            # except requests.exceptions.ReadTimeout:
            #     if verbose:
            #         print('Timeout... Retry')
            #     r = requests.get(url, timeout=10)

            # Get the results list
            temp_dict = r.json()['results']

            # Get every doc from the results list
            for result in temp_dict:
                data.append(result['columns'])
    else:
        # Format URL based on start and length
        url = META_URL.format(select=','.join(
            fields), start=start_id, length=end_id)
        if verbose:
            print(url)
        r = requests.get(url)

        # Get the results list
        temp_dict = r.json()['results']

        # Get every doc from the results list
        for result in temp_dict:
            data.append(result['columns'])

    return pd.DataFrame.from_records(data), resultcount


# set up script arguments
parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
parser.add_argument('--count', help='number of documents to retrieve', type=int, required=False)
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
df, resultcount = read_echr_metadata(end_id=arg_end_id, fields=['itemid', 'documentcollectionid2', 'languageisocode'], verbose=True)

print(f'ECHR data shape: {df.shape}')
print(f'Columns extracted: {list(df.columns)}')

print("--- Filter ECHR data")
df_eng = df.loc[df['languageisocode'] == 'ENG']

print(f'df before language filtering: {df.shape}')
print(f'df after language filtering: {df_eng.shape}')

print("--- Load ECHR data")

df.to_csv(CSV_ECHR_CASES)

print(f"\nUpdating {args.storage} storage ...")
storage.finish_pipeline()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

# Example python3 data_extraction/caselaw/echr/ECHR_metadata_harvester.py local --count=104  
# Avarage time for 35k cases: 00:04:50
# TODO manage aws
# TODO manage the last update