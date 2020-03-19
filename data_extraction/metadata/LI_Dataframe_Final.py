
# coding: utf-8

# In[1]:


import requests 
import json

import os
import pandas as pd
import numpy as np
import math
import re
import time


# In[2]:


#legal intelligence credentials
CLIENT_ID = 'm.meyers@maastrichtuniversity.nl'
CLIENT_SECRET = '0def3e99-2fbf-482c-8695-634c56d48739'


# # Methods needed for using the LI API

# In[3]:


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

    request = requests.post('https://api.legalintelligence.com/token', data=data, headers=headers)
    #print('Auth status code: %s' %request.status_code)

    response = request.json()
    #print('Auth access code: %s' %response['access_token'])
    
    return response['access_token']


# In[4]:


def get_search_query(query, filters=[]):
    headers = {    
        "x-subsitecode": "LI",    
        "authorization": "Bearer %s" %get_access_token(),    
        "accept": "application/json"  
    }
    params = {
        "start" :  0,
        "rows" : 40
    }
   
    link = 'https://api.legalintelligence.com/search?q=%s'%query
    for filter in filters:
        link += '&fq=%s' %filter
#     link += '&fq='.join(filters)
    
    request = requests.get(link, headers=headers, params = params)
    
    
    #total number of cases retrieved by the given query
    count = request.json()["Count"]
    print("case count : "+str(count))
    
    #because we are using 40 as the number of cases retrieved at a time by Legal Intelligence (see params), 
    #this is the total number of iterations we will have tot loop through in order to retrieve all cases
    nb_pages = math.ceil(count/40)
    print('number of pages : '+str(nb_pages))
    
    page_index = 1
    pages = list()

    #append the first request to the list of request dictionaries
    pages.append(request.json())
    
    
    #go through all pages, and add each dictionary request to the list until no more pages
    while page_index < nb_pages: 
        print('page index : '+str(page_index))
        params = {
            "start" :  page_index,
            "rows" : 40
        }
        #we put the computer to sleep every 50 requests, to avoid the API limit to be exceeded
        if (page_index/50).is_integer():
            print('put computer to sleep, it has been 50 request')
            time.sleep(70)
            request = requests.get(link, headers=headers, params = params)
            pages.append(request.json())
            page_index = page_index + 1
        else:
            request = requests.get(link, headers=headers, params = params)
            #here I am unsure what the error exactly is... so for now I just excluse it as an exception
            try:
                pages.append(request.json())
            except:
                print('weird error')
                #print(request.json())
            page_index = page_index + 1  

  
    total_search_results = pages[0]
    counter = 0 
    for page in pages[1:]:
        print('page count : '+str(counter))
        counter = counter +1
        print('page type : '+str(type(page)))
        if isinstance(page, str):
            print('ERROR : page is a string, and not a dictionary')
            print(page)
        else:
            #only take the Documents sections of each page, and add it to a general Documents section
            #such that it looks like a big list of a cases and not list of json files
            total_search_results['Documents'] = total_search_results['Documents'] + page['Documents']
        
    return total_search_results


# Now, in order to be able to merge informations from Rechtspraak and Legal Intelligence, we need to match the corresponding cases. To do this, we will use the ECLI number. However, this number is not present in the json format output by Legal Intelligence, but it is present in the request.text format that we can also have from our query. 

# In[5]:


#retrieve the document based on its id
def get_document(id):
    headers = {    
        "x-subsitecode": "LI",    
        "authorization": "Bearer %s" %get_access_token(),    
        "accept": "application/json"  
    }

    request = requests.get('https://api.legalintelligence.com/documents/%s' %id, headers=headers)
    
    return request.text


# In[6]:


#this method takes the case text as an argument, searches for teh ecli number and outputs it. 
def getECLInumber(caseText):
    ecliStart = caseText.find('ECLI')
    #since there are maximum 25 characers in an ECLI number, we can just take that whole chunk. It makes things faster
    #than if we were to split the whole text
    caseText = caseText[ecliStart:ecliStart+25]
    #print('print 25 after ECLI : '+str(caseText))
    ecliNumber = caseText.split('<')[0]
    ecliNumber = ecliNumber.split(' ')[0]
    ecliNumber = ecliNumber.split(',')[0]
    ecliNumber = ecliNumber.replace(':','_')
    
    return ecliNumber 


# In[7]:


def saveTextToArchive(year, ecliNumber, caseText, save_path):
    print('saving case as html file')
    
    #replace with where the location of the Rechspraak Archive
    save_path_html = save_path+"/"+ecliNumber+".html"
    
    file = open(save_path_html, "w", encoding="utf-8")
    file.write(caseText)
    file.close()


# In[8]:


def saveJsonToArchive(year, ecliNumber, json_file):
    print('saving case as a json file')
    
    #replace with where the location of the Rechspraak Archive
    save_path_json = "C:/Users/mario/Documents/LawTechLab/Comenius/Archive/"+str(year)+"/"+ecliNumber+".json"
    path_xml = "C:/Users/mario/Documents/LawTechLab/Comenius/Archive/"+str(year)+"/"+ecliNumber+".xml"

    #see if LI case is new or already in the archive
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


#This method takes a certain year, the path where the LI cases are located as json files as parameters. 
#It outputs a pandas dataframe of all LI cases of a certain year
#It also saves an html file for each case in order to later be able to retrieve the full text from it

def createLIDataframe(year_dump, save_path, id_list, json_files): 
    #save_path = "C:/Users/mario/Documents/LawTechLab/legal-intelligence-api/notebooks/legalIntelDumpsSmall/"
    #get the id list of the case files of all LI cases found for that year
    #id_list, json_files = getIdListAndJsonFromYearDump(save_path+year+'.json')
    
    LI_df = pd.DataFrame()
    count_id = 0 
    #go through each of the cases
    for index, case_id in enumerate(id_list):
        print("index : "+str(index))
        count_id = count_id+1
        #put the computer to sleep every 50 cases to avoid exceeding the API limit
        #if (count_id/15).is_integer():
         #   print('put computer to sleep, it has been 15 request')
          #  time.sleep(1)
        
        print("case_id : "+str(case_id))
        try: 
            casetext = get_document(case_id)
       
        except Exception as e:
            print(e)
            print("weird error")
            time.sleep(20)
            casetext = get_document(case_id)
            
    #get the json file for the case  
        json_file = json_files[index]
        #get the year number
        year = year_dump[0:4]

        #get the ECLI number from the case, and check if it is valid
        ecliNumber = getECLInumber(casetext)
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:]') 
        #if the ecli number doesn't contain any of the weird characters above, and is not empty, then it is valid. 
        if(regex.search(ecliNumber) == None and ecliNumber !=''): 
            #print("valid ecli number : "+str(ecliNumber)) 

            #convert json file to a panda dataframe
            law_area_list = [json_file['LawArea']]
            #print('law area list size : '+str(len(law_area_list)))

            #print(str(type(json_file['LawArea'])))
            del json_file['LawArea']
            #print('json file type : '+str(type(json_file)))
            db = pd.DataFrame(json_file)
            db = db.rename(columns={"PublicationDate": "date", "CaseNumber": "case_number", "Summary":"abstract", "EnactmentDate":"lodge_date", "IssuingInstitution":"authority"})
            #print('database size : '+str(db.shape))
            if db.shape[0] >1:
                db= db.drop(db.index[1:])
            #print('database columns : '+str(db.columns))
            #print(db.head())
            db['LawArea'] = law_area_list
            db['ecli'] = ecliNumber
            #merge this dataframe with the overall one
            LI_df = pd.concat([LI_df, db], axis=0, ignore_index=True)

            #save the case as html file such that we can retrieve the full text from it later on 
            saveTextToArchive(year, ecliNumber, casetext, save_path+'/'+str(year))


        else: 
            print("ERROR : not a correct ECLI number : we don't add the document for now "+str(ecliNumber))
          
    #re-arrange dataframe such that the ecli number is at the front
    cols = LI_df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    LI_df = LI_df[cols] 
    
    print(LI_df.head())
    return LI_df


# # Main Method

# In[30]:


#list of years we want to retrieve LI cases for
years = list(range(1913, 2000))
#where we want to store the csv files as well as the individual html docs
save_path = "../../data/cases"
svae_path_large_file = "../../data/"
total_LI_df = pd.DataFrame()

for year in years:
    #time.sleep(70)
    print(year)
    
    #get all cases from LI for that year
    search_results = get_search_query(str(year),['Jurisdiction_HF%3A1%7C010_Nederland%7C010_Rechtspraak'])
    
    #code to save them as json files
    with open(save_path+'/'+str(year)+'.json', 'w') as fp:
        json.dump(search_results, fp)
   
    #get ids and case_json from the dump
    ids = [document["Id"] for document in search_results["Documents"]]
    json_files = search_results["Documents"]
    
    #create dataframe
    #os.mkdir(save_path+'/'+str(year)+'/')
    LI_df = createLIDataframe(str(year), save_path, ids, json_files)
    total_LI_df = total_LI_df.append(LI_df, ignore_index=True)
    LI_df.to_csv(save_path+'/'+str(year)+'/'+str(year)+'.csv')
    #print(total_LI_df.head())
    print('total shape : '+str(total_LI_df.shape))
    #print('column names : '+str(total_LI_df.columns))
total_LI_df.to_csv(save_path+'legal_intelligence_cases.csv')
    


# In[23]:

