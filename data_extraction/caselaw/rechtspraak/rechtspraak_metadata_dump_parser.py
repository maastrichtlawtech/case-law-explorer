from lxml import etree
from lxml.etree import tostring
from itertools import chain
import os
import csv
import time
from definitions.file_paths import DIR_RECHTSPRAAK, CSV_RS_CASES, CSV_RS_OPINIONS
from definitions.terminology.field_names import SOURCE, JURISDICTION_COUNTRY, ECLI_DECISION
from definitions.terminology.field_values import RS_SOURCE, NL

is_case = False

case_records = []
opinion_records = []

global case_counter
global opinion_counter
global datarecord
case_counter = 0
opinion_counter = 0

# Field names used for output csv. Field names correspond to tags of original data
IDENTIFIER = 'identifier'
ISSUED = 'issued'
LANGUAGE = 'language'
CREATOR = 'creator'
DATE = 'date'
ZAAKNUMMER = 'zaaknummer'
TYPE = 'type'
PROCEDURE = 'procedure'
SPATIAL = 'spatial'
SUBJECT = 'subject'
RELATION = 'relation'
REFERENCES = 'references'
HAS_VERSION = 'hasVersion'
IDENTIFIER2 = 'identifier2'
TITLE = 'title'
INHOUDSINDICATIE = 'inhoudsindicatie'
INFO = 'info'
FULL_TEXT = 'full_text'


# Initialize the datarecord with the default fields and inital values
def initialise_data_record():
    global case_counter
    global opinion_counter
    global datarecord
    datarecord = {
        ECLI_DECISION: None,
        IDENTIFIER: None,
        ISSUED: None,
        LANGUAGE: None,
        CREATOR: None,
        DATE: None,
        ZAAKNUMMER: None,
        TYPE: None,
        PROCEDURE: None,
        SPATIAL: None,
        SUBJECT: None,
        RELATION: None,
        REFERENCES: None,
        HAS_VERSION: None,
        IDENTIFIER2: None,
        TITLE: None,
        INHOUDSINDICATIE: None,
        INFO: None,
        FULL_TEXT: None,
        SOURCE: RS_SOURCE,
        JURISDICTION_COUNTRY: NL,
    }


def stringify_children(node):
    # https://stackoverflow.com/a/4624146
    return ''.join(
        chunk for chunk in chain(
            (node.text,),
            chain(*((tostring(child, with_tail=False, encoding=str), child.tail) for child in node.getchildren())),
            (node.tail,)) if chunk)

# to get only text without tags:
# ''.join(tag.itertext())


