"""

This file is purely a testing file for trying out separate parts of code, testing if everything works and such.
Can be also used to develop future code.

Current main usage - Setting up Storage -> Setting up all the folders in root directory.



"""





from helpers.csv_manipulator import *
from helpers.citations_adder import *
from helpers.fulltext_saving import *
from helpers.json_to_csv import *
from helpers.sparql import *
from definitions.storage_handler import Storage
if __name__ == '__main__':

    #link = "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:52018IP0428&qid=1662057930872"
    #html=response_wrapper(link)
   # text = get_full_text_from_html(html.text)
    #print(get_eurovoc(text))
    storage=Storage("local")