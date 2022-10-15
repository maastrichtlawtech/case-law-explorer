import glob
import pandas as pd
from definitions.storage_handler import DIR_DATA_PROCESSED
import threading
from helpers.json_to_csv import read_csv
from helpers.eurlex_scraping import get_summary_from_html, get_summary_html, get_keywords_from_html, get_entire_page, \
    get_full_text_from_html, get_subject, get_codes, get_eurovoc
from concurrent.futures import ThreadPoolExecutor
"""
This is the method executed by individual threads by the add_sections method.

The big dataset is divided in parts, each thread gets its portion of work to do.
They add their portions of columns to corresponding lists, 
after all the threads are done the individual parts are put together.
"""


def execute_sections_threads(celex, start, list_sum, list_key, list_full, list_subject, list_codes, list_eurovoc):
    sum = pd.Series([], dtype='string')
    key = pd.Series([], dtype='string')
    full = pd.Series([], dtype='string')
    subject_matter = pd.Series([], dtype='string')
    case_codes = pd.Series([], dtype='string')
    eurovocs = pd.Series([], dtype='string')
    for i in range(len(celex)):
        j = start + i
        id = celex[j]
        summary = get_summary_html(id)
        if summary != "No summary available":
            text = get_keywords_from_html(summary, id[0])
            text2 = get_summary_from_html(summary, id[0])
            key[j] = text
            sum[j] = text2
        else:
            key[j] = ""
            sum[j] = ""
        entire_page = get_entire_page(id)
        text = get_full_text_from_html(entire_page)
        if entire_page != "No data available":
            subject = get_subject(text)
            code = get_codes(text)
            eurovoc = get_eurovoc(text)
        else:
            code = ""
            subject = ""
            eurovoc = ""
        eurovocs[j] = eurovoc
        subject_matter[j] = subject
        case_codes[j] = code
    list_sum.append(sum)
    list_key.append(key)
    # list_full.append(full)  # Currently turned off, as we will find another way to save full data
    list_codes.append(case_codes)
    list_subject.append(subject_matter)
    list_eurovoc.append(eurovocs)


"""
This method adds the following sections to a pandas dataframe, as separate columns:

Full Text
Case law directory codes
Subject matter
Keywords
Summary

Method is cellar-specific, scraping html from https://eur-lex.europa.eu/homepage.html.
It operates with multiple threads, using that feature is recommended as it speeds up the entire process.
"""


def add_sections(data, threads):
    name = 'CELEX IDENTIFIER'
    celex = data.loc[:, name]
    length = celex.size
    if length > 100:  # to avoid getting problems with small files
        at_once_threads = int(length / threads)
    else:
        at_once_threads = length
    threads = []
    list_sum = list()
    list_key = list()
    list_full = list()
    list_codes = list()
    list_subject = list()
    list_eurovoc = list()
    for i in range(0, length, at_once_threads):
        curr_celex = celex[i:(i + at_once_threads)]
        t = threading.Thread(target=execute_sections_threads,
                             args=(
                                 curr_celex, i, list_sum, list_key, list_full, list_subject, list_codes, list_eurovoc))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    add_column_frow_list(data, "celex_summary", list_sum)
    add_column_frow_list(data, "celex_keywords", list_key)
    add_column_frow_list(data, "celex_eurovoc", list_eurovoc)
    # add_column_frow_list(data,"celex_full_text",list_full)  # Currently turned off, as we will find another way to
    # save full data
    add_column_frow_list(data, "celex_subject_matter", list_subject)
    add_column_frow_list(data, "celex_directory_codes", list_codes)
def add_sections_pool(data, threads):
    name = 'CELEX IDENTIFIER'
    celex = data.loc[:, name]
    length = celex.size
    if length > 100:  # to avoid getting problems with small files
        at_once_threads = int(length / threads)
    else:
        at_once_threads = length
    threads = []
    list_sum = list()
    list_key = list()
    list_full = list()
    list_codes = list()
    list_subject = list()
    list_eurovoc = list()
    with ThreadPoolExecutor() as executor:
        for i in range(0, length, at_once_threads):
            curr_celex = celex[i:(i + at_once_threads)]
            executor.submit(execute_sections_threads,curr_celex,i,list_sum,list_key,list_full,list_subject,list_codes,list_eurovoc)
    executor.shutdown()
    add_column_frow_list(data, "celex_summary", list_sum)
    add_column_frow_list(data, "celex_keywords", list_key)
    add_column_frow_list(data, "celex_eurovoc", list_eurovoc)
    # add_column_frow_list(data,"celex_full_text",list_full)  # Currently turned off, as we will find another way to
    # save full data
    add_column_frow_list(data, "celex_subject_matter", list_subject)
    add_column_frow_list(data, "celex_directory_codes", list_codes)


"""
Used for adding columns easier to a dataframe for add_sections().
"""


def add_column_frow_list(data, name, list):
    column = pd.Series([], dtype='string')
    for l in list:
        column = column.append(l)
    column.sort_index(inplace=True)
    data.insert(1, name, column)

"""
Main function for manual transformation of csv files.
"""
if __name__ == '__main__':
    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")
    for i in range(len(csv_files)):
        if "Extracted" in csv_files[i]:
            print("")
            print(f"WORKING ON  {csv_files[i]} ")
            data = read_csv(csv_files[i])
            add_sections(data, 15)
            data.to_csv(csv_files[i].replace("Extracted", "With Summary"), index=False)
    print("WORK FINISHED SUCCESSFULLY!")
