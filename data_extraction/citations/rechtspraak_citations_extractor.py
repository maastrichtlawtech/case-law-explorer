import requests
from lxml import etree
import urllib.request
import rdflib
import os
import sys
import csv

def is_valid_ecli_code(ecli):
    ecli_code = ecli.replace(" ","")                        # Remove spaces
    ecli_components = ecli_code.split(":")                  # Split the ECLI into components 
    if ("." in input_eclis or len(ecli_components) != 5):   # Each ECLI has exactly 5 components (and does not have a full stop - this probably indicates a file name)
        return False
    if (ecli_components[0].lower() == 'ecli'):              # The first part of an ECLI is "ECLI"
        return True
    else:
        return False

def remove_spaces_from_ecli(ecli):
    return ecli.replace(" ","")

def is_valid_csv_file_name(filename):
    return input_eclis[-4:].lower() == ".csv"               # CSV filename should end in ".csv"

def write_data_to_csv(filename,data):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)


if len(sys.argv) != 5:                                      # At least 4 arguments should be specified (excluding the script name)
    print()
    print("Incorrect number of arguments! Exactly 4 required:")
    print()
    print("1. lido-api-username,")
    print("2. lido-api-password,")
    print("3. 's' or 'm' ('s' means single ECLI, 'm' means multiple ECLIs),")
    print("4. If argument 3 is 's' then supply a single ECLI code. If argument 3 is 'm' then supply a path to a CSV file which lists the ECLI codes (each on a separate line).")
    sys.exit()

switch = sys.argv[3]                                        # Switch 's' or 'm' represents either (s)ingle or (m)ultiple ECLIs

if switch != 's' and switch != 'm':                         # Switch must be one of 's' or 'm' not anything else
    print()
    sys.exit("Invalid switch specified. Please specify 's' or 'm' for third argument. Required arguments: 1) lido-api-username, 2) lido-api-password, 3) 's' or 'm' ('s' means single ECLI, 'm' means multiple ECLIs), 4) if argument 3 is 's' then supply single ECLI code. If argument 3 is 'm' then supply a path to a CSV file which lists the ECLI codes (each on a separate line).")

input_eclis = sys.argv[4]                                   # Input ECLI or ECLI(s) in a CSV file

if switch == 's':                                           
    if (not is_valid_ecli_code(input_eclis)):               # Check if a valid ECLI code is specified
        print()
        sys.exit("Invalid ECLI code specified. Please specify an ECLI code from a rechtspraak.nl case e.g. ECLI:NL:HR:2014:952.")

if switch == 'm':
    if (not is_valid_csv_file_name(input_eclis)):           # Check if a valid CSV file name is specified
        print()
        sys.exit("Invalid input file specified. Please specify the path to a CSV file with a list of ECLI codes (an example of an ECLI code is ECLI:NL:HR:2014:952). Each ECLI code should be on a separate line in the CSV file.")

xml_elements = []
LIDO_API_URL = 'http://linkeddata.overheid.nl/service/get-links'
auth = {}
auth['username'] = sys.argv[1]
auth['password'] = sys.argv[2]

# Code to execute LIDO API call
def get_lido_response(url):
    global auth
    response = requests.get(url,auth=requests.auth.HTTPBasicAuth(auth['username'],auth['password']))
    if response.status_code == 200:
        return response.text
    else:
        raise Exception('LinkedData responded with code {}: {}. {}'.format(response.status_code, response.reason, url))

# Generate a LIDO identifier from an input ECLI code of a case
def get_lido_id(ecli):
    return "http://linkeddata.overheid.nl/terms/jurisprudentie/id/" + ecli

# Extract the ECLI code from the LIDO identifier of the cited case law from the XML response from LIDO API
def get_ecli(sub_ref):
    return sub_ref.attrib['idref'].split('/')[-1]

# Extract the LIDO identifier of the cited legislation from the XML response from LIDO API
def get_legislation_identifier(sub_ref):
    return sub_ref.attrib['idref']

# Find the webpage expressing, in writing, the legislation referred to by the input LIDO identifier
def get_legislation_webpage(identifier):
    idcomponents = identifier.split("/")
    date = idcomponents[len(idcomponents)-1]
    url = identifier
    page = urllib.request.urlopen(url)
    g=rdflib.Graph()
    g.parse(page, format="xml")
    article = ""
    for s,p,o in g:
        if (str(p) == "http://purl.org/dc/terms/identifier"):
            article = o
            if date in str(o):
                return o
    return article
    
# Check if outgoing links in the XML response from the LIDO API are of type "Jurisprudentie" (case law)
def is_case_law(sub_ref):
    return sub_ref.attrib['groep'] == 'Jurisprudentie'

# Check if outgoing links in the XML response from the LIDO API are of type "Wet" (legislation)
def is_legislation(sub_ref):
    return sub_ref.attrib['groep'] == 'Wet' or sub_ref.attrib['groep'] == 'Artikel'

# Extract ECLI code of citation from a lido identifier. Example of a LIDO identifier "https://linkeddata.overheid.nl/terms/bwb/id/BWBR0020368/8655654/2016-08-11/2016-08-11"
def get_lido_id(ecli):
    return "http://linkeddata.overheid.nl/terms/jurisprudentie/id/" + ecli

