import glob
import os
import sys
import time
import warnings
from os.path import dirname, abspath

import pandas as pd

from definitions.storage_handler import DIR_DATA_RAW, get_path_processed, CSV_CELLAR_CASES
from helpers.citations_adder import add_citations,add_citations_separate
from helpers.csv_manipulator import drop_columns
from helpers.fulltext_saving import add_sections,add_sections_pool
from helpers.json_to_csv import read_csv, transform_main_file

warnings.filterwarnings("ignore")
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))

WINDOWS_SYSTEM = False

if sys.platform == "win32":
    WINDOWS_SYSTEM = True

"""
This is the main method for cellar file transformation.

It accepts a filepath to a .csv file and does the following to it:

Transforms the freshest json download and transforms it to the csv.
Removes data we decided not to need *
Adds citations for every separate case*
Adds multiple sections as columns, introducing new columns*

After all that is done, it saves the csv file in raw directory as the csv path provided.

*More detail available in separate functions.

"""


def update_cellar(update_path):
    update = read_csv(update_path)
    output = get_path_processed(CSV_CELLAR_CASES)
    main = read_csv(output)
    main = pd.concat([main, update])
    main.to_csv(output, index=False)
    os.remove(update_path)


def transform_cellar(filepath, threads):
    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', "PROCESSED DIR")
    print('\n--- START ---\n')
    start: float = time.time()

    done = transform_main_file()
    # Airflow modification, makes sure that it won't restart when this failed
    if done:
        data = read_csv(filepath)
        print("TRANSFORMATION OF CSV FILES INTO DATA PROCESSED DIR STARTED")
        print("REMOVING REDUNDANT COLUMNS AND NON-EU CASES")
        drop_columns(data)
        first = time.time()
        print("\n--- DONE ---")
        print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(first - start)))
        print("ADDING CITATIONS IN CELEX FORMAT")
        add_citations(data, threads)
       # add_citations_separate(data,threads)
        second = time.time()
        print("\n--- DONE ---")
        print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(second - first)))
        print("ADDING FULL TEXT, SUMMARY, KEYWORDS, SUBJECT MATTER AND CASE LAW DIRECTORY CODES")
        add_sections(data, threads)
        #add_sections_pool(data,threads)
        data.to_csv(filepath, index=False)
        print("WORK FINISHED SUCCESSFULLY!")
        end = time.time()
        print("\n--- DONE ---")
        print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - second)))
        return True
    else:
        print("CELLAR TRANSFORMATION FAILED -> EMPTY JSON FILE")
        return False


if __name__ == '__main__':
    print("Welcome to cellar transformation!")
    json_files = (glob.glob(DIR_DATA_RAW + "/" + "*.csv"))
    for file in json_files:
        print(f"\nFound file {file}")
        print("\nShould this file be transformed? Answer Y/N please.")
        answer = str(input())
        if answer == "Y":
            print(
                "How many threads should the code use for this transformation? (15 should be safe, higher numbers might"
                " limit your internet heavily)")
            thread = int(input())
            transform_cellar(file, thread)
