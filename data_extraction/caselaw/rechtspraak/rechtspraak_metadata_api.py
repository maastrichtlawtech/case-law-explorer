## DO NOT USE THIS FILE. WORK IS NOT YET FINISHED

import requests, json, xmltodict, pandas as pd, argparse
from datetime import date, datetime

from os.path import dirname, abspath
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_RECHTSPRAAK

# Check whether the API is working
def check_api(url):
    response = requests.get(f"{url}")

    # Return with the response code
    return response.status_code

def get_date(url):
    res = requests.get(url)
    res.raw.decode_content = True

    xpars = xmltodict.parse(res.text)
    json_string = json.dumps(xpars)
    json_object = json.loads(json_string)
    json_object = json_object['feed']['entry']

    return json_object

if __name__ == '__main__':
    # Define the base URL
    url = "https://data.rechtspraak.nl/uitspraken/zoeken?id=ECLI:NL:RBNHO:2022:3779"
    print("Rechtspraak metadata API")

    response_code = check_api(url)

    res = requests.get(url)
    res.raw.decode_content = True
    xpars = xmltodict.parse(res.text)
    json_string = json.dumps(xpars)
    json_object = json.loads(json_string)
    print(json_object)