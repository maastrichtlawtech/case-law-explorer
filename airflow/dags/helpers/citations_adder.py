import glob
import sys
import threading
import time
from io import StringIO
from os.path import dirname, abspath

import pandas as pd

from definitions.storage_handler import DIR_DATA_PROCESSED
from helpers.json_to_csv import read_csv
from helpers.sparql import get_citations_csv, get_cited, get_citing

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
"""
Method used by separate threads for the multi-threading method of adding citations to the dataframe
Sends a query which returns a csv file containing the the celex identifiers of cited works for each case.
Works with multi-case queries, at_once is the variable deciding for how many cases are used with each query.
"""


def execute_citations(csv_list, citations):
    at_once = 1000
    for i in range(0, len(citations), at_once):
        new_csv = get_citations_csv(citations[i:(i + at_once)])
        csv_list.append(StringIO(new_csv))


"""
This method replaces replaces the column with citations.

Old column -> links to cited works
New column -> celex identifiers of cited works

It uses multithreading, which is very much recommended.
Uses a query to get the citations in a csv format from the endpoint. * 

* More details in the query method.
"""


def add_citations(data, threads):
    name = "WORK CITES WORK. CI / CJ"
    celex = data.loc[:, "CELEX IDENTIFIER"]

    length = celex.size
    if length > 100:  # to avoid getting problems with small files
        at_once_threads = int(length / threads)
    else:
        at_once_threads = length
    all_csv = list()
    threads = []
    for i in range(0, length, at_once_threads):
        curr_celex = celex[i:(i + at_once_threads)]
        t = threading.Thread(target=execute_citations, args=(all_csv, curr_celex))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    df = pd.concat(map(pd.read_csv, all_csv), ignore_index=True)
    celexes = pd.unique(df.loc[:, 'celex'])
    citations = pd.Series([], dtype='string')
    for celex in celexes:
        index = data[data['CELEX IDENTIFIER'] == celex].index.values
        cited = df[df['celex'] == celex].loc[:, "citedD"]
        string = ";".join(cited)
        citations[index[0]] = string
    data.pop(name)
    citations.sort_index(inplace=True)
    data.insert(1, name, citations)

"""
Method used by separate threads for the multi-threading method of adding citations to the dataframe
Sends a query which returns a csv file containing the the celex identifiers of cited works for each case.
Works with multi-case queries, at_once is the variable deciding for how many cases are used with each query.
"""


def execute_citations_separate(cited_list,citing_list, citations):
    at_once = 1000
    for i in range(0, len(citations), at_once):
        new_cited = get_cited(citations[i:(i + at_once)],1)
        new_citing = get_citing(citations[i:(i + at_once)],1)
        cited_list.append(StringIO(new_cited))
        citing_list.append(StringIO(new_citing))


"""
This method replaces replaces the column with citations.

Old column -> links to cited works
New column -> celex identifiers of cited works

It uses multithreading, which is very much recommended.
Uses a query to get the citations in a csv format from the endpoint. * 

* More details in the query method.
"""


def add_citations_separate(data, threads):
    celex = data.loc[:, "CELEX IDENTIFIER"]
    length = celex.size
    if length > 100:  # to avoid getting problems with small files
        at_once_threads = int(length / threads)
    else:
        at_once_threads = length
    cited_csv = list()
    citing_csv=list()
    threads = []

    for i in range(0, length, at_once_threads):
        curr_celex = celex[i:(i + at_once_threads)]
        t = threading.Thread(target=execute_citations_separate, args=(cited_csv,citing_csv, curr_celex))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    cited = pd.concat(map(pd.read_csv, cited_csv), ignore_index=True)
    citing = pd.concat(map(pd.read_csv, citing_csv), ignore_index=True)

    celexes = pd.unique(cited.loc[:, 'celex'])

    citing_df = pd.Series([], dtype='string')
    cited_df = pd.Series([], dtype='string')
    for cel in celexes:
        index = data[data['CELEX IDENTIFIER'] == cel].index.values

        cited_data = cited[cited['celex'] == celex].loc[:, "citedD"]
        citing_data = citing[citing['celex'] == celex].loc[:, "citedD"]

        string_cited = ";".join(cited_data)
        string_citing = ";".join(citing_data)

        citing_df[index[0]] = string_citing
        cited_df[index[0]] = string_cited

    citing_df.sort_index(inplace=True)
    cited_df.sort_index(inplace=True)

    data.insert(1, "citing", citing_df)
    data.insert(1, "cited_by", cited_df)
if __name__ == '__main__':

    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")
    for i in range(len(csv_files)):
        if "Extracted" not in csv_files[i]:
            print("")
            start: float = time.time()
            print(f"EXTRACTING FROM {csv_files[i]} ")
            data = read_csv(csv_files[i])
            add_citations(data, 10)
            end = time.time()
            print("\n--- DONE ---")
            print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
            data.to_csv(csv_files[i].replace("Extracted", "With Citations"), index=False)
