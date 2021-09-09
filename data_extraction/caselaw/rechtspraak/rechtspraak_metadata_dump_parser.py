from os.path import dirname, abspath, basename, exists
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from lxml import etree
from lxml.etree import tostring
from itertools import chain
import os
import csv
import time
from definitions.storage_handler import Storage, DIR_RECHTSPRAAK, CSV_RS_CASES, CSV_RS_OPINIONS, CSV_RS_CASE_INDEX, get_path_raw
from definitions.terminology.field_names import SOURCE, JURISDICTION_COUNTRY, ECLI_DECISION, ECLI, RS_DATE, RS_RELATION
from definitions.terminology.field_values import RECHTSPRAAK, NL
import argparse


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
        SOURCE: RECHTSPRAAK,
        JURISDICTION_COUNTRY: NL,
    }


def stringify_children(node):
    # https://stackoverflow.com/a/4624146
    return ''.join(
        chunk for chunk in chain(
            (node.text,),
            chain(*((tostring(child, with_tail=False, encoding=str), child.tail) for child in node.getchildren())),
            (node.tail,)) if chunk)


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
        if datarecord[FULL_TEXT] is None:
            datarecord[FULL_TEXT] = stringify_children(tag)


# write column names to csv
def initialise_csv_files():
    initialise_data_record()
    if not exists(output_path_opinions):
        with open(output_path_opinions, 'w') as f:
            writer = csv.DictWriter(f, datarecord.keys())
            writer.writeheader()
    if not exists(output_path_cases):
        with open(output_path_cases, 'w') as f:
            # Using dictionary keys as fieldnames for the CSV file header
            datarecord.pop(ECLI_DECISION)
            writer = csv.DictWriter(f, datarecord.keys())
            writer.writeheader()
    if not exists(output_path_index):
        with open(output_path_index, 'w') as f:
            writer = csv.DictWriter(f, [ECLI, RS_DATE, RS_RELATION])
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
        # print("\033[94mCASE\033[0m %s" % datarecord[IDENTIFIER])
        datarecord.pop(ECLI_DECISION)
        write_line_csv(output_path_cases, datarecord)
        write_line_csv(output_path_index, {ECLI: datarecord[IDENTIFIER],
                                           RS_DATE: datarecord[DATE],
                                           RS_RELATION: datarecord[RELATION]})
    else:
        opinion_counter += 1
        # print("\033[95mOPINION\033[0m %s" % datarecord[IDENTIFIER])
        write_line_csv(output_path_opinions, datarecord)


start = time.time()

input_path = DIR_RECHTSPRAAK
output_path_cases = get_path_raw(CSV_RS_CASES)
output_path_opinions = get_path_raw(CSV_RS_OPINIONS)
output_path_index = get_path_raw(CSV_RS_CASE_INDEX)

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
args = parser.parse_args()
print('\n--- PREPARATION ---\n')
print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('INPUT:\t\t\t\t', basename(input_path))
print('OUTPUTS:\t\t\t', f'{basename(output_path_cases)}, {basename(output_path_opinions)}, {basename(output_path_index)}\n')
storage = Storage(location=args.storage, output_paths=[output_path_cases, output_path_opinions, output_path_index], input_path=input_path)
last_updated = storage.last_updated
print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

print('\n--- START ---\n')

is_case = False

case_counter = 0
opinion_counter = 0
datarecord = dict()

# Field names used for output csv. Field names correspond to tags of original data
IDENTIFIER = 'ecli'
ISSUED = 'issued'
LANGUAGE = 'language'
CREATOR = 'creator'
DATE = 'date_decision'
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

print("Building index of XML files...\n")

list_of_files_to_parse = []

# List all top-level directories
file_tree = os.walk(input_path)

# List all the files from the sub-directories
for (dirpath, dirnames, filenames) in file_tree:
    if filenames:
        year, month = int(basename(dirpath)[:4]), int(basename(dirpath)[4:])
        # skip files before from date
        if year < last_updated.year or year == last_updated.year and month < last_updated.month:
            continue
        for file in filenames:
            # Append only the xml files
            if file[-4:].lower() == ".xml":
                list_of_files_to_parse.append(os.path.join(dirpath, file))
            else:
                print(file)

num_files = len(list_of_files_to_parse)

print("Index successfully built! Number of files in index:" + str(num_files))
print("Parsing files...")

# Initialise csv files:
initialise_csv_files()

# Parse files to obtain list of tags in them
index = 1
for file in list_of_files_to_parse:
    # print("\033[1m%i/%i\033[0m %s" % (index, num_files, file))
    parse_metadata_from_xml_file(file)
    index += 1

print("Number of files: %i %i+%i" % (num_files, case_counter, opinion_counter))

print()
print("Parsing successfully completed!")
print('Number of cases: ', case_counter)
print('Number of opinions: ', opinion_counter)

print(f"\nUpdating {args.storage} storage ...")
storage.update_data()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
