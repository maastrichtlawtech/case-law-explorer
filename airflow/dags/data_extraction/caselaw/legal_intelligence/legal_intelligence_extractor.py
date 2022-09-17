from os.path import dirname, abspath
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import requests
import os
import pandas as pd
import math
import time
from definitions.storage_handler import Storage, CSV_LI_CASES, get_path_raw, basename
from dotenv import load_dotenv
import argparse

load_dotenv()

# Legal intelligence credentials
LI_ENDPOINT = os.getenv("LI_ENDPOINT")
LI_CLIENT_ID = os.getenv("LI_CLIENT_ID")
LI_CLIENT_SECRET = os.getenv("LI_CLIENT_SECRET")

# Debug var
TEST = os.getenv('SAMPLE_TEST')


# # Methods needed for using the LI API
def get_access_token():
    data = {
     "grant_type": "client_credentials",
     "client_id": LI_CLIENT_ID,
     "client_secret": LI_CLIENT_SECRET
    }

    headers = {
     "Content-Type": "application/x-www-form-urlencoded",
     "X-SubSiteCode": "LI",
     "cache-control": "no-cache"
    }

    try:
        request = requests.post('https://api.legalintelligence.com/token', data=data, headers=headers)
        response = request.json()
        return response['access_token']
    except:
        print(f'NO AUTH CODE {request}')
    return None


def get_search_query(query, filters=None):
    if filters is None:
        filters = []
    start_minute = time.time()
    n_requests = 0
    headers = {    
        "x-subsitecode": "LI",    
        "authorization": "Bearer %s" % get_access_token(),
        "accept": "application/json"  
    }
    params = {
        "start": 0,
        "rows": 40
    }
    link = f'{LI_ENDPOINT}/search?q=%s' % query
    for f in filters:
        link += '&fq=%s' % f

    documents = []

    #try:
    initial_response = requests.get(link, headers=headers, params=params)
    #except:
    #    print(f'RETRIEVAL PAGE ${1} FAILED')

    n_requests += 1
    print(initial_response)
    # total number of cases retrieved by the given query
    count = initial_response.json()["Count"]
    print("case count : " + str(count))

    # because we are using 40 as the number of cases retrieved at a time by Legal Intelligence (see params),
    # this is the total number of iterations we will have tot loop through in order to retrieve all cases
    if TEST == "TRUE":
        nb_pages = 0
    else:
        nb_pages = math.ceil(count / 40)

    print('number of pages : ' + str(nb_pages))
    # append the first response to the list of response dictionaries
    documents += initial_response.json()['Documents']

    # go through all pages, and add each dictionary response to the list until no more pages
    for page_index in range(1, nb_pages + 1):
        params = {
            "start": page_index,
            "rows": 40
        }
        # we put the computer to sleep if we reached 100 requests below a minute, to avoid the API limit to be exceeded
        if n_requests == 100 and (time.time() - start_minute) < 60:
            print(f'put computer to sleep for {(time.time() - start_minute)}s, it has been 100 requests')
            time.sleep(60 - (time.time() - start_minute))
            start_minute = time.time()

        # here I am unsure what the error exactly is... so for now I just exclude it as an exception
        #try:
        response = requests.get(link, headers=headers, params=params)
        documents += response.json()['Documents']
        print(f'{page_index+1}/{nb_pages} pages retrieved. ({len(documents)}/{count} documents)')
        #except:
        #    print(f'RETRIEVAL PAGE ${page_index} FAILED')

    total_search_results = initial_response.json()
    total_search_results['Documents'] = documents

    return total_search_results


def select_entry(group):
    group_tmp = group[group['PublicationNumber'].notna()]
    # 1. priority: case published by "NJ":
    entry = group_tmp.loc[group_tmp['PublicationNumber'].str.startswith('NJ ')]

    # 2. priority (if no entry published by NJ): case published by "RvdW":
    if len(entry) == 0:
        entry = group_tmp.loc[group_tmp['PublicationNumber'].str.startswith('RvdW')]

    group_tmp = group[group['PublicationDate'].notna()]
    # 3. priority (if no entry published by RvDW): latest publication date
    if len(entry) == 0:
        entry = group_tmp.loc[group_tmp['PublicationDate'] == group_tmp['PublicationDate'].max()]

    group_tmp = group[group['DateAdded'].notna()]
    # 4. priority (if multiple entries have same publication date): latest date added to li
    if len(entry) > 1:
        entry = group_tmp.loc[group_tmp['DateAdded'] == group_tmp['DateAdded'].max()]

    # else (if multiple entries have same date added): take first entry
    if len(entry) > 1:
        entry = group.head(1)

    return entry


def get_ecli(case_number):
    elements = case_number.split(' ')
    for e in elements:
        if 'ECLI:' in e:
            return e
    return None

# # Main Method

start = time.time()

output_path = get_path_raw(CSV_LI_CASES)

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
args = parser.parse_args()
print('\n--- PREPARATION ---\n')
print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('OUTPUTS:\t\t\t', f'{basename(output_path)}\n')
storage = Storage(location=args.storage)
storage.setup_pipeline(output_paths=[output_path])
last_updated = storage.pipeline_last_updated
print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

print('\n--- START ---\n')

counter = 0
large_summaries = 0

# get all return documents for given ecli from LI
search_results = get_search_query('*', ['Jurisdiction_HF%3A2|010_Nederland|010_Rechtspraak|250_Uitspraak'])

df = pd.DataFrame(search_results['Documents'])
df.to_csv(output_path.split('.csv')[0] + '_unfiltered.csv', index=False)

# add ecli number for each document
df['ecli'] = df['CaseNumber'].apply(get_ecli)
# drop rows with no valid ecli
df.dropna(subset=['ecli'], inplace=True)
# drop irrelevant column and adjust data types
df.drop('UrlWithAutoLogOnToken', axis=1, inplace=True)
# drop duplicate entries
# convert all columns to type str (in case more attributes are added by LI inthe future)
df = df.loc[df.astype(str).drop_duplicates(set(df.columns) - {'Url'}).index]
#df.drop_duplicates(set(df.columns) - {'Url'}, inplace=True)

# group by ecli number, select most relevant entry
df = df.groupby('ecli').apply(select_entry).reset_index(drop=True)
df['PublicationDate'] = df['PublicationDate'].astype(int)
df['EnactmentDate'] = df['EnactmentDate'].astype(int)
df['DateAdded'] = df['DateAdded'].astype(int)

# save dataframe to csv (append to existing if applicable):
if not os.path.exists(output_path):
    header = True
else:
    header = False
df.to_csv(output_path, mode='a', index=False, header=header)

print(f'LI dataframe shape: {df.shape}')

print(f"\nUpdating {args.storage} storage ...")
storage.finish_pipeline()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
