import requests
from lxml import etree
import urllib.request
import rdflib
import os
import sys
from os.path import dirname, abspath, basename
sys.path.append(dirname(dirname(dirname(abspath(__file__)))))
import pandas as pd
from definitions.storage_handler import Storage, CSV_CASE_CITATIONS, CSV_LEGISLATION_CITATIONS, CSV_RS_CASES, \
    CSV_LIDO_ECLIS_FAILED, get_path_raw
from definitions.terminology.attribute_names import ECLI, LIDO_JURISPRUDENTIE, LIDO_WET, LIDO_ARTIKEL, LIDO_ARTIKEL_TITLE, \
    RS_RELATION, RS_DATE, LIDO_TYPE, LIDO_LABEL
from dotenv import load_dotenv
load_dotenv()
import datetime
import time

LIDO_ENDPOINT = os.getenv('LIDO_ENDPOINT')
LIDO_USERNAME = os.getenv('LIDO_USERNAME')
LIDO_PASSWORD = os.getenv('LIDO_PASSWORD')

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
    df_eclis = pd.read_csv(filename, usecols=['ecli'])
    df_eclis = df_eclis.reset_index(drop=True)

    eclis = list(df_eclis['ecli'])


    for i, ecli in enumerate(eclis):
            case_citations_incoming, case_citations_outgoing, legislation_citations = find_citations_for_case(remove_spaces_from_ecli(ecli)
                                                                        , case_citations_fieldnames,
                                                                                legislation_citations_fieldnames)
            need_to_write_saving_here = True
            # TODO dict of lists --> list of dicts, saving

            if (i + 1) % 100 == 0:
                print(f'{datetime.datetime.now().isoformat()}: {i + 1}/{len(eclis)} eclis processed.')

    print(f'{datetime.datetime.now().isoformat()}: {i + 1}/{len(eclis)} eclis processed.')


def add_citations_no_duplicates(already_existing_list,element):
    duplicate = False
    new_ecli = get_ecli(element)
    added_sth_new = True
    for stored in already_existing_list:
        if stored[LIDO_JURISPRUDENTIE] == new_ecli:
            added_sth_new = False
            duplicate = True
            break
    if not duplicate:
        already_existing_list.append({LIDO_JURISPRUDENTIE: new_ecli,
                                            LIDO_LABEL: element.attrib['label'],
                                            LIDO_TYPE: element.attrib['type'].split('/id/')[1],
                                            'keep1': element.attrib['type'].split('/id/')[
                                                         1] == 'lx-referentie',
                                            'keep2': get_ecli(element) not in str()})
    return added_sth_new
def add_legislations_no_duplicates(list,element):
    duplicate = False
    new_legislation = get_legislation_identifier(element)
    added_sth_new = True
    for legs in list:
        if new_legislation == legs:
            added_sth_new = False
            duplicate = True
            break
    if not duplicate:
        list.append(get_legislation_identifier(element))
    return added_sth_new

