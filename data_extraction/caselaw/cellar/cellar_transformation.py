import csv
import glob
import json
import threading
import time
import warnings
import sys
from SPARQLWrapper import SPARQLWrapper, JSON, CSV, POST
import requests
from io import StringIO
from os.path import dirname, abspath
import re
from bs4 import BeautifulSoup
from definitions.storage_handler import CELLAR_DIR, DIR_DATA_PROCESSED
import pandas as pd
from eurlex import get_html_by_celex_id

warnings.filterwarnings("ignore")
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))

WINDOWS_SYSTEM = False

if sys.platform == "win32":
    WINDOWS_SYSTEM = True

"""
Reads a csv file and returns it.
"""


def read_csv(file_path):
    try:
        data = pd.read_csv(file_path, sep=",", encoding='utf-8')
        # print(data)
        return data
    except Exception:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)


"""
Method used to remove unnecessary columns from a dataframe.
"""


def drop_columns(data, columns):
    for i in range(len(columns)):
        try:
            data.pop(columns[i])
        except Exception:
            print(f"Column titled {columns[i]} does not exist in the file!")
    data.drop(data[-data.ECLI.str.contains("ECLI:EU")].index, inplace=True)
    data.reset_index(drop=True, inplace=True)


"""
Method used to fix a problem on windows systems, where the forward slashes need to be replaced.
"""


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
        print("CSV file " + filename + " created in " + DIR_DATA_PROCESSED)


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
            value = re.sub(r",", "_", str(value))
            # Remove HTML tags
            value = BeautifulSoup(value, "lxml").text

            for j in [j for j, x in enumerate(COLS) if x == title]:
                data[j] = value
        # data.insert(j-1, value)
        # print(j-1, value)

        final_data.append(data)
    return final_data


"""
Method acquired from a different law and tech project for getting the citations of a source_celex.
Unlike get_citations_csv, only works for one source celex at once. Returns a set containing all the works cited by
the source celex."""


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
        prefix cdm: <https://publications.europa.eu/ontology/cdm#>
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
    except Exception:
        return get_citations(source_celex)
    targets = set()
    for bind in ret['results']['bindings']:
        target = bind['name2']['value']
        targets.add(target)
    targets = set([el for el in list(targets)])  # Filters the list. Filter type: '3'=legislation, '6'=case law.

    return targets


"""
Method sending a query to the endpoint, which asks for cited works for each celex.
The celex variable in the method is a list of all the celex identifiers of the cases we need the citations of.
The query returns a csv, containing all of the data needed."""


