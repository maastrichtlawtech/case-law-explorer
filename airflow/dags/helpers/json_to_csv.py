import json, csv, re, glob
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings("ignore")
import sys
from definitions.storage_handler import CELLAR_DIR, DIR_DATA_RAW, get_path_raw, CSV_CELLAR_CASES

WINDOWS_SYSTEM = False
import pandas as pd

X = ['WORK IS CREATED BY AGENT (AU)', 'CASE LAW COMMENTED BY AGENT', 'CASE LAW HAS A TYPE OF PROCEDURE',
     'LEGAL RESOURCE USES ORIGINALLY LANGUAGE', 'CASE LAW USES LANGUAGE OF PROCEDURE',
     'CASE LAW HAS A JUDICIAL PROCEDURE TYPE', 'WORK HAS RESOURCE TYPE', 'LEGAL RESOURCE BASED ON TREATY CONCEPT',
     'CASE LAW ORIGINATES IN COUNTRY OR USES A ROLE QUALIFIER', 'CASE LAW ORIGINATES IN COUNTRY',
     'CASE LAW DELIVERED BY COURT FORMATION', 'LEGAL RESOURCE IS ABOUT SUBJECT MATTER', 'RELATED JOURNAL ARTICLE',
     'CASE LAW DELIVERED BY ADVOCATE GENERAL', 'CASE LAW DELIVERED BY JUDGE', 'ECLI',
     'CASE LAW INTERPRETS LEGAL RESOURCE', 'NATIONAL JUDGEMENT', 'DATE_CREATION_LEGACY', 'DATETIME NEGOTIATION',
     'SEQUENCE OF VALUES', 'DATE OF REQUEST FOR AN OPINION', 'CELEX IDENTIFIER', 'SECTOR IDENTIFIER',
     'NATURAL NUMBER (CELEX)', 'TYPE OF LEGAL RESOURCE', 'YEAR OF THE LEGAL RESOURCE', 'WORK CITES WORK. CI / CJ',
     'LEGACY DATE OF CREATION OF WORK', 'DATE OF DOCUMENT', 'IDENTIFIER OF DOCUMENT', 'WORK VERSION',
     'LAST CMR MODIFICATION DATE', 'CASE LAW HAS CONCLUSIONS']
Y = ['LEGAL RESOURCE HAS TYPE OF ACT', 'WORK HAS RESOURCE TYPE', 'CASE LAW ORIGINATES IN COUNTRY',
     'LEGAL RESOURCE IS ABOUT SUBJECT MATTER', 'ECLI', 'REFERENCE TO PROVISIONS OF NATIONAL LAW',
     'PUBLICATION REFERENCE OF COURT DECISION', 'CELEX IDENTIFIER', 'LOCAL IDENTIFIER', 'SECTOR IDENTIFIER',
     'TYPE OF LEGAL RESOURCE', 'YEAR OF THE LEGAL RESOURCE', 'WORK IS CREATED BY AGENT (AU)',
     'LEGACY DATE OF CREATION OF WORK', 'DATE OF DOCUMENT', 'IDENTIFIER OF DOCUMENT', 'WORK TITLE', 'CMR CREATION DATE',
     'LAST CMR MODIFICATION DATE', 'CASE LAW DELIVERED BY NATIONAL COURT', 'REFERENCE TO A EUROPEAN ACT IN FREE TEXT',
     'CASE LAW BASED ON A LEGAL INSTRUMENT', 'PARTIES OF THE CASE LAW']

COLS = set(X + Y)
COLS = sorted(COLS)

"""
Method used after the json to csv conversion, to save the file in the processed directory.
"""


def create_csv(filepath, encoding="UTF8", data=None, filename="undefined.csv"):
    if data != "":
        csv_file = open(filepath, 'w', encoding=encoding)
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(COLS)
        csv_writer.writerows(data)
        csv_file.close()
        print("CSV file " + filename + " created in " + DIR_DATA_RAW)


"""
Reads the json file and returns it.
"""


def read_json(file_path):
    with open(file_path, 'r') as f:
        json_data = json.loads(f.read())
    return json_data


"""
Method used to transform the json file received from cellar_extraction to a csv file.
Cellar specific, sets specific columns with names defined at the beginning of file as COLS.
"""


def json_to_csv(json_data):
    final_data = []
    for i in json_data:
        ecli_data = json_data[i]

        data = [''] * len(COLS)

        for v in ecli_data.items():
            title = v[0].upper()

            value = str(v[1])
            # Remove new lines
            value = re.sub(r"\\n", '', str(value))
            # Remove blank spaces appearing more than one time
            value = re.sub(r" +", ' ', str(value))
            # Remove brackets
            value = re.sub(r"\[", "", str(value))
            value = re.sub(r"\]", "", str(value))
            # Remove unwanted quotation marks
            value = re.sub(r"'", "", str(value))
            # value = re.sub("\"", "", str(value))
            # Remove semicolon
            value = re.sub(r";", ",", str(value))
            # Changing the commas inside lists of data into _, a fix to windows-only issue
            # Making commas as the only value separator in the dataset
            value = re.sub(r",", ";", str(value))
            # Remove HTML tags
            value = BeautifulSoup(value, "lxml").text

            for j in [j for j, x in enumerate(COLS) if x == title]:
                data[j] = value
        # data.insert(j-1, value)
        # print(j-1, value)

        final_data.append(data)
    return final_data


"""
Reads a csv file and returns it.
"""


def read_csv(file_path):
    try:
        data = pd.read_csv(file_path, sep=",", encoding='utf-8')
        return data
    except Exception:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)


"""
Used for cellar transformation, transforms newest json download to csv.
"""


def transform_main_file():
    try:
        json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))
        return json_to_csv_main(json_files[0])
    except:
        return False


"""
Main method of json_to_csv, transforms the entire json file and saves in raw folder of data, 
ready for further transformations.
"""


def json_to_csv_main(filepath):
    i = filepath
    print(f"JSON TO CSV OF {filepath} HAS STARTED")
    json_data = read_json(i)
    if json_data:
        final_data = json_to_csv(json_data)

        if final_data:
            filename = CSV_CELLAR_CASES
            filepath = get_path_raw(CSV_CELLAR_CASES)

            create_csv(filepath=filepath, encoding="UTF8", data=final_data, filename=filename)
        else:
            print("Error creating CSV file. Data is empty.")
            return False
    else:
        print("Error reading json file. Please make sure json file exists and contains data.")
        return False
    return True


if __name__ == '__main__':
    json_data = '';

    json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))

    for i in json_files:
        print(f"\nFound file {i}")
        print("\nShould this file be transformed? Answer Y/N please.")
        answer = str(input())
        if answer == "Y":
            json_to_csv_main(i)
