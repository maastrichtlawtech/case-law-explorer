import glob, sys
from os.path import dirname, abspath
import pandas as pd
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_PROCESSED
from bs4 import BeautifulSoup
import requests
from selenium import webdriver

def read_csv(file_path):
    try:
        data = pd.read_csv(file_path,sep=",",encoding='utf-8')
        #print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)
def add_sections(data):
    name='CASE LAW BASED ON A LEGAL INSTRUMENT'
    links = data.loc[:,name]
    S1 = pd.Series([])
    addition="/DOC_1"
    for link in links:
        myLink="http://publications.europa.eu/resource/cellar/387e4da5-e292-496d-a9bc-c3ebface5413.0014.03/DOC_1"
        page=requests.get(myLink)
        print(page.text)
        # The link does not work, returns a rdf with tons of different links
        # you can add stuff like .0006.01/DOC_1 to make it work
        # But only to some of them, the number 6 here determines the language
        # sometimes 6 is english sometimes its 4 or 14
        # fun stuff
if __name__ == '__main__':
    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")
    for i in range(len(csv_files)):
        if ("Extracted" in csv_files[i]):
            print("")
            print(f"EXTRACTING FROM {csv_files[i]} ")
            data = read_csv(csv_files[i])
            add_sections(data)
            data.to_csv(csv_files[i].replace("With Citations","With Citations and Sections"), index=False)