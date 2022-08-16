import glob, sys
from os.path import dirname, abspath
import pandas as pd
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_PROCESSED
from bs4 import BeautifulSoup
import requests
from eurlex  import get_html_by_celex_id
def read_csv(file_path):
    try:
        data = pd.read_csv(file_path,sep=",",encoding='utf-8')
        #print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)
def get_summary_html(celex):
    if celex.startswith("6"):
        link='https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere_SUM&qid=1657547189758&from=EN#SM'
        sum_link=link.replace("cIdHere",celex)
        response=requests.get(sum_link)
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
def get_summary_from_html(html,starting):
    # This method turns the html code from the summary page into text
    # It has different cases depending on the first character of the CELEX ID
    # Should only be used for summaries extraction
     soup = BeautifulSoup(html,"html.parser")
     for script in soup(["script", "style"]):
         script.extract()  # rip it out
     text = soup.get_text()
     # break into lines and remove leading and trailing space on each
     lines = (line.strip() for line in text.splitlines())
     # break multi-headlines into a line each
     chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
     # drop blank lines
     text = '\n'.join(chunk for chunk in chunks if chunk)
     text=text.replace(",","_")
     if starting =="8":
            text = text.replace("JURE SUMMARY","",1)
            index=text.index("JURE SUMMARY")
            text = text[index:]
            text = text.replace("JURE SUMMARY", "")
            text=text.strip()
     elif starting == "6":
         try:
            text=text.replace("Summary","nothing",1)
            index=text.index("Summary")
            text=text[index:]
         except:
             print("Weird summary website found, returning entire text")
     return text
def get_keywords_from_html(html,starting):
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
        text="No keywords available"
    elif starting == "6":
        try:
            text = text.replace("Summary", "nothing", 1)
            index = text.index("Summary")
            text=text.replace("Keywords","nothing",1)
            index2=text.index("Keywords")
            text = text[index2:index]
        except:
            print("Weird summary website found, returning entire text")
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
    text=text.replace(",","_")
    return text
def add_summary(data):

    name='CELEX IDENTIFIER'
    Ids= data.loc[:,name]
    S1 = pd.Series([],dtype='string')

    for i in range(len(Ids)):
        Id=Ids[i]
        summary=get_summary_html(Id)
        if summary !="No summary available":
            text = get_summary_from_html(summary,Id[0])
            S1[i]=text
        else:
            S1[i]=summary
    data.insert(1,"Summary", S1)
def add_keywords(data):
    name = 'CELEX IDENTIFIER'
    Ids = data.loc[:, name]
    S1 = pd.Series([],dtype='string')
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
    S1 = pd.Series([],dtype='string')
    for i in range(len(Ids)):
        html = get_html_by_celex_id(Ids[i])
        if "] not found." in html:
            #print(f"Full text not found for {Ids[i]}" )
            S1[i]="No full text in english available"
        else:
            text=get_full_text_from_html(html)
            S1[i]=text
    data.insert(1, "Full Text", S1)
def add_sections(data):
    name = 'CELEX IDENTIFIER'
    Ids = data.loc[:, name]
    Summaries = pd.Series([],dtype='string')
    Keywords = pd.Series([],dtype='string')
    Full_text = pd.Series([],dtype='string')
    for i in range(len(Ids)):
        id=Ids[i]
        html = get_html_by_celex_id(id)
        summary=get_summary_html(id)
        if "] not found." in html:
            #print(f"Full text not found for {Ids[i]}" )
            Full_text[i]="No full text in english available"
        else:
            text=get_full_text_from_html(html)
            Full_text[i]=text
        if summary != "No summary available":
            text = get_keywords_from_html(summary, id[0])
            text2 = get_summary_from_html(summary,id[0])
            Keywords[i] = text
            Summaries[i] = text2
        else:
            Keywords[i] = summary
            Summaries[i]=summary
    data.insert(1, "Full Text", Full_text)
    data.insert(1, "Keywords",Keywords)
    data.insert(1, "Summary", Summaries)

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