import glob, sys
from os.path import dirname, abspath
import pandas as pd
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_PROCESSED

# In this list, we would insert headings of all the columns we want removed from the data
X = ['WORK IS CREATED BY AGENT (AU)', 'CASE LAW COMMENTED BY AGENT', 'CASE LAW HAS A TYPE OF PROCEDURE', 'LEGAL RESOURCE USES ORIGINALLY LANGUAGE', 'CASE LAW USES LANGUAGE OF PROCEDURE', 'CASE LAW HAS A JUDICIAL PROCEDURE TYPE', 'WORK HAS RESOURCE TYPE', 'LEGAL RESOURCE BASED ON TREATY CONCEPT', 'CASE LAW ORIGINATES IN COUNTRY OR USES A ROLE QUALIFIER', 'CASE LAW ORIGINATES IN COUNTRY', 'CASE LAW DELIVERED BY COURT FORMATION', 'LEGAL RESOURCE IS ABOUT SUBJECT MATTER', 'RELATED JOURNAL ARTICLE', 'CASE LAW DELIVERED BY ADVOCATE GENERAL', 'CASE LAW DELIVERED BY JUDGE', 'ECLI', 'CASE LAW INTERPRETS LEGAL RESOURCE', 'NATIONAL JUDGEMENT', 'DATE_CREATION_LEGACY', 'DATETIME NEGOTIATION', 'SEQUENCE OF VALUES', 'DATE OF REQUEST FOR AN OPINION', 'CELEX IDENTIFIER', 'SECTOR IDENTIFIER', 'NATURAL NUMBER (CELEX)', 'TYPE OF LEGAL RESOURCE', 'YEAR OF THE LEGAL RESOURCE', 'WORK CITES WORK. CI / CJ', 'LEGACY DATE OF CREATION OF WORK', 'DATE OF DOCUMENT', 'IDENTIFIER OF DOCUMENT', 'WORK VERSION', 'LAST CMR MODIFICATION DATE', 'CASE LAW HAS CONCLUSIONS']
Y = ['LEGAL RESOURCE HAS TYPE OF ACT', 'WORK HAS RESOURCE TYPE', 'CASE LAW ORIGINATES IN COUNTRY', 'LEGAL RESOURCE IS ABOUT SUBJECT MATTER', 'ECLI', 'REFERENCE TO PROVISIONS OF NATIONAL LAW', 'PUBLICATION REFERENCE OF COURT DECISION', 'CELEX IDENTIFIER', 'LOCAL IDENTIFIER', 'SECTOR IDENTIFIER', 'TYPE OF LEGAL RESOURCE', 'YEAR OF THE LEGAL RESOURCE', 'WORK IS CREATED BY AGENT (AU)', 'LEGACY DATE OF CREATION OF WORK', 'DATE OF DOCUMENT', 'IDENTIFIER OF DOCUMENT', 'WORK TITLE', 'CMR CREATION DATE', 'LAST CMR MODIFICATION DATE', 'CASE LAW DELIVERED BY NATIONAL COURT', 'REFERENCE TO A EUROPEAN ACT IN FREE TEXT', 'CASE LAW BASED ON A LEGAL INSTRUMENT', 'PARTIES OF THE CASE LAW']
all_data=X+Y
# All_data is a list of all the column headings in the entire document

# Saving will be a list of all the columns we will not be deleting
saving=['CASE LAW BASED ON A LEGAL INSTRUMENT','CASE LAW COMMENTED BY AGENT','CASE LAW DELIVERED BY COURT FORMATION','CASE LAW HAS A JUDICIAL PROCEDURE TYPE','CASE LAW HAS A TYPE OF PROCEDURE','CASE LAW HAS CONCLUSIONS','CASE LAW INTERPRETS LEGAL RESOURCE','CASE LAW ORIGINATES IN COUNTRY','CASE LAW ORIGINATES IN COUNTRY OR USES A ROLE QUALIFIER','CASE LAW USES LANGUAGE OF PROCEDURE','CELEX IDENTIFIER','DATE OF DOCUMENT','DATE OF REQUEST FOR AN OPINION','ECLI','LEGACY DATE OF CREATION OF WORK','LEGAL RESOURCE BASED ON TREATY CONCEPT','LEGAL RESOURCE IS ABOUT SUBJECT MATTER','NATIONAL JUDGEMENT','RELATED JOURNAL ARTICLE','SECTOR IDENTIFIER','WORK CITES WORK. CI / CJ','WORK HAS RESOURCE TYPE','YEAR OF THE LEGAL RESOURCE']
data_to_drop=[i for i in all_data if i not in saving]
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
        if("Transformed" not in csv_files[i] and "Citations" not in csv_files[i] and "Extracted" not in csv_files[i]):
            print("")
            print(f"TRANSFORMING {csv_files[i]} ")
            data=read_csv(csv_files[i])
            drop_columns(data,data_to_drop)
            output_path=csv_files[i].replace(".csv","_Transformed.csv")
            data.to_csv(output_path,index=False)
    print("")
    print(f"TRANSFORMATION DONE")
    print("")