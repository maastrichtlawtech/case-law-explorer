import numpy as np
import pandas as pd
import re
import sys
import time
import dateutil.parser as parser    # for selecting by date
import datetime
import argparse
from os.path import dirname, abspath

current_dir = dirname(dirname(abspath(__file__)))
sys.path.append(current_dir)
from definitions.storage_handler import Storage, get_path_raw, CSV_ECHR_CASES, CSV_ECHR_CASES_NODES, CSV_ECHR_CASES_EDGES, JSON_ECHR_CASES_EDGES, JSON_ECHR_CASES_NODES

"""
todo: change lists into dictionary -> store dict as json file
"""

def open_metadata(filename_metadata):
    #todo: remove this method because it is redundant (keep for now to test)
    df = pd.read_csv('C:/Users/Chloe/PycharmProjects/case-law-explorer/data/echr/' + filename_metadata) # change hard coded path
    return df


def metadata_to_nodesedgeslist(df):
    """
    Returns a dataframe where column 'article' only contains a certain article

    param df: the complete dataframe from the metadata
    """
    df = df[df['article'].notna()]
    df = df[df.article.str.contains("P1")] # change to args -> need mapping between article names and format in column?
    return df


def retrieve_nodes_list(df):
    """
    todo: check if method is redundant (is it necessary to move ecli to first?)
    Returns a dataframe where 'ecli' is moved to the first column.

    param df: the dataframe after article filter
    """
    df = metadata_to_nodesedgeslist(df)
    col = df.pop("ecli")
    df.insert(1, col.name, col)
    df.drop(df.columns[0], axis=1, inplace=True)
    return df


def retrieve_edges_list(df, df_unfiltered):
    """
    Returns a dataframe consisting of 2 columns 'ecli1' and 'ecli2' which
    indicate a reference link between cases.

    params:
    df -- the node list extracted from the metadata
    df_unfiltered -- the complete dataframe from the metadata
    """
    edges = pd.DataFrame(columns=['ecli', 'references'])

    for index, item in df.iterrows():
        print(index)
        if item.scl is not np.nan:
            """
            Split the references from the scl column into a list of references.
            
            Example:
            references in string: "Ali v. Switzerland, 5 August 1998, § 32, Reports of Judgments and 
            Decisions 1998-V;Sevgi Erdogan v. Turkey (striking out), no. 28492/95, 29 April 2003"
            
            ["Ali v. Switzerland, 5 August 1998, § 32, Reports of Judgments and 
            Decisions 1998-V", "Sevgi Erdogan v. Turkey (striking out), no. 
            28492/95, 29 April 2003"]
            """
            newtext = item.scl.split(';')
            eclis = []

            for it in newtext:
                appnos = re.findall("[0-9]{4,5}\/[0-9]{2}", it)

                rows = lookup(appnos, it, df_unfiltered)

                for ind, itm in rows.iterrows():
                    if itm.ecli is not np.nan:
                        eclis.append(itm.ecli)
                        #print(itm.ecli)


            #for ec in eclis:
                #print(ec)
            edges = pd.concat(
                [edges, pd.DataFrame.from_records([{'ecli': item.ecli, 'references': eclis}])]) # improve?

        print("edges: \n", edges)
    return edges


def lookup(appnos, text, df):
    """ 
    Checks whether app numbers for cases were found. If so calls lookup_app_number
    otherwise use the casenames provided by calling lookup_casename.

    Returns the rows obtained from lookup_app_number and lookup_casename.
    """
    if len(appnos) > 0:
        rows = lookup_app_number(appnos, df)

        if rows.empty or rows.shape[0] > 1:
            rows = lookup_casename(text, df)

    else:
        rows = lookup_casename(text, df)
    return rows


def lookup_app_number(pattern, df): #change to app_number
    """
    Returns a list with rows containing the cases linked to the found app numbers.
    """
    #print(pattern)
    row = df.loc[df['appno'].isin(pattern)]
    #print(row)

    if row.empty:
        #print("empty!")
        return pd.DataFrame()
    elif row.shape[0] > 1:
        return row
    else:
        return row


def lookup_casename(text, df):
    """
    Process the reference for lookup in metadata.
    Returns the rows corresponding to the cases.

    - Example of the processing (2 variants) -

    Original reference from scl:
    - Hentrich v. France, 22 September 1994, § 42, Series A no. 296-A
    - Eur. Court H.R. James and Others judgment of 21 February 1986,
    Series A no. 98, p. 46, para. 81

    Split on ',' and take first item:
    Hentrich v. France
    Eur. Court H.R. James and Others judgment of 21 February 1986

    If certain pattern from CLEAN_REF in case name, then remove:
    Eur. Court H.R. James and Others judgment of 21 February 1986 -->
        James and Others

    Change name to upper case and add additional text to match metadata:
    Hentrich v. France --> CASE OF HENTRICH V. FRANCE
    James and Others --> CASE OF JAMES AND OTHERS
    """
    line = text.split(',')
    casename = line[0]

    f = open('CLEAN_REF.txt', 'r')
    patterns = f.read().splitlines()

    uptext = casename.upper()
    uptext = uptext.replace('V.', 'v.')

    for pattern in patterns:
        uptext = re.sub(pattern, '', uptext)

    uptext = re.sub(r'\[.*', "", uptext)
    uptext = uptext.strip()

    for l in line:
        #print(l)
        try:
            date = parser.parse(l, fuzzy=True)
            #print(date)
            date = date.strftime("%d/%m/%Y %H:%M:%S")
            break
        except:
            date = ''
    #print(date)

    #print(date)
    row = df[df['docname'].str.contains(uptext, regex=False, flags=re.IGNORECASE)]
    #print("row 1: \n", row)

    if row.shape[0] > 1:
        row_date = row[row['judgementdate'] == date]
        if row_date.shape[0] == 0 or row_date.shape[0] > 1:
            echr_date = line[-1].replace('ECHR ', 'ECHR:')
            echr_date = echr_date.strip()
            echr_date = re.sub('-.*', '', echr_date)
            #print(echr_date)
            row = row[row['ecli'].str.contains(echr_date, na=False, regex=False)]
        else:
            return row_date
        #print(row)

    return row


# ---- RUN ----
print('\n--- PREPARING DATAFRAME ---\n')
data = pd.read_csv(get_path_raw(CSV_ECHR_CASES))
#data = open_metadata(filename_metadata='ECHR_metadata.csv')

print('\n--- CREATING NODES LIST ---\n')
nodes = retrieve_nodes_list(data)
print(nodes)

print('\n--- START EDGES LIST ---\n')
start = time.time()

print('\n--- CREATING EDGES LIST ---\n')
edges = retrieve_edges_list(nodes, data)

print('\n--- CREATING CSV FILES ---\n')
nodes.to_csv(CSV_ECHR_CASES_NODES, index=False, encoding='utf-8')
edges.to_csv(CSV_ECHR_CASES_EDGES, index=False, encoding='utf-8')
nodes.to_json(JSON_ECHR_CASES_NODES, orient="records")
edges.to_json(JSON_ECHR_CASES_EDGES, orient="records")
#edges.to_json(r'C:/Users/Chloe/PycharmProjects/case-law-explorer/data/echr/ECHR_json.json ', orient="records")

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
