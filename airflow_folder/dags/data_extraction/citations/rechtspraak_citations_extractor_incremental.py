import requests
from lxml import etree
import urllib.request
import rdflib
import os
import sys
from os.path import dirname, abspath, basename
sys.path.append(dirname(dirname(dirname(abspath(__file__)))))
import pandas as pd
from airflow_folder.dags.definitions.storage_handler import Storage, CSV_CASE_CITATIONS, CSV_LEGISLATION_CITATIONS, CSV_RS_INDEX, \
    CSV_LIDO_ECLIS_FAILED, get_path_raw
from airflow_folder.dags.definitions.terminology.attribute_names import ECLI, LIDO_JURISPRUDENTIE, LIDO_WET, LIDO_ARTIKEL, LIDO_ARTIKEL_TITLE, \
    RS_RELATION, RS_DATE, LIDO_TYPE, LIDO_LABEL
from dotenv import load_dotenv
load_dotenv()
import argparse
import datetime
import time


def remove_spaces_from_ecli(ecli):
    return ecli.replace(" ", "")


def write_incremental_rows(filename, data):
    with open(filename, 'a') as f:
        pd.DataFrame(data).to_csv(f, mode='a', header=not f.tell(), index=False)


# Code to execute LIDO API call
def get_lido_response(url):
    response = requests.get(url, auth=requests.auth.HTTPBasicAuth(LIDO_USERNAME, LIDO_PASSWORD))
    if response.status_code == 200:
        return response.text
    else:
        raise Exception('LinkedData responded with code {}: {}. {}'.format(response.status_code, response.reason, url))


# Extract the ECLI code from the LIDO identifier of the cited case law from the XML response from LIDO API
def get_ecli(sub_ref):
    return sub_ref.attrib['idref'].split('/')[-1]


# Extract the LIDO identifier of the cited legislation from the XML response from LIDO API
def get_legislation_identifier(sub_ref):
    return sub_ref.attrib['idref']


# Find the webpage expressing, in writing, the legislation referred to by the input LIDO identifier
def get_legislation_webpage(identifier):
    idcomponents = identifier.split("/")
    date = idcomponents[len(idcomponents) - 1]
    url = identifier
    page = urllib.request.urlopen(url)
    g = rdflib.Graph()
    g.parse(page, format="xml")
    article = ""
    for s, p, o in g:
        if str(p) == "http://purl.org/dc/terms/identifier":
            article = o
            if date in str(o):
                return o

    return article


def get_legislation_name(url):
    # turn the response into an xml tree
    xml_response = get_lido_response(url)
    xml = etree.fromstring(bytes(xml_response, encoding='utf8'))

    pref_label = ""
    title = ""
    # RDF main element (root)
    for element in xml.iterchildren():
        # there is only one child and it is the "description" in which the rest of the info is
        # go through all the tags (all the info)
        for el in element.iterchildren():
            # the title (same thing as the preLabel) is the feature we want to be using
            if el.tag == "{http://purl.org/dc/terms/}title":
                title = el.text

    return title


# Check if outgoing links in the XML response from the LIDO API are of type "Jurisprudentie" (case law)
def is_case_law(sub_ref):
    return sub_ref.attrib['groep'] == 'Jurisprudentie'


# Check if outgoing links in the XML response from the LIDO API are of type "Wet" (legislation)
def is_legislation(sub_ref):
    return sub_ref.attrib['groep'] == 'Wet' or sub_ref.attrib['groep'] == 'Artikel'


# Extract ECLI code of citation from a lido identifier.
# Example of a LIDO identifier "https://linkeddata.overheid.nl/terms/bwb/id/BWBR0020368/8655654/2016-08-11/2016-08-11"
def get_lido_id(ecli):
    return "http://linkeddata.overheid.nl/terms/jurisprudentie/id/" + ecli


# Method written by Marion
"""
These methods are used to write the citations incrementally to the csv file (in case it crashes or times out). 
It allows us to stop the script whenever we want without loosing our data, and without having to start from the bginning the next time. 
"""


# Main method to execute LIDO API call on a list of ECLIs from a CSV file and extract the citations of each
# Add the implementation of the incremental writing of rows
def find_citations_for_cases(filename, case_citations_output_filename, case_citations_fieldnames,
                             legislation_citations_output_filename, legislation_citations_fieldnames):
    df_eclis = pd.read_csv(filename, usecols=[ECLI, RS_DATE, RS_RELATION])
    df_eclis = df_eclis.sort_values(by='date_decision').reset_index(drop=True)

    eclis = list(df_eclis[ECLI])

    if os.getenv('SAMPLE_TEST') == 'TRUE':
        eclis = eclis[-10:]

    if citation_type == "inkomende-links":
        print("Fetching incoming citations from LIDO...")
    else:
        print("Fetching outgoing citations from LIDO...")

    for i, ecli in enumerate(eclis):
        date = datetime.date.fromisoformat(df_eclis[RS_DATE][i])
        relation = df_eclis[RS_RELATION][i]
        if date >= last_updated:
            try:
                case_citations, legislation_citations = find_citations_for_case(remove_spaces_from_ecli(ecli), date,
                                                                                relation, case_citations_fieldnames,
                                                                                legislation_citations_fieldnames)
                write_incremental_rows(filename=case_citations_output_filename, data=case_citations)
                write_incremental_rows(filename=legislation_citations_output_filename, data=legislation_citations)
            except Exception as e:
                print(f'{ecli} failed: {e}')
                write_incremental_rows(filename=get_path_raw(CSV_LIDO_ECLIS_FAILED),
                                       data={ECLI: [ecli], RS_DATE: [date], RS_RELATION: [relation]})
        if (i + 1) % 100 == 0:
            print(f'{datetime.datetime.now().isoformat()}: {i + 1}/{len(eclis)} eclis processed.')

    print(f'{datetime.datetime.now().isoformat()}: {i + 1}/{len(eclis)} eclis processed.')


# Main method to execute LIDO API call on the ECLI code of the input case and extract the citations
def find_citations_for_case(ecli, date, relation, case_citations_fieldnames, legislation_citations_fieldnames):
    global citation_type
    xml_elements = []
    case_law_citations = []

    legislation_citations = []
    start_page = 0
    end_of_pages = False
    while not end_of_pages:
        num_citations_before_api_call = len(case_law_citations)
        url = "{}?id={}&start={}&rows={}&output=xml".format(LIDO_ENDPOINT, get_lido_id(ecli), start_page, 100)
        start_page += 1
        xml_text = get_lido_response(url)
        xml_elements.append(etree.fromstring(xml_text.encode('utf8')))
        for el in xml_elements:
            # print(el.tag)
            # print(etree.tostring(el))
            for sub in list(el.iterchildren('subject')):
                # print(etree.tostring(sub))
                if citation_type == "uitgaande-links":
                    for the_citations in sub.iterchildren(citation_type):
                        for sub_ref in the_citations.iterchildren():
                            if is_case_law(sub_ref):
                                case_law_citations.append({LIDO_JURISPRUDENTIE: get_ecli(sub_ref),
                                                           LIDO_LABEL: sub_ref.attrib['label'],
                                                           LIDO_TYPE: sub_ref.attrib['type'].split('/id/')[1],
                                                           'keep1': sub_ref.attrib['type'].split('/id/')[
                                                                        1] == 'lx-referentie',
                                                           'keep2': get_ecli(sub_ref) not in str(relation)})
                            if is_legislation(sub_ref):
                                legislation_citations.append(get_legislation_identifier(sub_ref))
                else:
                    for the_citations in sub.iterchildren(citation_type):
                        for sub_ref in the_citations.iterchildren():
                            if is_case_law(sub_ref):
                                case_law_citations.append({LIDO_JURISPRUDENTIE: get_ecli(sub_ref),
                                                           LIDO_LABEL: sub_ref.attrib['label'],
                                                           LIDO_TYPE: sub_ref.attrib['type'].split('/id/')[1],
                                                           'keep1': sub_ref.attrib['type'].split('/id/')[
                                                                        1] == 'lx-referentie',
                                                           'keep2': get_ecli(sub_ref) not in str(relation)})
                    for the_other_citations in sub.iterchildren("uitgaande-links"):
                        for other_sub_ref in the_other_citations.iterchildren():
                            if is_legislation(other_sub_ref):
                                legislation_citations.append(get_legislation_identifier(other_sub_ref))

        # Remove duplicates
        # case_law_citations = list(set(case_law_citations))
        case_law_citations = [dict(t) for t in {tuple(d.items()) for d in case_law_citations}]
        if ((len(case_law_citations) == num_citations_before_api_call) and (len(case_law_citations) > 0)) or (
                (len(case_law_citations) == 0) and (start_page == 5)):
            end_of_pages = True

    # Remove duplicates
    # case_law_citations = list(set(case_law_citations))
    case_law_citations = [dict(t) for t in {tuple(d.items()) for d in case_law_citations}]
    for item in case_law_citations:
        if item[LIDO_JURISPRUDENTIE] == "":
            case_law_citations.remove(item)

    # Remove duplicates
    legislation_citations = list(set(legislation_citations))
    # Remove input case ECLI (for some reason a case can cite itself...)
    # if (remove_spaces_from_ecli(ecli) in case_law_citations):
    #    case_law_citations.remove(remove_spaces_from_ecli(ecli))

    case_law_result = {key: [] for key in case_citations_fieldnames}
    legislation_result = {key: [] for key in legislation_citations_fieldnames}

    for case_citation in case_law_citations:
        if not case_citation[LIDO_JURISPRUDENTIE] == remove_spaces_from_ecli(ecli):
            case_law_result[case_citations_fieldnames[0]].append(remove_spaces_from_ecli(ecli))  # Source ECLI
            case_law_result[case_citations_fieldnames[1]].append(
                remove_spaces_from_ecli(case_citation[LIDO_JURISPRUDENTIE]))  # Target ECLI
            case_law_result[case_citations_fieldnames[2]].append(case_citation['label'])  # Target ECLI
            case_law_result[case_citations_fieldnames[3]].append(case_citation['type'])  # Target ECLI
            case_law_result[case_citations_fieldnames[4]].append(relation)  # Target ECLI
            case_law_result[case_citations_fieldnames[5]].append(case_citation['keep1'])  # Target ECLI
            case_law_result[case_citations_fieldnames[6]].append(case_citation['keep2'])  # Target ECLI
            case_law_result[case_citations_fieldnames[7]].append(date)
            # date of decision of ECLI

    for leg_citation in legislation_citations:
        legislation_result[legislation_citations_fieldnames[0]].append(remove_spaces_from_ecli(ecli))  # Source ECLI
        legislation_result[legislation_citations_fieldnames[1]].append(leg_citation)  # Target article
        legislation_result[legislation_citations_fieldnames[2]].append(
            get_legislation_webpage(leg_citation))  # Target article webpage
        legislation_result[legislation_citations_fieldnames[3]].append(
            get_legislation_name(leg_citation))  # pref label == article name
        legislation_result[legislation_citations_fieldnames[4]].append(date)  # date of decision of ecli

    return case_law_result, legislation_result


