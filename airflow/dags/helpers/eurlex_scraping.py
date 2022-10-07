import pandas as pd
from bs4 import BeautifulSoup
import requests
from eurlex import get_html_by_celex_id
import time
from dotenv import load_dotenv
load_dotenv()
import os
"""
Method for detecting code-words for case law directory codes for cellar.
"""
LINK_SUMMARY_INF=os.getenv('EURLEX_SUMMARY_LINK_INF')
LINK_SUMJURE=os.getenv('EURLEX_SUMJURE_LINK')
CELEX_SUBSTITUTE=os.getenv('CELEX_SUBSTITUTE')
LINK_SUMMARY=os.getenv('EURLEX_SUMMARY_LINK')
def is_code(word):
    return word.replace(".", "0").replace("-", "0")[1:].isdigit()


"""
Wrapped method for requests.get().
After 5 retries, it gives up and returns a "404" string.
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
Cellar specific, works for celex id's starting a 6 and 8.
"""


def get_summary_html(celex):
    if ";" in celex:
        idss = celex.split(";")
        for idsss in idss:
            if "_" in idsss:
                celex = idsss
    else:
        celex = celex
    celex = celex.replace(" ", "")
    if celex.startswith("6"):
        if "INF" in celex:
            link = LINK_SUMMARY_INF
        else:
            link = LINK_SUMMARY
        sum_link = link.replace(CELEX_SUBSTITUTE, celex)
        response = response_wrapper(sum_link)
        try:
            if response.status_code == 200:
                return response.text
            else:
                return "No summary available"
        except Exception:
            return "No summary available"
    elif celex.startswith("8"):
        link = LINK_SUMJURE
        sum_link = link.replace(CELEX_SUBSTITUTE, celex)
        response = response_wrapper(sum_link)
        if response.status_code == 200:
            return response.text
        else:
            return "No summary available"


"""
Method used to extract the summary from a html page.
Cellar specific, uses get_words_from_keywords.
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
Cellar specific, uses get_words_from_keywords.
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
They keywords on the page are always separated by " - " or other types of dashes.

"""


def get_words_from_keywords_em(text):
    lines = text.split(sep="\n")
    returner = set()
    for line in lines:
        if "—" in line:
            line = line.replace('‛', "")
            line = line.replace("(", "")
            line = line.replace(")", "")
            returner.update(line.split(sep="—"))
        elif "–" in line:
            line = line.replace('‛', "")
            line = line.replace("(", "")
            line = line.replace(")", "")
            returner.update(line.split(sep="–"))
        elif " - " in line:
            line = line.replace('‛', "")
            line = line.replace("(", "")
            line = line.replace(")", "")
            returner.update(line.split(sep=" - "))
    return ";".join(returner)
"""
One of the older method for keywords extraction. Not used, left in case of future usability.
"""

def add_lines(list, start, fragment):
    fragment = fragment.replace((str(start)) + ".", "")
    fragment = fragment.replace((str(start)) + " .", "")
    fragment = fragment.replace("\n", " ")
    fragment = fragment.replace("Summary", "")
    if "(" in fragment:
        index = fragment.find("(")
        fragment = fragment[:index]
    if "–" in fragment:
        words_new = fragment.split(sep=" – ")
    elif "-" in fragment:
        words_new = fragment.split(sep=" - ")
    else:
        print(fragment)
        words_new = []
    list.update(words_new)

"""
One of the older method for keywords extraction. Not used, left in case of future usability.
"""
def get_words_from_keywords_old(text):
    lines = text.split(sep='\n')
    returner = set()
    starting = 1
    current = 1
    number = 1
    fragment = ""
    for line in lines:
        if (str(starting) + ".") in line or (str(starting) + " .") in line:
            if current == 1:
                number = current
                current += 1
                fragment = line

            else:
                return ";".join(returner)
        elif (str(current) + ".") in line or (str(current) + " .") in line:
            current += 1
            add_lines(returner, number, fragment)
            fragment = line
        else:
            fragment += line
"""
Main method for extracting keywords from the main text.
"""

def get_words_from_keywords(text):
    if "Keywords" in text:
        try:
            index = text.find("Keywords")
            if "Summary" in text[index:index + 25]:
                text2 = text.replace("Summary", "", 1)
                try:
                    indexer = text2.find("Summary")
                    text = text[index:indexer]
                except Exception:
                    text = text
        except Exception:
            text = text
    else:
        if "Summary" in text:
            index = text.find("Summary")
            text = text[:index]
    return get_words_from_keywords_em(text)
        # return get_words_from_keywords_old(text)


"""
  This method turns the html code from the summary page into text.
  It has different cases depending on the first character of the CELEX ID.
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
    sum_link = link.replace(CELEX_SUBSTITUTE, celex)
    response = response_wrapper(sum_link)
    try:
        if response.status_code == 200:
            return response.text
        else:
            return "No data available"
    except Exception:
        return "No data available"


"""
This Method gets the subject matter from a fragment of code containing them.
Used for extracting subject matter for cellar cases only.
"""


def get_subject(text):
    try:
        index_matter = text.index("Subject matter:")
        try:
            index_end = text.index("Case law directory code:")  # if this fails then miscellaneous
        except Exception:
            index_end = text.index("Miscellaneous information")
        extracting = text[index_matter + 16:index_end]
        subject_mat = extracting.split(sep="\n")
        subject = ";".join(subject_mat)
        subject = subject[:len(subject) - 1]
    except Exception:
        subject = ""
    return subject


"""
This Method extracts all eurovocs, from a fragment containing them.
Used for extracting eurovoc for cellar cases.
"""


def get_eurovoc(text):
    try:
        start = text.find("EUROVOC")
        try:
            ending = text.find("Subject matter")
        except Exception:
            try:
                ending = text.find("Directory code")
            except Exception:
                try:
                    ending = text.find("Miscellaneous information")
                except Exception:
                    ending = start
        if ending is start:
            return ""
        else:
            text = text[start:ending]
            texts = text.split("\n")
            lists = []
            for t in texts:
                if "EUROVOC" not in t and t != "":
                    lists.append(t)
            return ";".join(lists)
    except Exception:
        return ""


"""
Method for getting all of the case directory codes for each cellar case.
Extracts them from a string containing the eurlex website containing all document information.
"""


def get_codes(text):
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
        code = ";".join(codes_result)
    except Exception:
        code = ""
    return code
