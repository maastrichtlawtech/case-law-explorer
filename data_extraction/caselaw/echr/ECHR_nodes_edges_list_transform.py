import numpy as np
import pandas as pd
import re
import re
import sys
import time
import dateutil.parser as parser    # for selecting by date
import dateparser
import datetime
import argparse
from os.path import dirname, abspath
from definitions.storage_handler import Storage, CSV_ECHR_CASES_NODES, CSV_ECHR_CASES_EDGES, CSV_ECHR_CASES_EDGES_JSON, CSV_ECHR_CASES_NODES_JSON

current_dir = dirname(dirname(abspath(__file__)))
correct_dir = '\\'.join(current_dir.replace('\\', '/').split('/')[:-2])
sys.path.append(correct_dir)


def open_metadata(filename_metadata):
    df = pd.read_csv('C:/Users/Chloe/PycharmProjects/case-law-explorer/data/echr/' + filename_metadata)  # change hard coded path
    return df


def metadata_to_nodesedgeslist(df):
    """
    Returns a dataframe where column 'article' only contains a certain article

    param df: the complete dataframe from the metadata
    """
    df = df[df['article'].notna()]
    df = df[df.article.str.contains("P1")]  # change to args -> need mapping between article names and format in column?
    return df


def retrieve_nodes_list(df):
    """
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

    count = 0
    tot_num_refs = 0
    missing_cases = []
    for index, item in df.iterrows():
        print(index)
        #percentage = count / len(df.index) * 100
        #sys.stdout.write('\r' + str(percentage))
        #sys.stdout.flush()
        eclis = []

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
            ref_list = item.scl.split(';')
            new_ref_list = []
            for ref in ref_list:
                ref = re.sub('\n', '', ref)
                new_ref_list.append(ref)

            tot_num_refs = tot_num_refs + len(ref_list)

            for ref in new_ref_list:
                #print("ref: ", ref)

                app_number = re.findall("[0-9]{4,5}\/[0-9]{2}", ref)

                if len(app_number) > 0:
                    # get dataframe with all possible cases by application number
                    if len(app_number) > 1:
                        app_number = [';'.join(app_number)]
                        #print(app_number)
                    case = lookup_app_number(app_number, df_unfiltered)
                else: # if no application number in reference
                    # get dataframe with all possible cases by casename
                    case = lookup_casename(ref, df_unfiltered)

                if len(case) == 0:
                    case = lookup_casename(ref, df_unfiltered)

                components = ref.split(',')
                # get the year of case
                year_from_ref = get_year_from_ref(components)
                #print("year from ref: ", year_from_ref)

                # remove cases in different language than reference
                for id, it in case.iterrows():
                    if 'v.' in components[0]:
                        lang = 'ENG'
                    else:
                        lang = 'FRE'

                    if lang not in it.languageisocode:
                        case = case[case['languageisocode'].str.contains(lang, regex=False, flags=re.IGNORECASE)]

                for id, i in case.iterrows():
                    #print("num of cases: ", len(case))
                    date = dateparser.parse(i.judgementdate)
                    year_from_case = date.year
                    #print(year_from_case)

                    if year_from_case - year_from_ref == 0:
                        case = case[case['judgementdate'].str.contains(str(year_from_ref), regex=False, flags=re.IGNORECASE)]

                case = metadata_to_nodesedgeslist(case)

                if len(case) > 0:
                    if len(case) > 3:
                        print("stop")
                    #print(case)
                    for _,row in case.iterrows():

                        eclis.append(row.ecli)
                    #print("final case: ",case, " date: ", case.judgementdate)
                else:
                    count = count + 1
                    missing_cases.append(ref)

            eclis = set(eclis)
            #add ecli to edges list
            edges = pd.concat(
                [edges, pd.DataFrame.from_records([{'ecli': item.ecli, 'references': eclis}])])

    print("num missed cases: ", count)
    print("total num of refs: ", tot_num_refs)
    missing_cases_set = set(missing_cases)
    missing_cases = list(missing_cases_set)

    missing_df = pd.DataFrame(missing_cases)
    missing_df.to_csv('C:/Users/Chloe/PycharmProjects/case-law-explorer/data/echr/missing_cases.csv', index=False, encoding='utf-8')

    return edges


def lookup_app_number(pattern, df):
    """
    Returns a list with rows containing the cases linked to the found app numbers.
    """
    #print(pattern)
    row = df.loc[df['appno'].isin(pattern)]
    # print(row)

    if row.empty:
        #print(" row empty!")
        return pd.DataFrame()
    elif row.shape[0] > 1:
        return row
    else:
        return row


def lookup_casename(ref, df):
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

    name = get_casename(ref)
    #print("name: ", name)

    f = open('CLEAN_REF.txt', 'r')
    patterns = f.read().splitlines()

    uptext = name.upper()
    #print("upper: ",uptext)

    if 'NO.' in uptext:
        uptext = uptext.replace('NO.', 'No.')

    if 'BV' in uptext:
        uptext = uptext.replace('BV', 'B.V.')

    if 'v.' in name:
        uptext = uptext.replace('V.', 'v.')
        lang = 'ENG'
    else:
        uptext = uptext.replace('C.', 'c.')
        lang = 'FRE'

    for pattern in patterns:
        uptext = re.sub(pattern, '', uptext)

    uptext = re.sub(r'\[.*', "", uptext)
    uptext = uptext.strip()
    #print("final text: ", uptext)

    row = df[df['docname'].str.contains(uptext, regex=False, flags=re.IGNORECASE)]

    if len(row) == 0:
        print("no cases matched: ", name)

    return row

def get_casename(ref):
    #print(ref)
    count = 0
    if 'v.' in ref:
        slice_at_versus = ref.split('v.')  # skip if typo (count how many)
    elif 'c.' in ref:
        slice_at_versus = ref.split('c.')
    else:
        count = count + 1
        #print('no versus')
        name = ref.split(',')
        return name[0]

    #print("before slice: ", slice_at_versus)
    # slice_at_versus[0] = slice_at_versus[0].replace(',', '')
    # slice_at_versus[0] = slice_at_versus[0].replace('\n', '')
    # print(slice_at_versus)

    num_commas = slice_at_versus[0].count(',')
    #print('commas: ', num_commas)

    # ref = " ".join(slice_at_versus)
    if num_commas > 0:
        num_commas = num_commas + 1
        # for i in range(0, len(components), num_commas):
        #    print("i: ", i, "components: ", components[i])
        name = ",".join(ref.split(",", num_commas)[:num_commas])
        # components = ref.split(",", num_commas)
        # components = ','.join(components[i:i + num_commas] for i in range(0, len(components), num_commas))
        #print("components: ", name)
        #print(ref)
    else:
        name = ref.split(',')
        #print('no commas')
        return name[0]
    return name

def get_year_from_ref(ref):
    for component in ref:
        if '§' in component:
            continue
        #print(component)
        if dateparser.parse(component) is not None:
            date = dateparser.parse(component)
            #print("good date: ",date)
        elif ("ECHR" in component or "CEDH" in component):
            if ("ECHR" in component or "CEDH" in component):
                date = re.sub('ECHR ', '', component)
                date = re.sub('CEDH ', '', date)
                date = date.strip()
                date = re.sub('-.*', '', date)
                date = re.sub('\s.*', '', date)
                #print('echr_date: ', date)
                date = dateparser.parse(date)
                #print("year: ", date.year)
        #else:
         #   return 0
    try:
        return date.year
    except:
        return 0
    #return date.year


# ---- RUN ----
print('\n--- PREPARING DATAFRAME ---\n')
data = open_metadata(filename_metadata='ECHR_metadata.csv')

print('\n--- CREATING NODES LIST ---\n')
nodes = retrieve_nodes_list(data)
print(nodes)

print('\n--- START EDGES LIST ---\n')
start = time.time()

print('\n--- CREATING EDGES LIST ---\n')
edges = retrieve_edges_list(nodes, data)
print(edges)
#final_edges = edges.groupby('ecli', as_index=False)['references'].agg(lambda x : list(set([e for l in x for e in l])))

print('\n--- CREATING CSV FILES ---\n')
# nodes.to_csv(CSV_ECHR_CASES_NODES, index=False, encoding='utf-8')
edges.to_csv(CSV_ECHR_CASES_EDGES, index=False, encoding='utf-8')
nodes.to_json(CSV_ECHR_CASES_NODES_JSON, orient="records")
edges.to_json(CSV_ECHR_CASES_EDGES_JSON, orient="records")

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))