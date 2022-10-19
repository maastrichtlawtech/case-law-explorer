import numpy as np
import pandas as pd
import re
import sys
import time
import dateutil.parser as parser
import datetime
import argparse
import os
from os.path import dirname, abspath

current_dir = dirname(dirname(abspath(__file__)))
sys.path.append(current_dir)
from definitions.storage_handler import Storage, get_path_raw, CSV_ECHR_CASES, CSV_ECHR_CASES_NODES, CSV_ECHR_CASES_EDGES

def open_metadata(filename_metadata):
    df = pd.read_csv(get_path_raw(CSV_ECHR_CASES))
    return df

def metadata_to_nodesedgeslist(df):
    df = df[df['article'].notna()]
    df = df[df.article.str.contains("P1")]
    return df

def retrieve_nodes_list(df):
    df = metadata_to_nodesedgeslist(df)
    col = df.pop("ecli")
    df.insert(1, col.name, col)
    df.drop(df.columns[0], axis=1, inplace=True)
    return df
"""
def retrieve_edges_list(df, df_unfiltered):
    edges = pd.DataFrame(columns=['ecli1', 'ecli2'])
    for index, item in df.iterrows():
        print(index)
        if item.scl is not np.nan:
            newtext = item.scl.split(';')
            pattern = []
            eclis = []

            for it in newtext:
                line = it.split(',')
                casenames = line[0]
                dates = line[1]

                if 'Series A' in it:
                    ecli = lookup_casename(line[0], line[1].strip(), df_unfiltered)

                    if len(ecli) > 0:
                        eclis = eclis + ecli

                    else:
                        print("continue 1")

                    #ADD IF NO EDGES ARE REQUIRED
                    #else:
                    #    edges = pd.concat(
                    #        [edges, pd.DataFrame.from_records([{'ecli1': item.ecli, 'ecli2': ''}])])
                # POTENTIAL FIX FOR EMPTY ECLI2: create another if statement if Series A and pattern are not there
                else:
                    print('ahoy')
                    pattern = pattern + re.findall("[0-9]{4,5}\/[0-9]{2}", it)

            eclis_from_appno = lookup_appno(pattern, df_unfiltered)

            if len(eclis_from_appno) > 0:
                eclis = eclis + eclis_from_appno
            else:
                print("continue 2")

            if len(eclis) > 0:

                for ec in eclis:
                    print(ec)
                    edges = pd.concat(
                        [edges, pd.DataFrame.from_records([{'ecli1': item.ecli, 'ecli2': ec}])])

        print(edges)
    return edges
"""
def retrieve_edges_list(df, df_unfiltered):
    edges = pd.DataFrame(columns=['ecli1', 'ecli2'])
    for index, item in df.iterrows():
        print(index)
        if item.scl is not np.nan:
            newtext = item.scl.split(';')
            pattern = []
            eclis = []
            rows = pd.DataFrame()

            for it in newtext:
                line = it.split(',')
                appnos = re.findall("[0-9]{4,5}\/[0-9]{2}", it)


                rows = lookup(appnos, it, df_unfiltered)

                for ind, itm in rows.iterrows():
                    if itm.ecli is not np.nan:
                        eclis.append(itm.ecli)
                        print(itm.ecli)

            for ec in eclis:
                print(ec)
                edges = pd.concat(
                    [edges, pd.DataFrame.from_records([{'ecli1': item.ecli, 'ecli2': ec}])])

        print("edges: \n", edges)
    return edges

def lookup(appnos, text, df):
    if len(appnos) > 0:
        rows = lookup_appno(appnos, df)

        if rows.empty or rows.shape[0] > 1:
            rows = lookup_casename(text, df)

    else:
        rows = lookup_casename(text, df)
    return rows

##############################################################################################
def lookup_appno(pattern, df):
    print(pattern)
    row = df.loc[df['appno'].isin(pattern)]
    print(row)

    if row.empty:
        print("empty!")
        return pd.DataFrame()
    elif row.shape[0] > 1:
        return row
    else:
        return row


def lookup_casename(text, df):
    line = text.split(',')
    casename = line[0]

    uptext = casename.upper()
    uptext = uptext.replace('V.', 'v.')
    uptext = uptext.replace('EUR. COURT H.R.', '')
    uptext = re.sub('JUDGMENT OF.*', '', uptext)
    uptext = re.sub(r'\[.*', "", uptext)
    uptext = uptext.strip()
    print(uptext)

    for l in line:
        print(l)
        try:
            date = parser.parse(l, fuzzy=True)
            print(date)
            date = date.strftime("%d/%m/%Y %H:%M:%S")
            break
        except:
            date = ''
    print(date)
    #except:
    #    print('skip')

    print(date)
    row = df[df['docname'].str.contains(uptext, regex=False, flags=re.IGNORECASE)]
    print("row 1: \n", row)

    if row.shape[0] > 1:
        row_date = row[row['judgementdate'] ==  date]
        if row_date.shape[0] == 0 or row_date.shape[0] > 1:
            echr_date = line[-1].replace('ECHR ', 'ECHR:')
            echr_date = echr_date.strip()
            echr_date = re.sub('-.*', '', echr_date)
            print(echr_date)
            row = row[row['ecli'].str.contains(echr_date, na=False, regex=False)]
        else:
            return row_date
        print(row)


    return row


"""
def lookup_appno(pattern, df):
    print(pattern)
    row = df.loc[df['appno'].isin(pattern)]
    print(row)

    if row.empty:
        print("empty!")
        return []
    elif row.shape[0] > 1:
        check = lookup_casename(pattern, df)
    else:
        eclis = []
        for index,item in row.iterrows():
            if item.ecli is not np.nan:
                eclis.append(item.ecli)
                print(item.ecli)
        return eclis


def lookup_casename(text, date, df):
    uptext = text.upper()
    uptext = uptext.replace('V.', 'v.')
    uptext = uptext.replace('EUR. COURT H.R.', '')
    uptext = re.sub('JUDGMENT OF.*', '', uptext)
    #uptext = re.sub(r'\(.*', "", uptext)

uptext = uptext.strip()
    print(uptext)
    try:
        date = parser.parse(date)
        print(date)
        date = date.strftime("%d/%m/%Y %H:%M:%S")
    except:
        print('skip')

    row = df[df['docname'].str.contains(uptext, regex=False, flags=re.IGNORECASE)]
    print(row)

    if row.shape[0] > 1:
        row = row[row['judgementdate'] ==  date]
        print(row)
    eclis = []
    for index, item in row.iterrows():
        eclis.append(item.ecli)
    return eclis
"""


print('\n--- PREPARING DATAFRAME ---\n')
data = open_metadata(filename_metadata='ECHR_metadata.csv')

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

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))