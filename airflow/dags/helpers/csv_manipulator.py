import glob
from definitions.storage_handler import DIR_DATA_PROCESSED
from data_transformation.utils import read_csv

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
     'CASE LAW BASED ON A LEGAL INSTRUMENT', 'PARTIES OF THE CASE LAW', 'index']

COLS = set(X + Y)
COLS = sorted(COLS)
all_data = X + Y
# All_data is a list of all the column headings in the entire document

# Saving will be a list of all the columns we will not be deleting
saving = ['CASE LAW COMMENTED BY AGENT', 'CASE LAW DELIVERED BY COURT FORMATION',
          'CASE LAW HAS A JUDICIAL PROCEDURE TYPE', 'CASE LAW HAS A TYPE OF PROCEDURE', 'CASE LAW HAS CONCLUSIONS',
          'CASE LAW INTERPRETS LEGAL RESOURCE', 'CASE LAW ORIGINATES IN COUNTRY',
          'CASE LAW ORIGINATES IN COUNTRY OR USES A ROLE QUALIFIER', 'CASE LAW USES LANGUAGE OF PROCEDURE',
          'CELEX IDENTIFIER', 'DATE OF DOCUMENT', 'DATE OF REQUEST FOR AN OPINION', 'ECLI',
          'LEGACY DATE OF CREATION OF WORK', 'LEGAL RESOURCE BASED ON TREATY CONCEPT',
          'LEGAL RESOURCE IS ABOUT SUBJECT MATTER', 'NATIONAL JUDGEMENT', 'RELATED JOURNAL ARTICLE',
          'SECTOR IDENTIFIER', 'WORK HAS RESOURCE TYPE', 'YEAR OF THE LEGAL RESOURCE']
data_to_drop = [i for i in all_data if i not in saving]

"""
Method used to remove unnecessary columns from a dataframe.
"""
types_to_keep = ['Unknown', 'Opinion of the Advocate General', 'Judgment']

def drop_columns(data):
    columns = data_to_drop
    for i in range(len(columns)):
        try:
            data.pop(columns[i])
        except Exception:
            print(f"Column titled {columns[i]} does not exist in the file!")
    data.drop(data[-data.ECLI.str.contains("ECLI:EU:C")].index, inplace=True)
    data.drop(data[-data['CELEX IDENTIFIER'].str.startswith('6')].index,inplace=True)
    data['WORK HAS RESOURCE TYPE'] = data['WORK HAS RESOURCE TYPE'].fillna('Unknown')
    data.drop(data[-data['WORK HAS RESOURCE TYPE'].str.contains('|'.join(types_to_keep))].index, inplace=True)

  #  data.drop(data[-data['WORK HAS RESOURCE TYPE'].contains("ECLI:EU:C")].index, inplace=True)
    data.reset_index(inplace=True, drop=True)


if __name__ == '__main__':
    print("")
    print("TRANSFORMATION OF CSV FILES IN DATA PROCESSED DIR STARTED")
    print("")
    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    for i in range(len(csv_files)):
        if "test" in csv_files[i]:
            data = read_csv(csv_files[i])
            b = 3
    b = 2
    print("")
    print(f"TRANSFORMATION DONE")
    print("")
