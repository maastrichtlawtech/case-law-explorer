"""

This file is purely a testing file for trying out separate parts of code, testing if everything works and such.
Can be also used to develop future code.

Current main usage - Setting up Storage -> Setting up all the folders in root directory.



"""




from dotenv import load_dotenv
load_dotenv()
from helpers.csv_manipulator import *
from helpers.citations_adder import *
from helpers.fulltext_saving import *
from helpers.eurlex_scraping import *
from helpers.json_to_csv import *
from helpers.sparql import *
from definitions.storage_handler import Storage


def get_html_by_celex_id(id):
    link = os.getenv("EURLEX_FULL_TEXT")
    ids = id.split(";")
    final=""
    if len(ids) > 1:
        for id_s in ids:
            if "INF" not in id_s:
                final=id_s
                break
    final = final.replace(" ","")
    final_link=link.replace(CELEX_SUBSTITUTE,final)
    return requests.get(final_link)


if __name__ == '__main__':

    #link = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:62000CJ0136_SUM&qid=1657547189758&from=EN#SM"
    #html=response_wrapper(link)
    #text = get_full_text_from_html(html.text)
    #b=2
    hey= get_html_by_celex_id("62020CO0099_INF; 62020CO0099")
    b=2
    #storage=Storage("local")