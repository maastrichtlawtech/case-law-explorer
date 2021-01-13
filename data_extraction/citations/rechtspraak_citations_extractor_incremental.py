import requests
from lxml import etree
import urllib.request
import rdflib
import os
import sys
import csv
import pandas as pd
from definitions import CSV_CASE_CITATIONS, CSV_LEGISLATION_CITATIONS

# SCRIPT USAGE:
# python rechtspraak_citations_extractor.py param1 param2 param3 param4 param5
# param1 : lido API username
# param2 : lido API password
# param3 : Indicates whether you want to run this script on a single case or multiple cases. Use "s" for single ECLI OR "m" for multiple ECLIs
# param4 : Indicates whether you want the "incoming" or "outgoing" citations for the given case(s). Use "i" for incoming and "o" for outgoing
# param5 : Indicates the ECLI code(s) for the case(s) you want to extract the citations for. If you chose "s" for param3 then put the ECLI code
# for the case here. If you chose "m" for param3 then put the path to a .csv file which contains a list of case ECLI codes (one on each line, no commas)

def is_valid_ecli_code(ecli):
    ecli_code = ecli.replace(" ","")                                        # Remove spaces
    ecli_components = ecli_code.split(":")                                  # Split the ECLI into components 
    if ("." in input_eclis or len(ecli_components) != 5):                   # Each ECLI has exactly 5 components (and does not have a full stop - this probably indicates a file name)
        return False
    if (ecli_components[0].lower() == 'ecli'):                              # The first part of an ECLI is "ECLI"
        return True
    else:
        return False

def remove_spaces_from_ecli(ecli):
    return ecli.replace(" ","")

def is_valid_csv_file_name(filename):
    return input_eclis[-4:].lower() == ".csv"                               # CSV filename should end in ".csv"

def write_data_to_csv(filename,data):

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)


def write_incremental_rows(old_citations, old_legislation_citations, new_citations, new_legislation_citations, citation_output, l_citation_output):
    print("save file")
    #print("old citation shape : "+str(old_citations.shape))
    #print("old legislation citation shape : " + str(old_legislation_citations.shape))


    for nc in new_citations:
        old_citations = old_citations.append(pd.Series(nc, index=old_citations.columns), ignore_index=True)

    for nc in new_legislation_citations:
        old_legislation_citations = old_legislation_citations.append(pd.Series(nc, index=old_legislation_citations.columns), ignore_index = True)

    #print("new citation shape : " + str(old_citations.shape))
    #print("new legislation citation shape : " + str(old_legislation_citations.shape))

    old_citations.to_csv(citation_output, index=False)
    old_legislation_citations.to_csv(l_citation_output,index=False)

    return old_citations, old_legislation_citations



if len(sys.argv) != 6:                                                      # At least 5 arguments should be specified (excluding the script name)
    print()
    print("Incorrect number of arguments! Exactly 4 required:")
    print()
    print("1. lido-api-username,")
    print("2. lido-api-password,")
    print("3. 's' or 'm' ('s' means single ECLI, 'm' means multiple ECLIs),")
    print("4. 'i' or 'o' ('i' means incoming citations, 'o' means outgoing citations),")
    print("5. If argument 3 is 's' then supply a single ECLI code. If argument 3 is 'm' then supply a path to a CSV file which lists the ECLI codes (each on a separate line).")
    sys.exit()

num_of_cases_switch = sys.argv[3]                                           # Switch 's' or 'm' represents either (s)ingle or (m)ultiple ECLIs
citation_type_switch = sys.argv[4]                                          # Switch 'i' or 'o' represents either (i)ncoming or (o)utgoing ECLIs
input_eclis = sys.argv[5]                                                   # Input ECLI or ECLI(s) in a CSV file

if num_of_cases_switch != 's' and num_of_cases_switch != 'm':               # Switch must be one of 's' or 'm' not anything else
    print()
    sys.exit("Invalid switch specified. Please specify 's' or 'm' for third argument. Required arguments: 1) lido-api-username, 2) lido-api-password, 3) 's' or 'm' ('s' means single ECLI, 'm' means multiple ECLIs), 4) 'i' or 'o' ('i' means incoming citations, 'o' means outgoing citations), 5) if argument 3 is 's' then supply single ECLI code. If argument 3 is 'm' then supply a path to a CSV file which lists the ECLI codes (each on a separate line).")

if num_of_cases_switch == 's':                                           
    if (not is_valid_ecli_code(input_eclis)):                               # Check if a valid ECLI code is specified
        print()
        sys.exit("Invalid ECLI code specified. Please specify an ECLI code from a rechtspraak.nl case e.g. ECLI:NL:HR:2014:952.")

if num_of_cases_switch == 'm':
    if (not is_valid_csv_file_name(input_eclis)):                           # Check if a valid CSV file name is specified
        print()
        sys.exit("Invalid input file specified. Please specify the path to a CSV file with a list of ECLI codes (an example of an ECLI code is ECLI:NL:HR:2014:952). Each ECLI code should be on a separate line in the CSV file.")

if citation_type_switch != 'i' and citation_type_switch != 'o':             # Switch must be one of 'i' or 'o' not anything else
    print()
    sys.exit("Invalid switch specified. Please specify 'i' or 'o' for third argument. Required arguments: 1) lido-api-username, 2) lido-api-password, 3) 's' or 'm' ('s' means single ECLI, 'm' means multiple ECLIs), 4) 'i' or 'o' ('i' means incoming citations, 'o' means outgoing citations), 5) if argument 3 is 's' then supply single ECLI code. If argument 3 is 'm' then supply a path to a CSV file which lists the ECLI codes (each on a separate line).")

if citation_type_switch == 'i':
    citation_type = "inkomende-links"
else:
    citation_type = "uitgaande-links"

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
    #print(sub_ref.attrib)
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

def get_legislation_name(url):
    #print("sub ref type : "+str(type(sub_ref)))
    #print(sub_ref)

    #get the url from where we can retrieve the info
    #url = str(sub_ref.attrib['idref'])

    #turn the response into an xml tree
    xml_response = get_lido_response(url)
    xml = etree.fromstring(bytes(xml_response, encoding='utf8'))

    pref_label=""
    title=""
    #RDF main element (root)
    for element in xml.iterchildren():
        # there is only one child and it is the "description" in whichh the rest of the info is
        #print("%s - %s" % (element.tag, element.text))
        #go through all the tags (all the info)
        for el in element.iterchildren():
            #print("%s - %s" % (el.tag, el.text))

            #the title (same thing as the preLabel) is the feature we want to be using
            if el.tag == "{http://purl.org/dc/terms/}title":
                title = el.text

    #if title==pref_label:
    #    print("title and pref label are equal")
    #else:
    #    print("not equal")

    return title


# Check if outgoing links in the XML response from the LIDO API are of type "Jurisprudentie" (case law)
def is_case_law(sub_ref):
    return sub_ref.attrib['groep'] == 'Jurisprudentie'

# Check if outgoing links in the XML response from the LIDO API are of type "Wet" (legislation)
def is_legislation(sub_ref):
    return sub_ref.attrib['groep'] == 'Wet' or sub_ref.attrib['groep'] == 'Artikel'

# Extract ECLI code of citation from a lido identifier. Example of a LIDO identifier "https://linkeddata.overheid.nl/terms/bwb/id/BWBR0020368/8655654/2016-08-11/2016-08-11"
def get_lido_id(ecli):
    return "http://linkeddata.overheid.nl/terms/jurisprudentie/id/" + ecli


# Method written by Marion
"""
These methods are used to write the citations incrementally to the csv file (in case it crashes or times out). 
It allows us to stop the script whenever we want without loosing our data, and without having to start from the bginning the next time. 
"""

#Given a csv file with a list of citations, retrieve the last ecli number
def get_last_ecli_downloaded(downloaded_citations):
    # these names were directly taken from the main method at the bottom of the file. Maybe these names should be put as
    # variables for the whole script
    last_citation_ecli =0
    #if there are no citations yet
    if downloaded_citations.shape[0] != 0:
        print(downloaded_citations.shape)
        last_citation_ecli = downloaded_citations.iloc[downloaded_citations.shape[0]-1]['ecli']

    return last_citation_ecli

