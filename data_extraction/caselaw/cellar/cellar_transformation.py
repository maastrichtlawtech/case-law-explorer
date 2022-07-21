import json, csv, re, glob
from bs4 import BeautifulSoup
import warnings
import time
warnings.filterwarnings("ignore")
import sys
from SPARQLWrapper import SPARQLWrapper, JSON,CSV,POST
import requests
from io import StringIO
from os.path import dirname, abspath, join
import re
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import CELLAR_DIR, DIR_DATA_PROCESSED

WINDOWS_SYSTEM = False
import pandas as pd
from eurlex import get_html_by_celex_id

if sys.platform == "win32":
    WINDOWS_SYSTEM = True


def read_csv(file_path):
    try:
        data = pd.read_csv(file_path, sep=",", encoding='utf-8')
        # print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)


def drop_columns(data, columns):
    for i in range(len(columns)):
        try:
            data.pop(columns[i])
        except:
            print(f"Column titled {columns[i]} does not exist in the file!")
    data.drop(data[-data.ECLI.str.contains("ECLI:EU")].index, inplace=True)
    data.reset_index(drop=True,inplace=True)


def windows_path(original):
    return original.replace('\\', '/')


# 'WORK_IS_CREATED_BY_AGENT_(AU)',_'CASE_LAW_COMMENTED_BY_AGENT',_'CASE_LAW_HAS_A_TYPE_OF_PROCEDURE',_'LEGAL_RESOURCE_USES_ORIGINALLY_LANGUAGE',_'CASE_LAW_USES_LANGUAGE_OF_PROCEDURE',_'CASE_LAW_HAS_A_JUDICIAL_PROCEDURE_TYPE',_'WORK_HAS_RESOURCE_TYPE',_'LEGAL_RESOURCE_BASED_ON_TREATY_CONCEPT',_'CASE_LAW_ORIGINATES_IN_COUNTRY_OR_USES_A_ROLE_QUALIFIER',_'CASE_LAW_ORIGINATES_IN_COUNTRY',_'CASE_LAW_DELIVERED_BY_COURT_FORMATION',_'LEGAL_RESOURCE_IS_ABOUT_SUBJECT_MATTER',_'RELATED_JOURNAL_ARTICLE',_'CASE_LAW_DELIVERED_BY_ADVOCATE_GENERAL',_'CASE_LAW_DELIVERED_BY_JUDGE',_'ECLI',_'CASE_LAW_INTERPRETS_LEGAL_RESOURCE',_'NATIONAL_JUDGEMENT',_'DATE_CREATION_LEGACY',_'DATETIME_NEGOTIATION',_'SEQUENCE_OF_VALUES',_'DATE_OF_REQUEST_FOR_AN_OPINION',_'CELEX_IDENTIFIER',_'SECTOR_IDENTIFIER',_'NATURAL_NUMBER_(CELEX)',_'TYPE_OF_LEGAL_RESOURCE',_'YEAR_OF_THE_LEGAL_RESOURCE',_'WORK_CITES_WORK._CI_/_CJ',_'LEGACY_DATE_OF_CREATION_OF_WORK',_'DATE_OF_DOCUMENT',_'IDENTIFIER_OF_DOCUMENT',_'WORK_VERSION',_'LAST_CMR_MODIFICATION_DATE',_'CASE_LAW_HAS_CONCLUSIONS'

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
          'SECTOR IDENTIFIER', 'WORK CITES WORK. CI / CJ', 'WORK HAS RESOURCE TYPE', 'YEAR OF THE LEGAL RESOURCE']
data_to_drop = [i for i in all_data if i not in saving]


def create_csv(filepath, encoding="UTF8", data=None, filename="undefined.csv"):
    if data != "":
        csv_file = open(filepath, 'w', encoding=encoding)
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(COLS)
        csv_writer.writerows(data)
        csv_file.close()
        print("CSV file " + filename + " created in " + DIR_DATA_PROCESSED)
def read_json(file_path):
    with open(file_path, 'r') as f:
        json_data = json.loads(f.read())
    return json_data
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
            value = re.sub(r",", "_", str(value))
            # Remove HTML tags
            value = BeautifulSoup(value, "lxml").text

            for j in [j for j, x in enumerate(COLS) if x == title]:
                data[j] = value
        # data.insert(j-1, value)
        # print(j-1, value)

        final_data.append(data)
    return final_data
