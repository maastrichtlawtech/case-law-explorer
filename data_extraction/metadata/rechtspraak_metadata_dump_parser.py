from lxml import etree
from lxml.etree import tostring
from itertools import chain

import os
import csv
import time
import re

is_case = False

case_records = []
opinion_records = []

datarecord = {}


# Initialize the datarecord with the default fields and inital values
def initialise_data_record():
    global datarecord
    datarecord = {
        "case_id": "",
        "date": "",
        "case_number": "",
        "description": "",
        "language": "",
        "venue": "",
        "abstract": "",
        "procedure_type": "",
        "lodge_date": "",
        "country": "NL",
        "subject": "",
        "authority": "",
        "legal_references": "",
        "related_cases": "",
        "alternative_sources": "",
        "full_text": ""
    }


def stringify_children(node):
    # https://stackoverflow.com/a/4624146
    parts = ([node.text] + list(chain(*([c.text, tostring(c, encoding=str), c.tail] for c in node.getchildren()))) + [
        node.tail])

    # filter removes possible Nones in texts and tails
    return ''.join(filter(None, parts))


def processtag(cleantagname, tag):
    global datarecord
    global is_case

    if cleantagname == 'type' and tag.text == 'Uitspraak':
        is_case = True
    if cleantagname == 'identifier':
        if datarecord['case_id'] == "":
            datarecord['case_id'] = tag.text
    if cleantagname == 'date':
        if datarecord['date'] == "":
            datarecord['date'] = tag.text
    if cleantagname == 'zaaknummer':
        if datarecord['case_number'] == "":
            datarecord['case_number'] = tag.text
    if cleantagname == 'inhoudsindicatie':
        if datarecord['description'] == "":
            datarecord['description'] = stringify_children(tag)
    if cleantagname == 'language':
        if datarecord['language'] == "":
            datarecord['language'] = tag.text.upper()
    if cleantagname == 'spatial':
        if datarecord['venue'] == "":
            datarecord['venue'] = tag.text
    if cleantagname == 'uitspraak.info':
        if datarecord['abstract'] == "":
            datarecord['abstract'] = stringify_children(tag)
    if cleantagname == 'conclusie.info':
        if datarecord['abstract'] == "":
            datarecord['abstract'] = stringify_children(tag)
    if cleantagname == 'procedure':
        if datarecord['procedure_type'] == "":
            datarecord['procedure_type'] = tag.text
    if cleantagname == 'subject':
        if datarecord['subject'] == "":
            datarecord['subject'] = tag.text
    if cleantagname == 'creator':
        if datarecord['authority'] == "":
            datarecord['authority'] = tag.text
    if cleantagname == 'references':
        if datarecord['legal_references'] == "":
            datarecord['legal_references'] = stringify_children(tag)
    if cleantagname == 'relation':
        if datarecord['related_cases'] == "":
            datarecord['related_cases'] = stringify_children(tag)
    if cleantagname == 'hasVersion':
        if datarecord['alternative_sources'] == "":
            datarecord['alternative_sources'] = stringify_children(tag)
    if cleantagname == 'uitspraak':
        file_name = tag.attrib['id']
        # ECLI_NL_RBROT_1913_22
        reg_post = re.search(
            'ECLI:(?P<country>.*):(?P<jur>.*):(?P<year>.*):(?P<no>.*):(?P<doc>.*)',
            file_name)
        file_name = PATH + reg_post.group('year') + '/' + file_name.replace(":", "_") + '.html'

        file = open(file_name, "w")
        file.write(stringify_children(tag))

        if datarecord['full_text'] == "":
            datarecord['full_text'] = file_name


#Function to write new line in the csv file
def write_line_csv(file_path, row):
    with open(file_path, 'a', newline='') as csvfile:
        columns = ['case_id', 'date', 'case_number', 'description', 'language', 'venue', 'abstract',
                       'procedure_type',
                       'lodge_date', 'country', 'subject', 'authority', 'legal_references', 'related_cases',
                       'alternative_sources', 'full_text']

        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writerow(row)


# Function to get all tags from an XML file
def parse_metadata_from_xml_file(filename):
    global datarecord
    global is_case

    initialise_data_record()
    is_case = False
    root = etree.parse(filename)

    for tag in root.iter():
        t = tag.tag
        tagname = str(t)

        # We have to remove the namespace preceding the tag name which is enclosed in '{}'
        if "}" in tagname:
            tagcomponents = tagname.split("}")
            cleantagname = tagcomponents[1]
            processtag(cleantagname, tag)
        else:
            cleantagname = tagname
            processtag(cleantagname, tag)

    if is_case:
        print("\033[94mCASE\033[0m %s" % datarecord['case_id'])
        write_line_csv('case.csv', datarecord)
    else:
        print("\033[95mOPINION\033[0m %s" % datarecord['case_id'])
        write_line_csv('case_opinion_from_advocate_general.csv', datarecord)


# Function to write data to file
def write_data_to_file(data, filename):
    csv_columns = ['case_id', 'date', 'case_number', 'description', 'language', 'venue', 'abstract', 'procedure_type',
                   'lodge_date', 'country', 'subject', 'authority', 'legal_references', 'related_cases',
                   'alternative_sources', 'full_text']
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
        writer.writeheader()
        for row in data:
            writer.writerow(row)


# Function to write data to file
def write_eclis_to_file(data, filename):
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerows(data)

###################################

PATH = "../../data/OpenDataUitspraken/"


# Start script timer
start = time.time()

print("Building index of XML files...\n")

# List all top-level directories
files = os.listdir(PATH)
dirs = [PATH + file for file in files if os.path.isdir(PATH + file) and file != 'full-text']
print(dirs)

# List all the .xml files from the directories
list_of_files_to_parse = []

for directory in dirs:
    # Get all the files from the directory
    files_in_dir = os.listdir(directory)

    for file in files_in_dir[:10]:
        # Append only the xml files
        if file[-4:].lower() == ".xml":
            list_of_files_to_parse.append(directory + "/" + file)

num_files = len(list_of_files_to_parse)

print("Index successfully built! Number of files in index:" + str(num_files))
print()
print("Parsing files...")
print()

# Parse files to obtain list of tags in them
index = 1
for file in list_of_files_to_parse:
    print("\033[1m%i/%i\033[0m %s" % (index, num_files, file))
    parse_metadata_from_xml_file(file)
    index += 1

print("Number of files: %i %i+%i" % (num_files, len(case_records), len(opinion_records)))

print()
print("Parsing successfully completed!")
print()
print("Writing data to file...")
print()

# case_dataframe = pd.DataFrame(caserecords)
# case_dataframe.to_csv('case.csv')

# write_data_to_file(case_records, 'case.csv')
# write_data_to_file(opinion_records, 'case_opinion_from_advocate_general.csv')
# write_eclis_to_file(eclis,'eclis_for_citations.csv')
print("Data successfully written to file!")
print()

# Stop the script timer
end = time.time()

print("Done!")
print()

print("Time taken: ", (end - start), "s")