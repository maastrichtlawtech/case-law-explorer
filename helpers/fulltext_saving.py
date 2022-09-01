import glob, sys
from os.path import dirname, abspath
import pandas as pd
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_PROCESSED
from bs4 import BeautifulSoup
import requests
from eurlex  import get_html_by_celex_id
import time
import threading
from helpers.json_to_csv import read_csv


def is_code(word):
    return word.replace(".", "0").replace("-", "0")[1:].isdigit()


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


if __name__ == '__main__':
    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")
    for i in range(len(csv_files)):
        if ("Extracted" in csv_files[i]):
            print("")
            print(f"WORKING ON  {csv_files[i]} ")
            data = read_csv(csv_files[i])
            #add_sections(data)
            add_keywords(data)
            data.to_csv(csv_files[i].replace("Extracted","With Summary"), index=False)
    print("WORK FINISHED SUCCESSFULLY!")