def processtag(cleantagname, tag):
    global datarecord
    global is_case

    if cleantagname == 'identifier':
        if datarecord[IDENTIFIER] is None:
            datarecord[IDENTIFIER] = tag.text
        else:
            datarecord[IDENTIFIER2] = tag.text
    if cleantagname == 'issued':
        datarecord[ISSUED] = tag.text
    if cleantagname == 'language':
        if datarecord[LANGUAGE] is None:
            datarecord[LANGUAGE] = tag.text.upper()
    if cleantagname == 'creator':
        if datarecord[CREATOR] is None:
            datarecord[CREATOR] = tag.text
    if cleantagname == 'date':
        if datarecord[DATE] is None:
            datarecord[DATE] = tag.text
    if cleantagname == 'zaaknummer':
        if datarecord[ZAAKNUMMER] is None:
            datarecord[ZAAKNUMMER] = tag.text
    if cleantagname == 'type':
        if datarecord[TYPE] is None:
            datarecord[TYPE] = tag.text
        if tag.text == 'Uitspraak':
            is_case = True
        # add case ecli to opinion records
        elif datarecord[ECLI_DECISION] is None and ':PHR:' in datarecord[IDENTIFIER]:
            datarecord[ECLI_DECISION] = datarecord[IDENTIFIER].replace(':PHR:', ':HR:')
    if cleantagname == 'procedure':
        if datarecord[PROCEDURE] is None:
            datarecord[PROCEDURE] = tag.text
        else:
            datarecord[PROCEDURE] += ', ' + tag.text
    if cleantagname == 'spatial':
        if datarecord[SPATIAL] is None:
            datarecord[SPATIAL] = tag.text
    if cleantagname == 'subject':
        if datarecord[SUBJECT] is None:
            datarecord[SUBJECT] = tag.text
    if cleantagname == 'relation':
        if datarecord[RELATION] is None:
            datarecord[RELATION] = tag.text
        else:
            datarecord[RELATION] += ', ' + tag.text
    if cleantagname == 'references':
        if datarecord[REFERENCES] is None:
            datarecord[REFERENCES] = tag.text
        else:
            datarecord[REFERENCES] += ', ' + tag.text
    if cleantagname == 'hasVersion':
        if datarecord[HAS_VERSION] is None:
            datarecord[HAS_VERSION] = stringify_children(tag)
    if cleantagname == 'title':
        if datarecord[TITLE] is None:
            datarecord[TITLE] = stringify_children(tag)
    if cleantagname == 'inhoudsindicatie':
        if datarecord[INHOUDSINDICATIE] is None:
            datarecord[INHOUDSINDICATIE] = stringify_children(tag)
    if cleantagname == 'uitspraak.info' or cleantagname == 'conclusie.info':
        if datarecord[INFO] is None:
            datarecord[INFO] = stringify_children(tag)
    if cleantagname == 'uitspraak' or cleantagname == 'conclusie':
        # file_name = tag.attrib['id']
        # # ECLI_NL_RBROT_1913_22
        # reg_post = re.search(
        #     'ECLI:(?P<country>.*):(?P<jur>.*):(?P<year>.*):(?P<no>.*):(?P<doc>.*)',
        #     file_name)
        # file_name = PATH + reg_post.group('year') + '/' + file_name.replace(":", "_") + '.html'
        #
        # file = open(file_name, "w")
        # file.write(stringify_children(tag))

        if datarecord[FULL_TEXT] is None:
            datarecord[FULL_TEXT] = stringify_children(tag)


# write column names to csv
def initialise_csv_files():
    initialise_data_record()
    with open(CSV_RS_OPINIONS, 'w') as f:
        writer = csv.DictWriter(f, datarecord.keys())
        writer.writeheader()
    with open(CSV_RS_CASES, 'w') as f:
        # Using dictionary keys as fieldnames for the CSV file header
        datarecord.pop(ECLI_DECISION)
        writer = csv.DictWriter(f, datarecord.keys())
        writer.writeheader()


# Function to write new line in the csv file
def write_line_csv(file_path, row):
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=row.keys())
        writer.writerow(row)


# Function to get all tags from an XML file
def parse_metadata_from_xml_file(filename):
    global datarecord
    global is_case
    global case_counter
    global opinion_counter

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
        case_counter += 1
        print("\033[94mCASE\033[0m %s" % datarecord[IDENTIFIER])
        datarecord.pop(ECLI_DECISION)
        write_line_csv(CSV_RS_CASES, datarecord)
    else:
        opinion_counter += 1
        print("\033[95mOPINION\033[0m %s" % datarecord[IDENTIFIER])
        write_line_csv(CSV_RS_OPINIONS, datarecord)

# Start script timer
start = time.time()

print("Building index of XML files...\n")

list_of_files_to_parse = []

# List all top-level directories
file_tree = os.walk(DIR_RECHTSPRAAK)

# List all the files from the sub-directories
for (dirpath, dirnames, filenames) in file_tree:
    for file in filenames:
        # Append only the xml files
        if file[-4:].lower() == ".xml":
            list_of_files_to_parse.append(os.path.join(dirpath, file))
        else:
            print(file)

    # list_of_files_to_parse.extend([os.path.join(dirpath, file) for file in filenames])

num_files = len(list_of_files_to_parse)

print("Index successfully built! Number of files in index:" + str(num_files))
print()
print("Parsing files...")
print()

# Initialise csv files:
initialise_csv_files()

# Parse files to obtain list of tags in them
index = 1
for file in list_of_files_to_parse:
    print("\033[1m%i/%i\033[0m %s" % (index, num_files, file))
    parse_metadata_from_xml_file(file)
    index += 1

print("Number of files: %i %i+%i" % (num_files, len(case_records), len(opinion_records)))

print()
print("Parsing successfully completed!")

# Stop the script timer
end = time.time()

print("Done!")
print()
print('Number of cases: ', case_counter)
print('Number of opinions: ', opinion_counter)
print("Time taken: ", (end - start), "s")

