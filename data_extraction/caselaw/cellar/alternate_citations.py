import json
from os.path import dirname, abspath, basename, join
from os import getenv
import csv
import sys
import glob

from io import StringIO
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import urllib.request
import time
from datetime import datetime
from definitions.storage_handler import CELLAR_DIR, Storage, DIR_DATA_PROCESSED
import argparse
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
from SPARQLWrapper import SPARQLWrapper, JSON, POST,CSV
from os.path import exists

start = time.time()

def get_citations_csv(celex):
    endpoint = 'https://publications.europa.eu/webapi/rdf/sparql'
    input='", "'.join(celex)
    query = '''
           prefix cdm: <http://publications.europa.eu/ontology/cdm#>
 prefix xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT DISTINCT * WHERE
        {
        {
            SELECT ?celex ?citedD WHERE {
                ?doc cdm:resource_legal_id_celex ?celex
                 FILTER(STR(?celex) in ("%s")).
                ?doc cdm:work_cites_work{1,1} ?cited .
                ?cited cdm:resource_legal_id_celex ?citedD .
            }
        } UNION {
            SELECT ?celex ?citedD WHERE {
                ?doc cdm:resource_legal_id_celex ?celex
                 FILTER(STR(?celex) in ("%s")).
                ?cited cdm:work_cites_work{1,1} ?doc .
                ?cited cdm:resource_legal_id_celex ?citedD .
            }
        }
}
       ''' % (input,input)

    sparql = SPARQLWrapper(endpoint)

    sparql.setReturnFormat(CSV)
    sparql.setMethod(POST)
    sparql.setQuery(query)
    ret = sparql.queryAndConvert()
    return ret.decode("utf-8")
def read_csv(file_path):
    try:
        data = pd.read_csv(file_path, sep=",", encoding='utf-8')
        # print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)
if __name__ == '__main__':

    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    data=read_csv(csv_files[0])
    celex=data.loc[:, "CELEX IDENTIFIER"]
    celex[200] = "62017CJ0216"
    all_csv = list()
    at_once=200
    for i in range(0, len(celex), at_once):
        new_csv = get_citations_csv(celex[i:(i + at_once)])
        all_csv.append(new_csv)
    all_IO=list()
    for i in range(len(all_csv)):
        all_IO.append(StringIO(all_csv[i]))
    df = pd.concat(map(pd.read_csv,all_IO),ignore_index=True)
    function={'celex':'"_".join'}
    celexes=pd.unique(df.loc[:,'celex'])
    citations = pd.Series([],dtype='string')
    for celex in celexes:
        index=data[data['CELEX IDENTIFIER']==celex].index.values
        cited=df[df['celex']==celex].loc[:,"citedD"]
        string = "_".join(cited)
        print(index)
        print(string)
        try:
            citations[index[0]]=string
        except:
            b=2
    data.insert(1,"Citations",citations)
    b=2
