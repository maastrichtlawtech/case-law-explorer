import requests 
import json
import os
import pandas as pd
import numpy as np
import math
import re
import time
from terminology import *

# Import and load env vars, see .env
from dotenv import load_dotenv
load_dotenv()

# Legal intelligence credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


# # Methods needed for using the LI API

def get_access_token():
    data = {
     "grant_type": "client_credentials",
     "client_id": CLIENT_ID,
     "client_secret": CLIENT_SECRET
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
   
    link = 'https://api.legalintelligence.com/search?q=%s' % query
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
    nb_pages = math.ceil(count / 40)
    print('number of pages : ' + str(nb_pages))
    # append the first response to the list of response dictionaries
    documents += initial_response.json()['Documents']

    # go through all pages, and add each dictionary response to the list until no more pages
    for page_index in range(1, 400):  #, nb_pages + 1):
        print('page index : ' + str(page_index))
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

# Now, in order to be able to merge informations from Rechtspraak and Legal Intelligence,
# we need to match the corresponding cases. To do this, we will use the ECLI number.
# However, this number is not present in the json format output by Legal Intelligence,
# but it is present in the request.text format that we can also have from our query.

# ### DEPRECATED ### retrieve the document based on its doc_id
#def get_document(doc_id):
#    headers = {
#        "x-subsitecode": "LI",
#        "authorization": "Bearer %s" % get_access_token(),
#        "accept": "application/json"
#    }
#
#    try:
#        response = requests.get('https://api.legalintelligence.com/documents/%s' % doc_id, headers=headers)
#    except:
#        print(f'GET DOC ${doc_id} FAILED')
#
#    return response.text


# this method takes the case text as an argument, searches for teh ecli number and outputs it.
def get_ecli_number(case_text):
    ecli_start = case_text.find('ECLI')
    # since there are maximum 25 characers in an ECLI number, we can just take that whole chunk. It makes things faster
    # than if we were to split the whole text
    case_text = case_text[ecli_start:ecli_start + 25]
    #print('print 25 after ECLI : '+ str(case_text))
    ecli_number = case_text.split('<')[0]
    ecli_number = ecli_number.split(' ')[0]
    ecli_number = ecli_number.split(',')[0]
    ecli_number = ecli_number.replace(':', '_')
    
    return ecli_number


def save_text_to_archive(ecli_number, case_text, save_path):
    print('saving case as html file')
    
    # replace with where the location of the Rechspraak Archive
    save_path_html = save_path + "/" + ecli_number + ".html"
    
    file = open(save_path_html, "w", encoding="utf-8")
    file.write(case_text)
    file.close()


def save_json_to_archive(year, ecli_number, json_file):
    print('saving case as a json file')
    
    # replace with where the location of the Rechspraak Archive
    save_path_json = "C:/Users/mario/Documents/LawTechLab/Comenius/Archive/" + str(year) + "/" + ecli_number + ".json"
    path_xml = "C:/Users/mario/Documents/LawTechLab/Comenius/Archive/" + str(year) + "/" + ecli_number + ".xml"

    # see if LI case is new or already in the archive
    if os.path.isfile(path_xml):
        print("LI case existed in archive")
        with open(save_path_json, 'w') as fp:
            json.dump(json_file, fp)
        return True
    else: 
        print('new case found in LI')
        return False
    

# # Create the LI Dataframe

# In[29]:


# This method takes a certain year, the path where the LI cases are located as json files as parameters.
# It outputs a pandas dataframe of all LI cases of a certain year
# It also saves an html file for each case in order to later be able to retrieve the full text from it

def create_li_dataframe(year_dump, save_path, id_list, json_files):
    #save_path = "C:/Users/mario/Documents/LawTechLab/legal-intelligence-api/notebooks/legalIntelDumpsSmall/"
    # get the doc_id list of the case files of all LI cases found for that year
    #id_list, json_files = getIdListAndJsonFromYearDump(save_path+year+'.json')
    
    li_df = pd.DataFrame()
    count_id = 0
    # go through each of the cases
    for index, case_id in enumerate(id_list):
        print("index : "+str(index))
        count_id = count_id + 1
        # put the computer to sleep every 50 cases to avoid exceeding the API limit
        #if (count_id/15).is_integer():
         #   print('put computer to sleep, it has been 15 request')
          #  time.sleep(1)
        
        print("case_id : " + str(case_id))
        try: 
            case_text = get_document(case_id)
       
        except Exception as e:
            print(e)
            print("weird error")
            time.sleep(20)
            case_text = get_document(case_id)
            
    # get the json file for the case
        json_file = json_files[index]
        # get the year number
        year = year_dump[0:4]

        # get the ECLI number from the case, and check if it is valid
        ecli_number = get_ecli_number(case_text)
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:]')
        # if the ecli number doesn't contain any of the weird characters above, and is not empty, then it is valid.
        if regex.search(ecli_number) == None and ecli_number != '':
            #print("valid ecli number : "+str(ecli_number))

            # convert json file to a panda dataframe
            law_area_list = [json_file['LawArea']]
            #print('law area list size : '+str(len(law_area_list)))

            #print(str(type(json_file['LawArea'])))
            del json_file['LawArea']
            #print('json file type : '+str(type(json_file)))
            db = pd.DataFrame(json_file)
            db = db.rename(columns={"PublicationDate": "date",
                                    "CaseNumber": "case_number",
                                    "Summary": "abstract",
                                    "EnactmentDate": "lodge_date",
                                    "IssuingInstitution": "authority"})
            #print('database size : '+str(db.shape))
            if db.shape[0] > 1:
                db = db.drop(db.index[1:])
            #print('database columns : '+str(db.columns))
            #print(db.head())
            db['LawArea'] = law_area_list
            db['ecli'] = ecli_number
            # merge this dataframe with the overall one
            li_df = pd.concat([li_df, db], axis=0, ignore_index=True)

            # save the case as html file such that we can retrieve the full text from it later on
            save_text_to_archive(ecli_number, case_text, save_path + '/' + str(year))

        else: 
            print("ERROR : not a correct ECLI number : we don't add the document for now " + str(ecli_number))
          
    # re-arrange dataframe such that the ecli number is at the front
    cols = li_df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    li_df = li_df[cols]
    
    print(li_df.head())
    return li_df


