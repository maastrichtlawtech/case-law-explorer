import glob, sys
from os.path import dirname, abspath,join
import pandas as pd
import csv
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import CELLAR_DIR
output_path=join(CELLAR_DIR,'output.csv')

data_to_drop=["CASE LAW BASED ON A LEGAL INSTRUMENT"]

def read_csv(file_path):

    data = pd.read_csv(file_path,sep=",",encoding='utf-8')
    print(data)
    return data

def drop_columns(data,columns):
    for i in range(len(columns)):
        data.pop(columns[i])
        #data.drop(columns[i],inplace=True,axis=1)


if __name__ == '__main__':
    print("TRANSFORMATION OF CSV FILES IN CELLAR DIR STARTED")
    csv_files = (glob.glob(CELLAR_DIR + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")
    for i in range(len(csv_files)):
        print(f"TRANSFORMING {csv_files[i]} ")
        data=read_csv(csv_files[i])
        drop_columns(data,data_to_drop)
        data.to_csv(output_path,index=False)
    print(f"TRANSFORMATION DONE")