start = time.time()

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
parser.add_argument('-f', '--failed', action='store_true', help='parse list of failed eclis instead of full list of eclis')
parser.add_argument('-i', '--incoming', action='store_true', help='fetch incoming citations instead of outgoing')
args = parser.parse_args()

input_path = get_path_raw(CSV_LIDO_ECLIS_FAILED) if args.failed else get_path_raw(CSV_RS_INDEX)
output_path_c_citations = get_path_raw(CSV_CASE_CITATIONS)
output_path_l_citations = get_path_raw(CSV_LEGISLATION_CITATIONS)

print('\n--- PREPARATION ---\n')
print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('INPUT:\t\t\t\t', basename(input_path))
print('OUTPUTS:\t\t\t', f'{basename(output_path_c_citations)}, {basename(output_path_l_citations)}\n')
storage = Storage(location=args.storage)
storage.setup_pipeline(output_paths=[output_path_c_citations, output_path_l_citations], input_path=input_path)
citation_type = "inkomende-links" if args.incoming else "uitgaande-links"
last_updated = storage.pipeline_last_updated
print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

print('\n--- START ---\n')

LIDO_ENDPOINT = os.getenv('LIDO_ENDPOINT')
LIDO_USERNAME = os.getenv('LIDO_USERNAME')
LIDO_PASSWORD = os.getenv('LIDO_PASSWORD')

case_citations_fieldnames = [ECLI, LIDO_JURISPRUDENTIE, LIDO_LABEL, LIDO_TYPE, RS_RELATION, 'keep1', 'keep2', RS_DATE]
legislation_citations_fieldnames = [ECLI, LIDO_WET, LIDO_ARTIKEL, LIDO_ARTIKEL_TITLE, RS_DATE]

#find citations, and save the file incrementally
find_citations_for_cases(input_path, output_path_c_citations, case_citations_fieldnames,
                         output_path_l_citations, legislation_citations_fieldnames)

print('Dropping duplicate legislation citations...')
# DROP DUPLICATES from the legislation citation table
legislation_citations = pd.read_csv(output_path_l_citations)
#print(legislation_citations.head())
#print("size leg before droping duplicates : "+str(legislation_citations.shape))
legislation_citations = legislation_citations.drop_duplicates()
#print("size leg after droping duplicates : " + str(legislation_citations.shape))
legislation_citations.to_csv(output_path_l_citations, index=False)

print(f"\nUpdating {args.storage} storage ...")
storage.finish_pipeline()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