# Main method to execute LIDO API call on a list of ECLIs from a CSV file and extract the citations of each
def find_citations_for_cases(filename):
    eclis = []
    csv_reader = None
    try:
        with open(filename) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                eclis.append(row[0])
    except IOError:
        print()
        sys.exit("Error opening " + str(filename))
    if (not csv_reader) or (len(eclis) == 0):
        print()
        sys.exit("No data in " + str(filename))

    result = []
    case_law_result = []
    legislation_result = []

    print()
    print("Fetching citations from LIDO...")
    print()
    
    num_eclis = len(eclis)
    index = 1
    for ecli in eclis:
        print(remove_spaces_from_ecli(ecli),"\t\t","(",index,"/",num_eclis,")")
        index += 1
        current_citations = find_citations_for_case(remove_spaces_from_ecli(ecli))
        case_law_result.extend(current_citations[0])
        legislation_result.extend(current_citations[1])

    result.append(case_law_result)
    result.append(legislation_result)
    return result

# Main method to execute LIDO API call on the ECLI code of the input case and extract the citations
def find_citations_for_case(ecli):
    global LIDO_API_URL
    global xml_elements
    case_law_citations = []
    legislation_citations = []
    start_page = 0
    end_of_pages = False
    while (end_of_pages == False):
        num_citations_before_api_call = len(case_law_citations)
        url = "{}?id={}&start={}&rows={}&output=xml".format(LIDO_API_URL, get_lido_id(ecli),start_page,100)
        start_page += 1 
        xml_text = get_lido_response(url)
        xml_elements.append(etree.fromstring(xml_text.encode('utf8')))
        for el in xml_elements:
            for sub in list(el.iterchildren('subject')):
                for outgoing_citations in sub.iterchildren('uitgaande-links'):
                    for sub_ref in outgoing_citations.iterchildren():
                        if is_case_law(sub_ref):
                            case_law_citations.append(get_ecli(sub_ref))
                        if is_legislation(sub_ref):
                            legislation_citations.append(get_legislation_identifier(sub_ref))
        
        # Remove duplicates
        case_law_citations = list(set(case_law_citations))
        if ((len(case_law_citations) == num_citations_before_api_call) and (len(case_law_citations) > 0)) or ((len(case_law_citations) == 0) and (start_page == 5)):
            end_of_pages = True

    # Remove duplicates
    case_law_citations = list(set(case_law_citations))
    # Remove duplicates
    legislation_citations = list(set(legislation_citations))
    # Remove input case ECLI (for some reason a case can cite itself...)
    if (remove_spaces_from_ecli(ecli) in case_law_citations):
        case_law_citations.remove(remove_spaces_from_ecli(ecli))

    result = []
    case_law_result = []
    legislation_result = []
    
    for case_citation in case_law_citations:
        current_row = []
        current_row.append(remove_spaces_from_ecli(ecli))    # Source ECLI
        current_row.append("")                                          # Source paragraph     
        current_row.append(remove_spaces_from_ecli(case_citation))      # Target ECLI
        current_row.append("")                                          # Target paragraph
        case_law_result.append(current_row)
    
    for leg_citation in legislation_citations:
        current_row = []
        current_row.append(remove_spaces_from_ecli(ecli))    # Source ECLI
        current_row.append("")                                          # Source paragraph     
        current_row.append(leg_citation)                                # Target article
        current_row.append("")                                          # Target paragraph
        current_row.append(get_legislation_webpage(leg_citation))       # Target article webpage
        legislation_result.append(current_row)

    result.append(case_law_result)
    result.append(legislation_result)

    return result

# Testing the script
if (switch == 's'):                                                                                                                 # Single ECLI
    ecli_code = remove_spaces_from_ecli(input_eclis)
    ecli_code = ecli_code.replace(":", "")
    case_citations_output_filename = ecli_code + "_caselaw_citations.csv"
    legislation_citations_output_filename = ecli_code + "_legislation_citations.csv"
    citations = find_citations_for_case(remove_spaces_from_ecli(input_eclis))
    citations[0].insert(0,['source_ecli','source_paragraph','target_ecli','target_paragraph'])                                      # Insert case citations header
    write_data_to_csv(case_citations_output_filename, citations[0])                                                                 # Write case law citations to file
    citations[1].insert(0,['source_ecli','source_paragraph','target_article','target_article_paragraph','target_article_webpage'])  # Insert legislation citations header
    write_data_to_csv(legislation_citations_output_filename, citations[1])                                                          # Write legislation citations to file
else:                                                                                                                               # Multiple ECLIs
    case_citations_output_filename = "caselaw_citations.csv"
    legislation_citations_output_filename = "legislation_citations.csv"
    citations = find_citations_for_cases(input_eclis)
    citations[0].insert(0,['source_ecli','source_paragraph','target_ecli','target_paragraph'])                                      # Insert case citations header
    write_data_to_csv(case_citations_output_filename, citations[0])        
    citations[1].insert(0,['source_ecli','source_paragraph','target_article','target_article_paragraph','target_article_webpage'])  # Insert legislation citations header                                                         # Write case law citations to file
    write_data_to_csv(legislation_citations_output_filename, citations[1])                                                          # Write legislation citations to file