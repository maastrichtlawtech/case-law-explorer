import glob, sys
from os.path import dirname, abspath
import pandas as pd
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_PROCESSED

# In this list, we would insert headings of all the columns we want removed from the data
data_to_drop = ["CASE LAW HAS A TYPE OF PROCEDURE", "SECTOR IDENTIFIER", "YEAR OF THE LEGAL RESOURCE"]

def read_csv(file_path):
    try:
        data = pd.read_csv(file_path,sep=",",encoding='utf-8')
        #print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)

def drop_columns(data,columns):
    for i in range(len(columns)):
        try:
            data.pop(columns[i])
        except:
            print(f"Column titled {columns[i]} does not exist in the file!")



if __name__ == '__main__':
    print("")
    print("TRANSFORMATION OF CSV FILES IN DATA PROCESSED DIR STARTED")
    print("")
    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")

    for i in range(len(csv_files)):
        if("Transformed" not in csv_files[i]):
            print("")
            print(f"TRANSFORMING {csv_files[i]} ")
            data=read_csv(csv_files[i])
            drop_columns(data,data_to_drop)
            output_path=csv_files[i].replace(".csv","_Transformed.csv")
            data.to_csv(output_path,index=False)
    print("")
    print(f"TRANSFORMATION DONE")
    print("")