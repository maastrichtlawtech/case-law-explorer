import requests
import os
import pandas as pd
import math
import time
from definitions.storage_handler import CSV_LI_CASES, URL_LI_ENDPOINT
from dotenv import load_dotenv

load_dotenv()

start_script = time.time()

# Legal intelligence credentials
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


def get_search_query(query, filters=[]):
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
   
    link = f'{URL_LI_ENDPOINT}/search?q=%s' % query
    for filter in filters:
        link += '&fq=%s' % filter

    documents = []

    try:
        initial_response = requests.get(link, headers=headers, params=params)
    except:
        print(f'RETRIEVAL PAGE ${1} FAILED')

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
        try:
            response = requests.get(link, headers=headers, params=params)
            documents += response.json()['Documents']
            print('page index : ' + str(page_index) + ' retrieved. Number of documents: ' + len(documents))
        except:
            print(f'RETRIEVAL PAGE ${page_index} FAILED')

    total_search_results = initial_response.json()
    total_search_results['Documents'] = documents

    return total_search_results


def select_entry(group):
    # 1. priority: case published by "NJ":
    entry = group.loc[group['PublicationNumber'].str.startswith('NJ ')]

    # 2. priority (if no entry published by NJ): case published by "RvdW":
    if len(entry) == 0:
        entry = group.loc[group['PublicationNumber'].str.startswith('RvdW')]

    # 3. priority (if no entry published by RvDW): latest publication date
    if len(entry) == 0:
        entry = group.loc[group['PublicationDate'] == group['PublicationDate'].max()]

    # 4. priority (if multiple entries have same publication date): latest date added to li
    if len(entry) > 1:
        entry = group.loc[group['DateAdded'] == group['DateAdded'].max()]

    # else (if multiple entries have same date added): take first entry
    if len(entry) > 1:
        entry = group.head(1)

    return entry


def get_ecli(case_number):
    if 'ECLI:' in case_number:
        return 'ECLI:' + case_number.split('ECLI:')[1]
    else:
        return None

# # Main Method

# In[30]:
#eclis = pd.read_csv('data/case.csv', usecols=['ecli'])['ecli'].tolist()
#print(f"Processing {len(eclis)} eclis...")
counter = 0
large_summaries = 0

# get all return documents for given ecli from LI
search_results = get_search_query('*', ['Jurisdiction_HF%3A2|010_Nederland|010_Rechtspraak|250_Uitspraak'])

df = pd.DataFrame(search_results['Documents'])
df.to_csv('test.csv', index=False)

# add ecli number for each document
df['ecli'] = df['CaseNumber'].apply(get_ecli)
# drop rows with no valid ecli
df.dropna(subset=['ecli'], inplace=True)
# drop irrelevant column and adjust data types
df.drop('UrlWithAutoLogOnToken', axis=1, inplace=True)
#df['LawArea'] = df['LawArea'].astype(str)  # redundant
#df['Sources'] = df['Sources'].astype(str)  # redundant
# drop duplicate entries
# convert all columns to type str (in case more attributes are added by LI inthe future)
df = df.loc[df.astype(str).drop_duplicates(set(df.columns) - {'Url'}).index]
#df.drop_duplicates(set(df.columns) - {'Url'}, inplace=True)

# group by ecli number, select most relevant entry
df = df.groupby('ecli').apply(select_entry).reset_index(drop=True)
df['PublicationDate'] = df['PublicationDate'].astype(int)
df['EnactmentDate'] = df['EnactmentDate'].astype(int)
df['DateAdded'] = df['DateAdded'].astype(int)

    # # select correct return document: "NJ" is first choice, "RvdW" is second choice
    # document = None
    # if search_results['Count'] != 0:  # check if results found on LI for ecli
    #     for doc in search_results["Documents"]:
    #         if doc['PublicationNumber'].startswith('NJ') or (document is None and doc['PublicationNumber'].startswith('RvdW')):
    #             document = doc
    #
    # # append selected document to dataframe
    # if document is not None:
    #     if len(document['Summary']) > 252:  # check if summaries not truncated (can be removed)
    #         large_summaries += 1
    #     document['ecli'] = ecli
    #     df = df.append(document, ignore_index=True)
    #
    # counter += 1
    # if counter % 500 == 0:
    #     print(f"{counter}/{len(eclis)} eclis processed.")

# save dataframe to csv:
df.to_csv(CSV_LI_CASES, index=False)

#print(f'All {len(eclis)} eclis processed and saved to dataframe.')
print(f'LI dataframe shape: {df.shape}')

end_script = time.time()

print("Done!")
print("Time taken: ", (end_script - start_script), "s")