def get_citations_csv(celex):
    endpoint = 'https://publications.europa.eu/webapi/rdf/sparql'
    input_celex = '", "'.join(celex)
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
       ''' % (input_celex, input_celex)

    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(CSV)
    sparql.setMethod(POST)
    sparql.setQuery(query)
    try:
        ret = sparql.queryAndConvert()
    except Exception:
        return get_citations_csv(celex)
    return ret.decode("utf-8")


"""
Method used by separate threads for the multi-threading method of adding citations to the dataframe
Sends a query which returns a csv file containing the the celex identifiers of cited works for each case.
Works with multi-case queries, at_once is the variable deciding for how many cases are used with each query.
"""


def execute_citations(csv_list, citations):
    at_once = 1000
    for i in range(0, len(citations), at_once):
        new_csv = get_citations_csv(citations[i:(i + at_once)])
        csv_list.append(StringIO(new_csv))


"""
This method replaces replaces the column with citations.

Old column -> links to cited works
New column -> celex identifiers of cited works

It uses multithreading, which is very much recommended.
Uses a query to get the citations in a csv format from the endpoint. * 

* More details in the query method.
"""


def add_citations(data, threads):
    name = "WORK CITES WORK. CI / CJ"
    celex = data.loc[:, "CELEX IDENTIFIER"]
    length = celex.size
    at_once_threads = int(length / threads)
    all_csv = list()
    threads = []
    for i in range(0, length, at_once_threads):
        curr_celex = celex[i:(i + at_once_threads)]
        t = threading.Thread(target=execute_citations, args=(all_csv, curr_celex))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    df = pd.concat(map(pd.read_csv, all_csv), ignore_index=True)
    celexes = pd.unique(df.loc[:, 'celex'])
    citations = pd.Series([], dtype='string')
    for celex in celexes:
        index = data[data['CELEX IDENTIFIER'] == celex].index.values
        cited = df[df['celex'] == celex].loc[:, "citedD"]
        string = "_".join(cited)
        citations[index[0]] = string
    data.pop(name)
    citations.sort_index(inplace=True)
    data.insert(1, name, citations)


"""
Wrapped method for requests.get()
After 5 retries, it gives up and returns a "404" string
"""


def response_wrapper(link, num=1):
    if num == 5:
        return "404"
    try:
        response = requests.get(link)
        return response
    except Exception:
        time.sleep(0.5 * num)
        return response_wrapper(id, num + 1)


"""
This method returns the html of a summary page.
Cellar specific, works for celex id's starting a 6 and 8
"""


def get_summary_html(celex):
    if celex.startswith("6"):
        link = 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere_SUM&qid=1657547189758&from=EN#SM'
        sum_link = link.replace("cIdHere", celex)
        response = response_wrapper(sum_link)
        try:
            if response.status_code == 200:
                return response.text
            else:
                return "No summary available"
        except Exception:
            return "No summary available"
    elif celex.startswith("8"):
        link = 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=URISERV:cIdHere_SUMJURE&qid=1657547270514' \
               '&from=EN '
        sum_link = link.replace("cIdHere", celex)
        response = response_wrapper(sum_link)
        if response.status_code == 200:
            return response.text
        else:
            return "No summary available"


"""
Method used to extract the summary from a html page.
Cellar specific, uses get_words_from_keywords
Currently only walking for celex id's starting with a 6 ( EU cases).
"""


def get_summary_from_html(html, starting):
    # This method turns the html code from the summary page into text
    # It has different cases depending on the first character of the CELEX ID
    # Should only be used for summaries extraction
    text = get_full_text_from_html(html)
    if starting == "8":
        text2 = text.replace("JURE SUMMARY", "", 1)
        index = text2.index("JURE SUMMARY")
        text2 = text2[index:]
        text2 = text2.replace("JURE SUMMARY", "")
        text2 = text2.strip()
        return text2
    elif starting == "6":
        try:
            text2 = text.replace("Summary", "nothing", 1)
            index = text2.index("Summary")
            text2 = text2[index:]
            return text2
        except Exception:
            return text
            # print("Weird summary website found, returning entire text")
    return text


"""
Method used to extract the keywords from a html page.
Cellar specific, uses get_words_from_keywords
"""


def get_keywords_from_html(html, starting):
    # This method turns the html code from the summary page into text
    # It has different cases depending on the first character of the CELEX ID
    # Should only be used for summaries extraction
    text = get_full_text_from_html(html)
    if starting == "8":
        text = "No keywords available"
        return text
    elif starting == "6":
        return get_words_from_keywords(text)


"""
This method tries to extract only they keywords from a part of html page containing it.
They keywords on the page are always separated by " - ".

**THIS METHOD COULD BE VERY MUCH IMPROVED**

Currently it only gets the "edge" words from the keywords.
Example:

input text : Crime rates - Potato and carrot prices - Labour costs
output keywords: rates_Potato_prices_Labour

"""


def get_words_from_keywords(text):
    text = text.replace(" - ", "-")
    words = text.split()
    result = set()
    for word in words:
        if "-" in word:
            result.update(word.split(sep="-"))
    return "_".join(result)


"""
  This method turns the html code from the summary page into text
  It has different cases depending on the first character of the CELEX ID
  Universal method, also replaces all "," with "_".
"""


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


"""
Separate method for adding the keywords and the summary to a dataframe.
"""


def add_summary_and_keywords(data):
    name = 'CELEX IDENTIFIER'
    ids = data.loc[:, name]
    s1 = pd.Series([], dtype='string')
    s2 = pd.Series([], dtype='string')
    for i in range(len(ids)):
        id = ids[i]
        summary = get_summary_html(id)
        if summary != "No summary available":
            text = get_summary_from_html(summary, id[0])
            text2 = get_keywords_from_html(summary, id[0])
            s1[i] = text
            s2[i] = text2
        else:
            s1[i] = summary
            s2[i] = summary
    data.insert(1, "Summary", s1)
    data.inser(1, "Keywords", s2)


"""
Separate method for adding the keywords to a dataframe.
"""


def add_keywords(data):
    name = 'CELEX IDENTIFIER'
    ids = data.loc[:, name]
    s1 = pd.Series([], dtype='string')
    for i in range(len(ids)):
        id = ids[i]
        summary = get_summary_html(id)
        if summary != "No summary available":
            text = get_keywords_from_html(summary, id[0])
            s1[i] = text
        else:
            s1[i] = summary
    data.insert(1, "Keywords", s1)


"""
Separate method for adding the full text to a dataframe.
"""


def add_fulltext(data):
    name = 'CELEX IDENTIFIER'
    ids = data.loc[:, name]
    s1 = pd.Series([], dtype='string')
    for i in range(len(ids)):
        html = get_html_by_celex_id_wrapper(ids[i])
        if "] not found." in html:
            # print(f"Full text not found for {Ids[i]}" )
            s1[i] = "No full text in english available"
        else:
            text = get_full_text_from_html(html)
            s1[i] = text
    data.insert(1, "Full Text", s1)


"""
This method is a wrapped for the get_html_by_celex_id method imported from eurlex.
Sometimes thew websites do not load because of too many connections at once,
this method waits a bit and tries again for up to 5 tries.
"""


def get_html_by_celex_id_wrapper(id, num=1):
    if num == 5:
        return "404"
    try:
        html = get_html_by_celex_id(id)
        return html
    except Exception:
        time.sleep(0.5 * num)
        return get_html_by_celex_id_wrapper(id, num + 1)


"""
Method which could (but is not) currently used to a multi-threading approach where they all add data to a single pandas
Series. 15 threads adding data to one object doesnt work out well, this method is a quick low effort fix.
"""


def put_data_in_threads(list, index, data):
    try:
        list[index] = data
    except Exception:
        time.sleep(0.2)
        # print(f"trying to put in went wrong, trying again in  {threading.currentThread().getName()}")
        put_data_in_threads(list, index, data)


"""
This method gets the page containing all document details for extracting the subject matter and
the case law directory codes. Uses the celex identifier of a case.
"""


def get_entire_page(celex):
    link = 'https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:cIdHere'
    sum_link = link.replace("cIdHere", celex)
    response = response_wrapper(sum_link)
    try:
        if response.status_code == 200:
            return response.text
        else:
            return "No data available"
    except Exception:
        return "No data available"


"""
This is the method executed by individual threads by the add_sections method.

The big dataset is divided in parts, each thread gets its portion of work to do.
They add their portions of columns to corresponding lists, 
after all the threads are done the individual parts are put together.
"""


def execute_sections_threads(celex, start, list_sum, list_key, list_full, list_subject, list_codes):
    sum = pd.Series([], dtype='string')
    key = pd.Series([], dtype='string')
    full = pd.Series([], dtype='string')
    subject_matter = pd.Series([], dtype='string')
    case_codes = pd.Series([], dtype='string')
    for i in range(len(celex)):
        j = start + i
        id = celex[j]
        html = get_html_by_celex_id_wrapper(id)
        if html != "404":

            if "] not found." in html:
                # print(f"Full text not found for {Ids[i]}" )
                full[j] = "No full text in english available"
                # put_data_in_threads(full,j,"No full text in english available")
            else:
                text = get_full_text_from_html(html)
                full[j] = text

        summary = get_summary_html(id)  # put_data_in_threads(full,j,text)
        if summary != "No summary available":
            text = get_keywords_from_html(summary, id[0])
            text2 = get_summary_from_html(summary, id[0])
            key[j] = text
            sum[j] = text2
            # put_data_in_threads(key,j,text)
            # put_data_in_threads(sum, j, text2)
        else:
            key[j] = summary
            sum[j] = summary
            # put_data_in_threads(key, j, summary)
            # put_data_in_threads(sum, j, summary)
        entire_page = get_entire_page(id)
        text = get_full_text_from_html(entire_page)
        if entire_page != "No data available":
            try:
                index_matter = text.index("Subject matter:")
                try:
                    index_end = text.index("Case law directory code:")  # if this fails then miscellaneous
                except Exception:
                    index_end = text.index("Miscellaneous information")
                extracting = text[index_matter + 16:index_end]
                subject_mat = extracting.split(sep="\n")
                subject = "_".join(subject_mat)
                subject = subject[:len(subject) - 1]
            except Exception:
                subject = ""
            try:
                index_codes = text.index("Case law directory code:")
                index_end = text.index("Miscellaneous information")
                extracting = text[index_codes + 20:index_end]
                extracting = extracting.rstrip()
                words = extracting.split()
                codes = [x for x in words if is_code(x)]
                codes_full = list(set(codes))
                codes_result = list()
                indexes = [extracting.find(x) for x in codes_full]
                for x in range(len(codes_full)):
                    done = False
                    index_start = indexes[x]
                    getting_ending = extracting[index_start:]
                    words_here = getting_ending.split()

                    for words in words_here:

                        if words is not words_here[0]:

                            if is_code(words):
                                ending = getting_ending[2:].find(words)
                                done = True
                                break

                    if done:
                        code_text = getting_ending[:ending]
                    else:
                        code_text = getting_ending

                    codes_result.append(code_text.replace("\n", ""))
                code = "_".join(codes_result)
            except:
                code = ""
        else:
            code = ""
            subject = ""
        subject_matter[j] = subject
        case_codes[j] = code
    list_sum.append(sum)
    list_key.append(key)
    list_full.append(full)
    list_codes.append(case_codes)
    list_subject.append(subject_matter)


"""
This method adds the following sections to a pandas dataframe, as separate columns:

Full Text
Case law directory codes
Subject matter
Keywords
Summary

Method is cellar-specific, scraping html from https://eur-lex.europa.eu/homepage.html.
It operates with multiple threads, using that feature is recommended as it speeds up the entire process.
"""


def add_sections(data, threads):
    name = 'CELEX IDENTIFIER'
    celex = data.loc[:, name]
    summaries = pd.Series([], dtype='string')
    keywords = pd.Series([], dtype='string')
    full_text = pd.Series([], dtype='string')
    codes = pd.Series([], dtype='string')
    subject_matter = pd.Series([], dtype='string')
    at_once_threads = int(celex.size / threads)
    length = celex.size
    threads = []
    list_sum = list()
    list_key = list()
    list_full = list()
    list_codes = list()
    list_subject = list()
    for i in range(0, length, at_once_threads):
        curr_celex = celex[i:(i + at_once_threads)]
        t = threading.Thread(target=execute_sections_threads,
                             args=(curr_celex, i, list_sum, list_key, list_full, list_subject, list_codes))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for l in list_sum:
        summaries = summaries.append(l)
    for l in list_key:
        keywords = keywords.append(l)
    for l in list_full:
        full_text = full_text.append(l)
    for l in list_codes:
        codes = codes.append(l)
    for l in list_subject:
        subject_matter = subject_matter.append(l)
    full_text.sort_index(inplace=True)
    summaries.sort_index(inplace=True)
    keywords.sort_index(inplace=True)
    codes.sort_index(inplace=True)
    subject_matter.sort_index(inplace=True)
    data.insert(1, "Subject matter", subject_matter)
    data.insert(1, "Case law directory codes", codes)
    data.insert(1, "Full Text", full_text)
    data.insert(1, "Keywords", keywords)
    data.insert(1, "Summary", summaries)


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
    json_data = read_json(filepath)
    if json_data:
        final_data = json_to_csv(json_data)
        if final_data:
            if WINDOWS_SYSTEM:
                filepath = windows_path(filepath)
            filename = filepath[filepath.rindex('/') + 1:].partition('.')[0] + ".csv"
            filepath = DIR_DATA_PROCESSED + "/" + filename
            create_csv(filepath=filepath, encoding="UTF8", data=final_data, filename=filename)
        else:
            print("Error creating CSV file. Data is empty.")
    else:
        print("Error reading json file. Please make sure json file exists and contains data.")
    print("CREATION OF CSV DONE")
    print("TRANSFORMATION OF CSV FILES IN DATA PROCESSED DIR STARTED")
    data = read_csv(filepath)
    print("REMOVING REDUNDANT COLUMNS AND NON-EU CASES")
    drop_columns(data, data_to_drop)
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


def is_code(word):
    return word.replace(".", "0").replace("-", "0")[1:].isdigit()


if __name__ == '__main__':
    print("Welcome to cellar transformation!")
    json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))
    for file in json_files:
        print(f"\nFound file {file}")
        print("\nShould this file be transformed? Answer Y/N please.")
        answer = str(input())
        if answer == "Y":
            transform_file(file)