def get_citations(source_celex, cites_depth=1, cited_depth=1):
    """
    Gets all the citations one to X steps away. Hops can be specified as either
    the source document citing another (defined by `cites_depth`) or another document
    citing it (`cited_depth`). Any numbers higher than 1 denote that new source document
    citing a document of its own.

    This specific implementation does not care about intermediate steps, it simply finds
    anything X or fewer hops away without linking those together.
    """
    sparql = SPARQLWrapper('https://publications.europa.eu/webapi/rdf/sparql')
    sparql.setReturnFormat(JSON)
    sparql.setQuery('''
        prefix cdm: <http://publications.europa.eu/ontology/cdm#>
        prefix xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT DISTINCT * WHERE
        {
        {
            SELECT ?name2 WHERE {
                ?doc cdm:resource_legal_id_celex "%s"^^xsd:string .
                ?doc cdm:work_cites_work{1,%i} ?cited .
                ?cited cdm:resource_legal_id_celex ?name2 .
            }
        } UNION {
            SELECT ?name2 WHERE {
                ?doc cdm:resource_legal_id_celex "%s"^^xsd:string .
                ?cited cdm:work_cites_work{1,%i} ?doc .
                ?cited cdm:resource_legal_id_celex ?name2 .
            }
        }
        }''' % (source_celex, cites_depth, source_celex, cited_depth))
    try:
        ret = sparql.queryAndConvert()
    except:
        return get_citations(source_celex)
    targets = set()
    for bind in ret['results']['bindings']:
        target = bind['name2']['value']
        targets.add(target)
    targets = set([el for el in list(targets)])  # Filters the list. Filtertype: '3'=legislation, '6'=case law.

    return targets
def get_citations_csv(celex):
    endpoint = 'https://publications.europa.eu/webapi/rdf/sparql'
    input='", "'.join(celex)
    query = '''
           prefix cdm: <http://publications.europa.eu/ontology/cdm#>
 prefix xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT DISTINCT * WHERE
        {
        {
            SELECT ?celex ?citedD WHERE {
                ?doc cdm:resource_legal_id_celex ?celex
                 FILTER(STR(?celex) in ("%s")).
                ?doc cdm:work_cites_work{1,1} ?cited .
                ?cited cdm:resource_legal_id_celex ?citedD .
            }
        } UNION {
            SELECT ?celex ?citedD WHERE {
                ?doc cdm:resource_legal_id_celex ?celex
                 FILTER(STR(?celex) in ("%s")).
                ?cited cdm:work_cites_work{1,1} ?doc .
                ?cited cdm:resource_legal_id_celex ?citedD .
            }
        }
}
       ''' % (input,input)

    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(CSV)
    sparql.setMethod(POST)
    sparql.setQuery(query)
    try:
        ret = sparql.queryAndConvert()
    except:
        return get_citations_csv(celex)
    return ret.decode("utf-8")
def add_citations(data):
    name="WORK CITES WORK. CI / CJ"
    celex = data.loc[:, "CELEX IDENTIFIER"]
    all_csv = list()
    at_once = 1000
    for i in range(0, len(celex), at_once):
        new_csv = get_citations_csv(celex[i:(i + at_once)])
        all_csv.append(StringIO(new_csv))
    df = pd.concat(map(pd.read_csv, all_csv), ignore_index=True)
    celexes = pd.unique(df.loc[:, 'celex'])
    citations = pd.Series([], dtype='string')
    for celex in celexes:
        index = data[data['CELEX IDENTIFIER'] == celex].index.values
        cited = df[df['celex'] == celex].loc[:, "citedD"]
        string = "_".join(cited)
        citations[index[0]] = string
    data.pop(name)
    data.insert(1, name, citations)
def read_csv(file_path):
    try:
        data = pd.read_csv(file_path, sep=",", encoding='utf-8')
        # print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)
def get_summary_html(celex):
    if celex.startswith("6"):
        link = 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere_SUM&qid=1657547189758&from=EN#SM'
        sum_link = link.replace("cIdHere", celex)
        response = requests.get(sum_link)
        if response.status_code == 200:
            return response.text
        else:
            return "No summary available"
    elif celex.startswith("8"):
        link = 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=URISERV:cIdHere_SUMJURE&qid=1657547270514&from=EN'
        sum_link = link.replace("cIdHere", celex)
        response = requests.get(sum_link)
        if response.status_code == 200:
            return response.text
        else:
            return "No summary available"
def get_summary_from_html(html, starting):
    # This method turns the html code from the summary page into text
    # It has different cases depending on the first character of the CELEX ID
    # Should only be used for summaries extraction
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()  # rip it out
    text = soup.get_text()
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    text = text.replace(",", "_")
    if starting == "8":
        text = text.replace("JURE SUMMARY", "", 1)
        index = text.index("JURE SUMMARY")
        text = text[index:]
        text = text.replace("JURE SUMMARY", "")
        text = text.strip()
    elif starting == "6":
        try:
            text = text.replace("Summary", "nothing", 1)
            index = text.index("Summary")
            text = text[index:]
        except:
            print("Weird summary website found, returning entire text")
    return text