# Main method to execute LIDO API call on a list of ECLIs from a CSV file and extract the citations of each
#Add the implementation of the incremental writing of rows
def find_citations_for_cases(filename, last_ecli, downloaded_citations, downloaded_legislation_citations, case_citations_output_name, legislation_citation_output_name):
    print(filename)

    start= False

    #if there is nothing in the table yet (meaning it is the first time we run the script)
    if last_ecli == 0:
        start=True
    eclis = []
    csv_reader = None
    try:

        with open(filename) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                if row[0] == last_ecli:
                    print("start the retrieval, this is the last ecli downloaded")
                    start = True
                #only append the eclis starting from (and including) the input ecli number (the last one we have already downloaded)
                if start == True:
                    eclis.append(row[0])
    except IOError:
        print()
        sys.exit("Error opening " + str(filename))
    if (not csv_reader) or (len(eclis) == 0):
        print()
        sys.exit("No data in " + str(filename))

    print()
    if (citation_type_switch == "i"):
        print("Fetching incoming citations from LIDO...")
    else:
        print("Fetching outgoing citations from LIDO...")
    print()
    
    num_eclis = len(eclis)
    index = 1

    hundred_counts = 3000
    case_law_result_temp = []
    legislation_result_temp = []
    for ecli in eclis:
        print(remove_spaces_from_ecli(ecli),"\t\t","(",index,"/",num_eclis,")")
        print()
        index += 1
        hundred_counts += 1
        current_citations = find_citations_for_case(remove_spaces_from_ecli(ecli))

        #print("citation size : "+str(len(current_citations[0])))
        #print("legislation citation size : " + str(len(current_citations[1])))

        #temporary list of citations (stored but not yet written to the csv file)
        case_law_result_temp.extend(current_citations[0])
        legislation_result_temp.extend(current_citations[1])


        #save in csv file when count == 100
        if hundred_counts == 30:
            #write them to the csv file
            downloaded_citations, downloaded_legislation_citations = write_incremental_rows(downloaded_citations, downloaded_legislation_citations, case_law_result_temp, legislation_result_temp, case_citations_output_name, legislation_citation_output_name)
            #set the hundred ones to 0, and empty the temporary citations list
            case_law_result_temp = []
            legislation_result_temp = []
            hundred_counts = 0

    #write to csv the last batch of cases
    write_incremental_rows(downloaded_citations, downloaded_legislation_citations, case_law_result_temp,legislation_result_temp, case_citations_output_name, legislation_citation_output_name)



# Main method to execute LIDO API call on the ECLI code of the input case and extract the citations
def find_citations_for_case(ecli):
    global LIDO_API_URL
    global citation_type
    xml_elements = []
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
            #print(el.tag)
            #print(etree.tostring(el))
            for sub in list(el.iterchildren('subject')):
                #rint(etree.tostring(sub))
                if (citation_type == "uitgaande-links"):
                    for the_citations in sub.iterchildren(citation_type):
                        for sub_ref in the_citations.iterchildren():
                            if is_case_law(sub_ref):
                                case_law_citations.append(get_ecli(sub_ref))
                            if is_legislation(sub_ref):
                                legislation_citations.append(get_legislation_identifier(sub_ref))
                else:
                    for the_citations in sub.iterchildren(citation_type):
                        for sub_ref in the_citations.iterchildren():
                            if is_case_law(sub_ref):
                                case_law_citations.append(get_ecli(sub_ref))                            
                    for the_other_citations in sub.iterchildren("uitgaande-links"):
                        for other_sub_ref in the_other_citations.iterchildren():
                            if is_legislation(other_sub_ref):
                                legislation_citations.append(get_legislation_identifier(other_sub_ref))
        
        # Remove duplicates
        case_law_citations = list(set(case_law_citations))
        if ((len(case_law_citations) == num_citations_before_api_call) and (len(case_law_citations) > 0)) or ((len(case_law_citations) == 0) and (start_page == 5)):
            end_of_pages = True

    # Remove duplicates
    case_law_citations = list(set(case_law_citations))
    for item in case_law_citations:
        if item == "":
            case_law_citations.remove(item)

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
        #  current_row.append("")                                          # Source paragraph   --> not needed
        current_row.append(remove_spaces_from_ecli(case_citation))      # Target ECLI
        #  current_row.append("")                                          # Target paragraph  --> not needed
        case_law_result.append(current_row)
    
    for leg_citation in legislation_citations:
        current_row = []
        current_row.append(remove_spaces_from_ecli(ecli))    # Source ECLI
        #  current_row.append("")                                          # Source paragraph  --> not needed
        current_row.append(leg_citation)                                # Target article
        #  current_row.append("")                                          # Target paragraph  --> not needed
        current_row.append(get_legislation_webpage(leg_citation))       # Target article webpage

        article_name = get_legislation_name(leg_citation)
        current_row.append(article_name)                               #pref label == article name
        legislation_result.append(current_row)

    result.append(case_law_result)
    result.append(legislation_result)

    return result

