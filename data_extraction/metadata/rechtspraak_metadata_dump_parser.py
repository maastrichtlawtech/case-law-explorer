from lxml import etree
from lxml.etree import tostring
from itertools import chain
import zipfile
import os
import csv
import time
import pandas as pd
import re
import io
from terminology import *

is_case = False

case_records = []
opinion_records = []

global case_counter
global opinion_counter
global datarecord
case_counter = 0
opinion_counter = 0


# extract all files in directory "filename" and all subdirectories:
def extract_all(filename):
    newpath = '../../data/OpenDataUitspraken/'
    os.makedirs(newpath)
    z = zipfile.ZipFile(filename)
    for f in z.namelist():
        if f.endswith('.zip'):
            # get directory name from file
            dirname = os.path.dirname(f)
            if not os.path.exists(newpath + dirname):
                os.mkdir(newpath + dirname)
            newdir = os.path.splitext(f)[0]
            # create new directory
            os.mkdir(newpath + newdir)
            # read inner zip file into bytes buffer
            content = io.BytesIO(z.read(f))
            zip_file = zipfile.ZipFile(content)
            for i in zip_file.namelist():
                zip_file.extract(i, newpath + newdir)


# Initialize the datarecord with the default fields and inital values
def initialise_data_record():
    global case_counter
    global opinion_counter
    global datarecord
    datarecord = {
        RS_IDENTIFIER_ECLI: None,
        RS_ISSUED: None,
        RS_LANGUAGE: None,
        RS_CREATOR: None,
        RS_DATE: None,
        RS_ZAAKNUMMER: None,
        RS_TYPE: None,
        RS_PROCEDURE: None,
        RS_SPATIAL: None,
        RS_SUBJECT: None,
        RS_RELATION: None,
        RS_REFERENCES: None,
        RS_HASVERSION: None,
        RS_IDENTIFIER_URL: None,
        RS_TITLE: None,
        RS_INHOUDSINDICATIE: None,
        RS_INFO: None,
        RS_FULLTEXT: None,
        RS_SOURCE: "Rechtspraak",
        RS_JURISDICTION_COUNTRY: "NL",
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
        if datarecord[RS_IDENTIFIER_ECLI] is None:
            datarecord[RS_IDENTIFIER_ECLI] = tag.text
        else:
            datarecord[RS_IDENTIFIER_URL] = tag.text
    if cleantagname == 'issued':
        datarecord[RS_ISSUED] = tag.text
    if cleantagname == 'language':
        if datarecord[RS_LANGUAGE] is None:
            datarecord[RS_LANGUAGE] = tag.text.upper()
    if cleantagname == 'creator':
        if datarecord[RS_CREATOR] is None:
            datarecord[RS_CREATOR] = tag.text
    if cleantagname == 'date':
        if datarecord[RS_DATE] is None:
            datarecord[RS_DATE] = tag.text
    if cleantagname == 'zaaknummer':
        if datarecord[RS_ZAAKNUMMER] is None:
            datarecord[RS_ZAAKNUMMER] = tag.text
    if cleantagname == 'type':
        if datarecord[RS_TYPE] is None:
            datarecord[RS_TYPE] = tag.text
        if tag.text == 'Uitspraak':
            is_case = True
    if cleantagname == 'procedure':
        if datarecord[RS_PROCEDURE] is None:
            datarecord[RS_PROCEDURE] = tag.text
        else:
            datarecord[RS_PROCEDURE] += ', ' + tag.text
    if cleantagname == 'spatial':
        if datarecord[RS_SPATIAL] is None:
            datarecord[RS_SPATIAL] = tag.text
    if cleantagname == 'subject':
        if datarecord[RS_SUBJECT] is None:
            datarecord[RS_SUBJECT] = tag.text
    if cleantagname == 'relation':
        if datarecord[RS_RELATION] is None:
            datarecord[RS_RELATION] = tag.text
        else:
            datarecord[RS_RELATION] += ', ' + tag.text
    if cleantagname == 'references':
        if datarecord[RS_REFERENCES] is None:
            datarecord[RS_REFERENCES] = tag.text
        else:
            datarecord[RS_REFERENCES] += ', ' + tag.text
    if cleantagname == 'hasVersion':
        if datarecord[RS_HASVERSION] is None:
            datarecord[RS_HASVERSION] = stringify_children(tag)
    if cleantagname == 'title':
        if datarecord[RS_TITLE] is None:
            datarecord[RS_TITLE] = stringify_children(tag)
    if cleantagname == 'inhoudsindicatie':
        if datarecord[RS_INHOUDSINDICATIE] is None:
            datarecord[RS_INHOUDSINDICATIE] = stringify_children(tag)
    if cleantagname == 'uitspraak.info' or cleantagname == 'conclusie.info':
        if datarecord[RS_INFO] is None:
            datarecord[RS_INFO] = stringify_children(tag)
    if cleantagname == 'uitspraak':
        # file_name = tag.attrib['id']
        # # ECLI_NL_RBROT_1913_22
        # reg_post = re.search(
        #     'ECLI:(?P<country>.*):(?P<jur>.*):(?P<year>.*):(?P<no>.*):(?P<doc>.*)',
        #     file_name)
        # file_name = PATH + reg_post.group('year') + '/' + file_name.replace(":", "_") + '.html'
        #
        # file = open(file_name, "w")
        # file.write(stringify_children(tag))

        if datarecord[RS_FULLTEXT] is None:
            datarecord[RS_FULLTEXT] = stringify_children(tag)


# write column names to csv
def initialise_csv_files():
    initialise_data_record()
    with open('../../data/case.csv', 'w') as f:
        # Using dictionary keys as fieldnames for the CSV file header
        writer = csv.DictWriter(f, datarecord.keys())
        writer.writeheader()
    with open('../../data/case_opinion_from_advocate_general.csv', 'w') as f:
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
        print("\033[94mCASE\033[0m %s" % datarecord[RS_IDENTIFIER_ECLI])
        write_line_csv('../../data/case.csv', datarecord)
    else:
        opinion_counter += 1
        print("\033[95mOPINION\033[0m %s" % datarecord[RS_IDENTIFIER_ECLI])
        write_line_csv('../../data/case_opinion_from_advocate_general.csv', datarecord)


# Function to write data to file
#def write_data_to_file(data, filename):
#    csv_columns = ['case_id', 'date', 'case_number', 'description', 'language', 'venue', 'abstract', 'procedure_type',
#                   'lodge_date', 'country', 'subject', 'authority', 'legal_references', 'related_cases',
#                   'alternative_sources', 'full_text']
#    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
#        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
#        writer.writeheader()
#        for row in data:
#            writer.writerow(row)


# Function to write data to file
#def write_eclis_to_file(data, filename):
#    with open(filename, 'w', newline='') as csvfile:
#        writer = csv.writer(csvfile, delimiter=',')
#        writer.writerows(data)

###################################

PATH = "../../data/OpenDataUitspraken/"


# Start script timer
start = time.time()

print("Extracting files...\n")
#extract_all("../../data/OpenDataUitspraken.zip")
print("All files extracted!\n")

print("Building index of XML files...\n")

# List all top-level directories
files = os.listdir(PATH)
dirs = [PATH + file for file in files if os.path.isdir(PATH + file) and file != 'full-text']
print(dirs)

# List all the .xml files from the directories
list_of_files_to_parse = []

for directory in dirs:
    print('DIRNAME: ' + directory)
    # Get all the files from the directory
    subdirectories = os.listdir(directory)
    subdirs = [directory + '/' + sub for sub in subdirectories if os.path.isdir(directory + '/' + sub) and sub != 'full-text']

    for subdir in subdirs:
        print('SUBDIRNAME: ' + subdir)
        files_in_dir = os.listdir(subdir)

        for file in files_in_dir:
            # Append only the xml files
            if file[-4:].lower() == ".xml":
                list_of_files_to_parse.append(subdir + "/" + file)

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
print()
print("Writing data to file...")
print()

#case_dataframe = pd.DataFrame(case_records)
#case_dataframe.to_csv('case.csv')

#write_data_to_file(case_records, 'case.csv')
#write_data_to_file(opinion_records, 'case_opinion_from_advocate_general.csv')
#write_eclis_to_file(eclis,'eclis_for_citations.csv')
print("Data successfully written to file!")
print()

# Stop the script timer
end = time.time()

print("Done!")
print()
print('Number of cases: ', case_counter)
print('Number of opinions: ', opinion_counter)
print("Time taken: ", (end - start), "s")

