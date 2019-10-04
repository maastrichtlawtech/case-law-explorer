from lxml import etree
import os
import csv
import time
import pandas as pd

is_case = False
contains_isReplacedBy = False

eclis = []
caserecords = []
opinionrecords = []

datarecord = {}


def initialise_data_record():
    global datarecord
    datarecord = {
        "id": "",
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
        "alternative_sources": ""
    }


def clean_namespace(item):
    item_str = str(item)
    item_str = item_str.replace("{http://www.w3.org/2005/Atom}", "")
    return item_str.replace(" ", "")


def stringify_children(node):
    from lxml.etree import tostring
    from itertools import chain
    parts = ([node.text] + list(chain(*([c.text, tostring(c, encoding=str), c.tail] for c in node.getchildren()))) + [
        node.tail])
    # filter removes possible Nones in texts and tails
    return ''.join(filter(None, parts))


def processtag(cleantagname, tag):
    global datarecord
    global is_case
    global contains_isReplacedBy
    global eclis

    # if (cleantagname == 'isReplacedBy'):
    # 	contains_isReplacedBy = True
    if (cleantagname == 'type' and tag.text == 'Uitspraak'):
        is_case = True
    if (cleantagname == 'identifier'):
        if datarecord['id'] == "":
            eclis.append([tag.text])
            datarecord['id'] = tag.text
    if (cleantagname == 'date'):
        if datarecord['date'] == "":
            datarecord['date'] = tag.text
    if (cleantagname == 'zaaknummer'):
        if datarecord['case_number'] == "":
            datarecord['case_number'] = tag.text
    if (cleantagname == 'inhoudsindicatie'):
        if datarecord['description'] == "":
            datarecord['description'] = stringify_children(tag)
    if (cleantagname == 'language'):
        if datarecord['language'] == "":
            datarecord['language'] = tag.text.upper()
    if (cleantagname == 'spatial'):
        if datarecord['venue'] == "":
            datarecord['venue'] = tag.text
    if (cleantagname == 'uitspraak.info'):
        if datarecord['abstract'] == "":
            datarecord['abstract'] = stringify_children(tag)
    if (cleantagname == 'conclusie.info'):
        if datarecord['abstract'] == "":
            datarecord['abstract'] = stringify_children(tag)
    if (cleantagname == 'procedure'):
        if datarecord['procedure_type'] == "":
            datarecord['procedure_type'] = tag.text
    if (cleantagname == 'subject'):
        if datarecord['subject'] == "":
            datarecord['subject'] = tag.text
    if (cleantagname == 'creator'):
        if datarecord['authority'] == "":
            datarecord['authority'] = tag.text
    if (cleantagname == 'references'):
        if datarecord['legal_references'] == "":
            datarecord['legal_references'] = stringify_children(tag)
    if (cleantagname == 'relation'):
        if datarecord['related_cases'] == "":
            datarecord['related_cases'] = stringify_children(tag)
    if (cleantagname == 'hasVersion'):
        if datarecord['alternative_sources'] == "":
            datarecord['alternative_sources'] = stringify_children(tag)


# Function to get all tags from an XML file
def parse_metadata_from_xml_file(filename):
    global datarecord
    global is_case
    global contains_isReplacedBy

    initialise_data_record()
    is_case = False
    root = etree.parse(filename)

    for tag in root.iter():
        t = tag.tag
        tagname = str(t)
        # We have to remove the namespace preceding the tag name which is enclosed in '{}'
        if ("}" in tagname):
            tagcomponents = tagname.split("}")
            cleantagname = tagcomponents[1]
            processtag(cleantagname, tag)
        else:
            cleantagname = tagname
            processtag(cleantagname, tag)

    if not contains_isReplacedBy:
        if is_case:
            print("\033[94mCASE\033[0m %s" % datarecord['id'])
            caserecords.append(datarecord)
        else:
            print("\033[95mOPINION\033[0m %s" % datarecord['id'])
            opinionrecords.append(datarecord)


# Function to write data to file
def write_data_to_file(data, filename):
    csv_columns = ['id', 'date', 'case_number', 'description', 'language', 'venue', 'abstract', 'procedure_type',
                   'lodge_date', 'country', 'subject', 'authority', 'legal_references', 'related_cases',
                   'alternative_sources']
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


# Start script timer
start = time.time()

print()
print("Building index of XML files...")
print()

# List all top-level directories
files = os.listdir(".")
dirs = [file for file in files if os.path.isdir(file)]

# for file in files:
# 	if os.path.isdir(file):
# 		# if file == "1965":
# 			dirs.append(file)

# List all the .xml files from the directories
list_of_files_to_parse = []

for directory in dirs:
    # Get all the files from the directory
    files_in_dir = os.listdir(directory)

    for file in files_in_dir[:20]:
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

print("Number of files: %i %i+%i" % (num_files, len(caserecords), len(opinionrecords)))

print()
print("Parsing successfully completed!")
print()
print("Writing data to file...")
print()

# case_dataframe = pd.DataFrame(caserecords)
# case_dataframe.to_csv('case.csv')

write_data_to_file(caserecords, 'case.csv')
write_data_to_file(opinionrecords, 'case_opinion_from_advocate_general.csv')
write_eclis_to_file(eclis, 'eclis_for_citations.csv')
print("Data successfully written to file!")
print()

# Stop the script timer
end = time.time()

print("Done!")
print()

print("Time taken: ", (end - start), "s")