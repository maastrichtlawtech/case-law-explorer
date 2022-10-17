"""

This file is purely a testing file for trying out separate parts of code, testing if everything works and such.
Can be also used to develop future code.

Current main usage - Setting up Storage -> Setting up all the folders in root directory.



"""



import requests
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

   """
   CELEXES FOR TESTING USE
   62021CO0659
   62020CO0099
   62021CO0221
   They all have keywords and a summary
   """

   celex="62021CO0659"
   username=os.getenv("EURLEX_WEBSERVICE_USERNAME")
   password=os.getenv("EURLEX_WEBSERVICE_PASSWORD")
   celexes=["62021CO0659","62020CO0099","62021CO0221"]
   response = get_keywords_from_celexes(celexes,username,password)



   b=2
