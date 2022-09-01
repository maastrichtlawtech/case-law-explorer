import glob
import time
import warnings
import sys
from os.path import dirname, abspath
from definitions.storage_handler import CELLAR_DIR
from helpers.json_to_csv import json_to_csv
from helpers.csv_manipulator import drop_columns
from helpers.citations_adder import add_citations
from helpers.fulltext_saving import add_sections
warnings.filterwarnings("ignore")
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))

WINDOWS_SYSTEM = False

if sys.platform == "win32":
    WINDOWS_SYSTEM = True

"""
This is the main method for cellar file transformation.

It accepts a filepath to a .json file and does the following to it:

Transforms it to csv format*
Removes data we decided not to need *
Adds citations for every separate case*
Adds multiple sections as columns, introducing new columns*

After all that is done, it saves the csv file in processed directory with "Processed" in its name.

*More detail available in separate functions.

"""

def transform_file(filepath):
    print("How many threads should the code use for this transformation? (15 should be safe, higher numbers might "
          "limit your internet heavily)")
    threads = int(input())
    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', "PROCESSED DIR")
    print('\n--- START ---\n')
    start: float = time.time()
    print("TRANSFORMING JSON INTO CSV")
    data = json_to_csv(filepath)
    print("TRANSFORMATION OF CSV FILES IN DATA PROCESSED DIR STARTED")
    print("REMOVING REDUNDANT COLUMNS AND NON-EU CASES")
    drop_columns(data)
    first = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(first - start)))
    print("ADDING CITATIONS IN CELEX FORMAT")
    add_citations(data, threads)
    second = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(second - first)))
    print("ADDING FULL TEXT, SUMMARY, KEYWORDS, SUBJECT MATTER AND CASE LAW DIRECTORY CODES")
    add_sections(data, threads)
    data.to_csv(filepath.replace(".csv", "_Processed_.csv"), index=False)
    print("WORK FINISHED SUCCESSFULLY!")
    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - second)))

if __name__ == '__main__':
    print("Welcome to cellar transformation!")
    json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))
    for file in json_files:
        print(f"\nFound file {file}")
        print("\nShould this file be transformed? Answer Y/N please.")
        answer = str(input())
        if answer == "Y":
            transform_file(file)