print("START TESTING")
# Testing the script
if (num_of_cases_switch == 's'):                                                                                                                 # Single ECLI
    ecli_code = remove_spaces_from_ecli(input_eclis)
    ecli_code = ecli_code.replace(":", "")
    if (citation_type_switch == "i"):                                                                        # Single ECLI
        case_citations_output_filename = ecli_code + "_caselaw_citations_incoming.csv"
    else:
        case_citations_output_filename = ecli_code + "_caselaw_citations_outgoing.csv"
    
    legislation_citations_output_filename = ecli_code + "_legislation_citations.csv"
    citations = find_citations_for_case(remove_spaces_from_ecli(input_eclis))
    # citations[0].insert(0,['source_ecli','source_paragraph','target_ecli','target_paragraph'])                                      # Insert case citations header --> old
    citations[0].insert(0,['ecli', 'Jurisprudentie'])                                      # Insert case citations header
    write_data_to_csv(case_citations_output_filename, citations[0])                                                                 # Write case law citations to file
    # citations[1].insert(0,['source_ecli','source_paragraph','target_article','target_article_paragraph','target_article_webpage'])  # Insert legislation citations header  --> old
    citations[1].insert(0,['ecli', 'Wet', 'Artikel'])  # Insert legislation citations header
    write_data_to_csv(legislation_citations_output_filename, citations[1])                                                          # Write legislation citations to file
else:                                                       
    if (citation_type_switch == "i"):                                                                        # Multiple ECLIs
        case_citations_output_filename = "caselaw_citations_incoming.csv"
    else:
        case_citations_output_filename = CSV_CASE_CITATIONS  # outgoing citations

    legislation_citations_output_filename = CSV_LEGISLATION_CITATIONS

    #default value for the last ecli downloaded
    last_ecli = 0

    #if the file already exists, read it
    if os.path.isfile(case_citations_output_filename):
        downloaded_citations = pd.read_csv(case_citations_output_filename)
        last_ecli = get_last_ecli_downloaded(downloaded_citations)
        print("citation file already exists, last ecli : " + str(last_ecli))
    #if it doesnt, create it with the right columns
    else:
        downloaded_citations = pd.DataFrame(columns=['ecli', 'Jurisprudentie'])

    if os.path.isfile(legislation_citations_output_filename):
        downloaded_legislation_citations = pd.read_csv(legislation_citations_output_filename)
    else:
        downloaded_legislation_citations = pd.DataFrame(columns=['ecli', 'Wet', 'Artikel'])



    #if the file already existed
    if last_ecli != 0:

        print("pre size : "+str(downloaded_citations.shape))
        #delte the rows that come from that ecli, so that we dont re-download some of the citations (in case it broke in the middle)
        #if a later case had legislation citations but no case citations, it will be re-downloaded (because we are taking the last ecli
        #in the case citation table). This is why we have to drop duplicated from the legislation citation table at the very end of the script.
        downloaded_citations = downloaded_citations[downloaded_citations["ecli"] != last_ecli]
        print("post size : " + str(downloaded_citations.shape))

        print('legislation citations downloaded shape : '+str(downloaded_legislation_citations.shape))

    #find citations, and save the file incrementally
    find_citations_for_cases(input_eclis, last_ecli, downloaded_citations, downloaded_legislation_citations, case_citations_output_filename, legislation_citations_output_filename)

    # DROP DUPLICATES from the legislation citation table
    legislation_citations = pd.read_csv(legislation_citations_output_filename)
    #print(legislation_citations.head())
    #print("size leg before droping duplicates : "+str(legislation_citations.shape))
    legislation_citations = legislation_citations.drop_duplicates()
    #print("size leg after droping duplicates : " + str(legislation_citations.shape))
    legislation_citations.to_csv(legislation_citations_output_filename, index=False)