# Main method to execute LIDO API call on the ECLI code of the input case and extract the citations
def find_citations_for_case(ecli, case_citations_fieldnames, legislation_citations_fieldnames):
    xml_elements = []
    case_law_citations_outgoing = []
    legislation_citations = []
    case_law_citations_incoming = []
    start_page = 0
    end_of_pages = False
    outgoing = "uitgaande-links"
    incoming = "inkomende-links"

    while not end_of_pages:
        added_sth_new = True
        url = "{}?id={}&start={}&rows={}&output=xml".format(LIDO_ENDPOINT, get_lido_id(ecli), start_page, 100)
        start_page += 1

        xml_text = get_lido_response(url)
        xml_elements.append(etree.fromstring(xml_text.encode('utf8')))


        for el in xml_elements:

            for sub in list(el.iterchildren('subject')):

                for the_citations in sub.iterchildren(outgoing):
                    for sub_ref in the_citations.iterchildren():
                        if is_case_law(sub_ref):
                            added_sth_new = add_citations_no_duplicates(case_law_citations_outgoing,sub_ref)
                        elif is_legislation(sub_ref):
                            added_sth_new = add_legislations_no_duplicates(legislation_citations,sub_ref)

                for the_citations in sub.iterchildren(incoming):
                    for sub_ref in the_citations.iterchildren():
                        if is_case_law(sub_ref):
                            added_sth_new = add_citations_no_duplicates(case_law_citations_incoming, sub_ref)




        if not added_sth_new and start_page>10:
            end_of_pages = True

    # Remove duplicates empties

    for item in case_law_citations_incoming:
        if item[LIDO_JURISPRUDENTIE] == "":
            case_law_citations_incoming.remove(item)
    for item in case_law_citations_outgoing:
        if item[LIDO_JURISPRUDENTIE] == "":
            case_law_citations_outgoing.remove(item)


    # Remove input case ECLI (for some reason a case can cite itself...)
    for dicts in case_law_citations_incoming:
        if dicts[LIDO_JURISPRUDENTIE] == remove_spaces_from_ecli(ecli):
            case_law_citations_incoming.remove(dicts)
            break
    if (remove_spaces_from_ecli(ecli) in case_law_citations_incoming):
        case_law_citations_incoming.remove(remove_spaces_from_ecli(ecli))

    case_law_result_outgoing = extract_results_citations(case_law_citations_outgoing,ecli,case_citations_fieldnames)
    case_law_results_incoming = extract_results_citations(case_law_citations_incoming,ecli,case_citations_fieldnames)
    legislation_results = extract_results_legislations(legislation_citations,ecli,legislation_citations_fieldnames)

    return case_law_results_incoming, case_law_result_outgoing, legislation_results


def extract_results_citations(list,ecli,fields):
    case_law_result = {key: [] for key in fields}
    for case_citation in list:
        case_law_result[fields[0]].append(remove_spaces_from_ecli(ecli))  # Source ECLI
        case_law_result[fields[1]].append(
            remove_spaces_from_ecli(case_citation[LIDO_JURISPRUDENTIE]))  # Target ECLI
        case_law_result[fields[2]].append(case_citation['label'])  # Target ECLI
        case_law_result[fields[3]].append(case_citation['type'])  # Target ECLI
        case_law_result[fields[4]].append("")  # Target ECLI
        case_law_result[fields[5]].append(case_citation['keep1'])  # Target ECLI
        case_law_result[fields[6]].append(case_citation['keep2'])  # Target ECLI
    return case_law_result
def extract_results_legislations(list,ecli,fields):
    legislation_result = {key: [] for key in fields}
    for leg_citation in list:
        legislation_result[fields[0]].append(remove_spaces_from_ecli(ecli))  # Source ECLI
        legislation_result[fields[1]].append(leg_citation)  # Target article
        legislation_result[fields[2]].append(
            get_legislation_webpage(leg_citation))  # Target article webpage
        legislation_result[fields[3]].append(
            get_legislation_name(leg_citation))  # pref label == article name
        legislation_result[fields[4]].append("")  # date of decision of ecli
    return legislation_result

def run_citations_extraction_rechtspraak():
    start = time.time()
    input_path =  get_path_raw(CSV_RS_CASES)
    output_path_c_citations = get_path_raw(CSV_CASE_CITATIONS)
    output_path_l_citations = get_path_raw(CSV_LEGISLATION_CITATIONS)

    print('\n--- PREPARATION ---\n')
    print('INPUT/OUTPUT DATA STORAGE:\t', 'local')
    print('INPUT:\t\t\t\t', basename(input_path))
    print('OUTPUTS:\t\t\t', f'{basename(output_path_c_citations)}, {basename(output_path_l_citations)}\n')
    storage = Storage()
    storage.setup_pipeline(output_paths=[output_path_c_citations, output_path_l_citations], input_path=input_path)


    print('\n--- START ---\n')


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

    print(f"\nUpdating storage ...")


    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

if __name__ == '__main__':
    run_citations_extraction_rechtspraak()