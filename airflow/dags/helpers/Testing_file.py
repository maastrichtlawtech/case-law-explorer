"""

This file is purely a testing file for trying out separate parts of code, testing if everything works and such.
Can be also used to develop future code.

Current main usage - Setting up Storage -> Setting up all the folders in root directory.



"""





from helpers.csv_manipulator import *
from helpers.citations_adder import *
from helpers.fulltext_saving import *
from helpers.eurlex_scraping import *
from helpers.json_to_csv import *
from helpers.sparql import *
from definitions.storage_handler import Storage
if __name__ == '__main__':

    link = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:62000CJ0136_SUM&qid=1657547189758&from=EN#SM"
    html=response_wrapper(link)
    text = get_full_text_from_html(html.text)
    b=2
    #storage=Storage("local")