# # Main Method

# In[30]:
# where we want to store the csv files as well as the individual html docs
save_path = "data/"
#eclis = pd.read_csv('data/case.csv', usecols=['ecli'])['ecli'].tolist()
#print(f"Processing {len(eclis)} eclis...")
counter = 0
large_summaries = 0

# get all return documents for given ecli from LI
search_results = get_search_query('*', ['Jurisdiction_HF%3A2|010_Nederland|010_Rechtspraak|250_Uitspraak'])

df = pd.DataFrame(search_results['Documents'])

# add ecli number for each document:
df['ecli'] = df['CaseNumber'].apply(lambda x: 'ECLI:' + x.split('ECLI:')[1])
df.drop('UrlWithAutoLogOnToken', axis=1, inplace=True)
df['LawArea'] = df['LawArea'].astype(str)
df['Sources'] = df['Sources'].astype(str)
df.drop_duplicates(set(df.columns) - {'Url'}, inplace=True)

# group by ecli number, select most relevant entry
df = df.groupby('ecli').apply(lambda group: select_entry(group)).reset_index(drop=True)


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

# rename column names:
# original column names can be found here: https://www.legalintelligence.com/files/li-search-endpoint.pdf
df.rename(columns={
    'ecli': LI_ECLI,
    'Id': LI_ID,
    'Title': LI_TITLE,
    'DisplayTitle': LI_DISPLAY_TITLE,
    'DisplaySubtitle': LI_DISPLAY_SUBTITLE,
    'Summary': LI_SUMMARY,
    'Url': LI_URL,
    'OriginalUrl': LI_ORIGINAL_URL,
    'Jurisdiction': LI_JURISDICTION,
    'DocumentType': LI_DOCUMENT_TYPE,
    'LawArea': LI_LAW_AREA,
    'IssuingInstitution': LI_ISSUING_INSTITUTION,
    'CaseNumber': LI_CASE_NUMBER,
    'PublicationNumber': LI_PUBLICATION_NUMBER,
    'IssueNumber': LI_ISSUE_NUMBER,
    'PublicationDate': LI_PUBLICATION_DATE,
    'EnactmentDate': LI_ENACTMENT_DATE,
    'DateAdded': LI_DATE_ADDED,
    'Sources': LI_SOURCES
})

# save dataframe to csv:
df.to_csv(save_path + 'legal_intelligence_cases.csv', index=False)

#print(f'All {len(eclis)} eclis processed and saved to dataframe.')
print(f'LI dataframe shape: {df.shape}')
#print(f'Number of summaries larger than 250 chars: {large_summaries}')
