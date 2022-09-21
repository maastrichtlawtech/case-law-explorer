import glob, sys
from os.path import dirname, abspath
import argparse

# sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_RAW
from helpers.json_to_csv import read_csv


# In this list, we would insert headings of all the columns we want removed from the data

def extract_rows(data, number):
    try:
        output = data[1:number]
    except:
        print(f"The file does not have {number} entries, returning entire file.")
        output = data
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--amount', help='number of rows to extract', type=int, required=True)
    args = parser.parse_args()
    # The first row contains only the column headings, which is why we add +1
    number = args.amount + 1

    print("")
    print("EXTRACTION FROM CSV FILE IN DATA PROCESSED DIR STARTED")
    print("")
    csv_files = (glob.glob(DIR_DATA_RAW + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")

    for i in range(len(csv_files)):
        if ("clean" not in csv_files[i]):
            print("")
            print(f"EXTRACTING FROM {csv_files[i]} ")
            data = read_csv(csv_files[i])
            output = extract_rows(data, number)
            output_path = DIR_DATA_RAW+"/tester_100.csv"
            output.to_csv(output_path, index=False)
    print("")
    print(f"Extraction DONE")
    print("")
