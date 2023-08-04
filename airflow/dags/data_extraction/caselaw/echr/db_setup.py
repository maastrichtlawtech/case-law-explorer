
import echr_extractor as echr
from definitions.storage_handler import *
import pandas as pd
import json
from os.path import exists
def get_echr_setup_args(last_index):
    """
    ECHR database setup routine - for building entire DB from scratch.
    This method returns the start&end dates for extraction
    Index referenced in code is the index of last visited point in the var_list.
    Proper usage will set up the entire database, with small increments, year by year.
    """
    var_list = ['1995-01-01', '1996-01-01', '1997-01-01', '1998-01-01', '1999-01-01', '2000-01-01', '2001-01-01',
                '2002-01-01',
                '2003-01-01', '2004-01-01', '2005-01-01', '2006-01-01', '2007-01-01', '2008-01-01', '2009-01-01',
                '2010-01-01',
                '2011-01-01', '2012-01-01', '2013-01-01', '2014-01-01', '2015-01-01', '2016-01-01', '2017-01-01',
                '2018-01-01',
                '2019-01-01', '2020-01-01', '2021-01-01', '2022-01-01', '2023-01-01']
    next_index = last_index + 1  # end index
    if last_index >= len(var_list):  # if start is out, no extraction out
        starting = None
        ending = None
    elif last_index >= 0:  # starting is in
        starting = var_list[last_index]
        if next_index >= len(var_list):  # determine if end is there or no
            ending = None
        else:
            ending = var_list[next_index]
    else:
        starting = None
        ending = var_list[0]

    return starting, ending
def setup_db():
    df_filepath = get_path_raw(CSV_ECHR_CASES)
    json_filepath = JSON_FULL_TEXT_ECHR
    for i in range(-1, 29):  # runs the entire db setup in small steps, as current implementation can only do 10k at once
        starting, ending = get_echr_setup_args(i)
        if starting and ending:
            print(f'Starting from manually specified date: {starting} and ending at end date: {ending}')
            metadata, full_text = echr.get_echr_extra(count=100000, start_date=starting, end_date=ending,
                                                      save_file="n")
        elif starting:
            print(f'Starting from manually specified date: {starting}')
            metadata, full_text = echr.get_echr_extra(count=100000, start_date=starting,
                                                      save_file="n")
        elif ending:
            print(f'Ending at manually specified end date {ending}')
            metadata, full_text = echr.get_echr_extra(count=100000, end_date=ending,
                                                      save_file="n")

        if exists(df_filepath):
            df = pd.read_csv(df_filepath)
            df_appended = pd.concat([df, metadata])
            df_appended.to_csv(df_filepath, index=False)
        else:
            metadata.to_csv(df_filepath, index=False)

        if exists(json_filepath):
            with open(json_filepath, "r+") as file:
                file_data = json.load(file)
                file_data.append(full_text)
                file.seek(0)
                json.dump(file_data, file)
        else:
            with open(json_filepath, 'w') as f:
                json.dump(full_text, f)
    print("Adding Nodes and Edges lists to storage should happen now")
    big_metadata = pd.read_csv(df_filepath)
    nodes, edges = echr.get_nodes_edges(dataframe=big_metadata, save_file="n")
    # get only the ecli column in nodes
    nodes = nodes[['ecli']]

    nodes_txt = get_path_raw(TXT_ECHR_NODES)
    edges_txt = get_path_raw(TXT_ECHR_EDGES)

    # save to text file from dataframe
    nodes.to_csv(nodes_txt, index=False, header=False, sep='\t')
    edges.to_csv(edges_txt, index=False, header=False, sep='\t')


if __name__ == "__main__":
    pass