def get_keywords_from_html(html, starting):
    # This method turns the html code from the summary page into text
    # It has different cases depending on the first character of the CELEX ID
    # Should only be used for summaries extraction
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()  # rip it out
    text = soup.get_text()
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    text = text.replace(",", "_")
    if starting == "8":
        text = "No keywords available"
    elif starting == "6":
        try:
            text = text.replace("Summary", "nothing", 1)
            index = text.index("Summary")
            text = text.replace("Keywords", "nothing", 1)
            index2 = text.index("Keywords")
            text = text[index2:index]
        except:
            print("Weird summary website found, returning entire text")
            return text
    return get_words_from_keywords(text)
def get_words_from_keywords(text):
    words = text.split()
    result = list()
    for word in words:
        if "-" in word:
            result.extend(word.split(sep="-"))
    return "_".join(result)
def get_full_text_from_html(html):
    # This method turns the html code from the summary page into text
    # It has different cases depending on the first character of the CELEX ID
    # Should only be used for summaries extraction
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()  # rip it out
    text = soup.get_text()
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    text = text.replace(",", "_")
    return text
def add_summary_and_keywords(data):
    name = 'CELEX IDENTIFIER'
    Ids = data.loc[:, name]
    S1 = pd.Series([], dtype='string')
    S2 = pd.Series([], dtype='string')
    for i in range(len(Ids)):
        Id = Ids[i]
        summary = get_summary_html(Id)
        if summary != "No summary available":
            text = get_summary_from_html(summary, Id[0])
            text2 = get_keywords_from_html(summary,Id[0])
            S1[i] = text
            S2[i] = text2
        else:
            S1[i] = summary
            S2[i] = summary
    data.insert(1, "Summary", S1)
    data.inser(1,"Keywords",S2)
def add_keywords(data):
    name = 'CELEX IDENTIFIER'
    Ids = data.loc[:, name]
    S1 = pd.Series([], dtype='string')
    for i in range(len(Ids)):
        Id = Ids[i]
        summary = get_summary_html(Id)
        if summary != "No summary available":
            text = get_keywords_from_html(summary, Id[0])
            S1[i] = text
        else:
            S1[i] = summary
    data.insert(1, "Keywords", S1)
def add_fulltext(data):
    name = 'CELEX IDENTIFIER'
    Ids = data.loc[:, name]
    S1 = pd.Series([], dtype='string')
    for i in range(len(Ids)):
        html = get_html_by_celex_id(Ids[i])
        if "] not found." in html:
            # print(f"Full text not found for {Ids[i]}" )
            S1[i] = "No full text in english available"
        else:
            text = get_full_text_from_html(html)
            S1[i] = text
    data.insert(1, "Full Text", S1)
def add_sections(data):
    name = 'CELEX IDENTIFIER'
    Ids = data.loc[:, name]
    Summaries = pd.Series([], dtype='string')
    Keywords = pd.Series([], dtype='string')
    Full_text = pd.Series([], dtype='string')
    for i in range(len(Ids)):
        id = Ids[i]
        html = get_html_by_celex_id(id)
        summary = get_summary_html(id)
        if "] not found." in html:
            # print(f"Full text not found for {Ids[i]}" )
            Full_text[i] = "No full text in english available"
        else:
            text = get_full_text_from_html(html)
            Full_text[i] = text
        if summary != "No summary available":
            text = get_keywords_from_html(summary, id[0])
            text2 = get_summary_from_html(summary, id[0])
            Keywords[i] = text
            Summaries[i] = text2
        else:
            Keywords[i] = summary
            Summaries[i] = summary
    data.insert(1, "Full Text", Full_text)
    data.insert(1, "Keywords", Keywords)
    data.insert(1, "Summary", Summaries)
if __name__ == '__main__':
    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', "PROCESSED DIR")
    print('\n--- START ---\n')
    start: float = time.time()
    print("TRANSFORMING JSON INTO CSV")
    json_data = '';
    json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))
    global filepath
    for i in json_files:
        json_data = read_json(i)

        if json_data:
            final_data = json_to_csv(json_data)

            if final_data:
                if WINDOWS_SYSTEM:
                    i = windows_path(i)
                filename = i[i.rindex('/') + 1:].partition('.')[0] + ".csv"
                filepath = DIR_DATA_PROCESSED + "/" + filename
                create_csv(filepath=filepath, encoding="UTF8", data=final_data, filename=filename)
            else:
                print("Error creating CSV file. Data is empty.")
        else:
            print("Error reading json file. Please make sure json file exists and contains data.")
    print("CREATION OF CSV DONE")
    print("TRANSFORMATION OF CSV FILES IN DATA PROCESSED DIR STARTED")
    data=read_csv(filepath)
    print("REMOVING REDUNDANT COLUMNS AND NON-EU CASES")
    drop_columns(data, data_to_drop)
    print("ADDING CITATIONS IN CELEX FORMAT")
    add_citations(data)
    print("ADDING FULL TEXT, SUMMARY AND KEYWORDS")
    add_sections(data)
    data.to_csv(filepath.replace(".csv","_Processed_.csv"), index=False)
    print("WORK FINISHED SUCCESSFULLY!")
    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
