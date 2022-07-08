import glob, sys
from os.path import dirname, abspath
import pandas as pd
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_PROCESSED



def read_csv(file_path):
    try:
        data = pd.read_csv(file_path,sep=",",encoding='utf-8')
        #print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)
def add_sections(data):
    name='LEGAL RESOURCE HAS TYPE OF ACT'
    links = data.loc[:,name]
    S1 = pd.Series([])


if __name__ == '__main__':
    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")
    for i in range(len(csv_files)):
        if ("Extracted" in csv_files[i]):
            print("")
            print(f"EXTRACTING FROM {csv_files[i]} ")
            data = read_csv(csv_files[i])
            add_sections(data)
            data.to_csv(csv_files[i].replace("With Citations","With Citations and Sections"), index=False)