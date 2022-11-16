import pandas as pd
import numpy as np
from definitions.terminology.attribute_names import ECLI
from definitions.mappings.attribute_value_maps import *
from definitions.terminology.attribute_values import Domain
from definitions.storage_handler import CSV_ECHR_ARTICLES, CSV_ECHR_VIOLATIONS, \
    CSV_ECHR_NONVIOLATIONS, CSV_ECHR_YEARS
from lxml import etree
import dateutil.parser
import re
import sys
import csv
from ctypes import c_long, sizeof


#csv.field_size_limit(sys.maxsize) #appears to be system dependent so is replaced with:
#from https://stackoverflow.com/questions/52475749/maximum-and-minimum-value-of-c-types-integers-from-python
signed = c_long(-1).value < c_long(0).value
bit_size = sizeof(c_long)*8
signed_limit = 2**(bit_size-1)
csv.field_size_limit(signed_limit-1 if signed else 2*signed_limit-1)


# %%
""" CLEANING: """


# removes xml tags from string and returns text content (only Rechtspraak data extracted from xml)
def format_rs_xml(text):
    try:
        root = etree.fromstring('<items> ' + text + ' </items>')
    except Exception as e:
        print(e)
        return None
    text_list = root.xpath("//text()")
    clean = ' '.join(txt for txt in text_list)
    if clean.strip() == '-' or clean.strip() == '':
        return None
    return clean.strip()


# converts RS list notation: 'item1, item2, item3'
# to unified list notation: 'item1; item2; item3'
def format_rs_list(text):
    return '; '.join(i for i in set(text(', ')))


# converts LI list notation: "['item1', 'item2', 'item3']"
# to unified list notation: 'item1; item2; item3'
def format_li_list(text):
    repl = {"', '": "; ",
            "['": "",
            "']": ""}
    for i, j in repl.items():
        text = text.replace(i, j)
    return text


# converts string representation of a date into datetime (YYYY-MM-DD)
# from original RS date format YYYY-MM-DD
def format_rs_date(text):
    return dateutil.parser.parse(text).date()


# converts string representation of a date into datetime (YYYY-MM-DD)
# from original ECHR date format DD-MM-YYYY
def format_echr_date(text):
    return dateutil.parser.parse(text).date()


# converts string representation of a date into datetime
# from original LI date format YYYYMMDD or YYYYMMDD.0 (if numeric date was accidentally stored as float)
def format_li_date(text):
    return dateutil.parser.parse(str(int(float(text)))).date()


def format_domains(text):
    if len(text.split('; ')) == 1:
        text += '; ' + text + '-' + Domain.ALGEMEEN_OVERIG_NIED_GELABELD.value
    return text


def format_li_domains(text):
    clean = format_li_list(text)
    domains = set()
    for domain in set(clean.split('; ')):
        domains = domains.union(MAP_LI_DOMAINS[domain])
    domains_str = format_li_list(str(list(domains)))
    return format_domains(domains_str)


def format_instance(text):
    for key, value in MAP_INSTANCE.items():
        text = text.replace(key, value)
    return text


# removes xml tags and list format 'item1\n item2\n item3\n'
# to unified list notation: 'item1; item2; item3'
def format_rs_alt_sources(text):
    clean = format_rs_xml(text)
    if clean:
        clean = re.sub(' *\n *', '; ', clean)
    return clean


# renames RS and LI jurisdiction notation to unified notation
def format_jurisdiction(text):
    return MAP_JURISDICTION[text]


""" DF OPERATIONS (READ, WRITE, PRINT, SELECT): """

# make sure all csvs are read in the same way
def read_csv(path, cols=None):
    return pd.read_csv(path, dtype=str, usecols=cols).replace({np.nan: None})


# only returns (number) rows of dataframe df for which no column in columns is None
def not_none_rows(df, columns=None, number=-1):
    if number == -1:
        number = len(df)
    if not columns:
        columns = df.columns
    df_not_none = df.copy()
    for column in columns:
        df_not_none = df_not_none[~df_not_none[column].isnull()]
    return df_not_none.head(number)


# returns dataframe of cases that exist both in df_1 and df_2 with merged columns.
# Requires both dfs to have column named ECLI
def map_cases(df_1, df_2):
    intersection = list(set(df_1[ECLI]).intersection(set(df_2[ECLI])))
    df_mapped = df_1[df_1[ECLI].isin(intersection)]
    df_mapped.set_index(ECLI, inplace=True)
    df_2.set_index(ECLI, inplace=True)
    df_mapped = df_mapped.join(df_2)
    df_mapped.reset_index(inplace=True)
    df_2.reset_index(inplace=True)
    return df_mapped


# Perform operations on ECHR rows.
def manage_ECHR_rows(row, row_clean):
    row_clean["violation"] = violation_found(row)
    row_clean["nonviolation"] = nonviolation_found(row)
    separate_articles(row)
    separate_years(row_clean)
    

"""
Binarise the violations column for ECHR data. 0 or 1 shows the presence or absence of violations
respectively in a row.
"""
def violation_found(row):
    if row['violation'] != '':
        return 1
    elif row['violation'] == '':
        return 0


"""
Binarise the nonviolations column for ECHR data. 0 or 1 shows the presence or absence of
nonviolations respectively in a row.
"""
def nonviolation_found(row):
    '''Function performs binarization of variable "non-violation". Measures whether a non-violation of any article was found.
       Input: a row of a dataframe.
       Return: 1 - if a non-violation was found,
               0 - if a non-violation was not found.'''
    # 1 = non-violation is not empty
    if row['nonviolation'] != '':
        return 1
    # 0 = non-violation is empty
    elif row['nonviolation'] == '':
        return 0


# Check if a csv file is empty.
def is_empty_csv(path):
    with open(path) as csvfile:
        reader = csv.reader(csvfile)
        for i, _ in enumerate(reader):
            if i:  # found the second row
                return False
    return True


# Append the ecli and corresponding binary row to the specified csv file.
def write_binary(ecli, split_row, key_list, path):
    split_set = set(split_row)
    matches = [i for i, val in enumerate(key_list) if val in split_set]
    binary = np.zeros(len(key_list))
    binary[matches] = 1
    binary = binary.tolist()
    binary[0] = ecli
    file = open(path, 'a', newline='')
    with file:
        writer = csv.writer(file)
        if is_empty_csv(path):
            writer.writerow(key_list)
        writer.writerow(binary)


"""
Add binary variables based on articles for which a violation or non-violation was found, the 
violated articles, and the nonviolated articles to separate csv files. Column headers correspond to
articles and column values are 0 or 1 show the presence or absence of an article respectivelly.
"""
def separate_articles(row):
    # Convert the violation column into a list of strings of numbers.
    split_violation_row = []
    for i in row['violation'].split(';'):
        split_violation_row.append(re.split(r'\+|\-', i)[0])
    split_violation_row += find_protocols(row['violation'])
    # Convert the nonviolation column into a list of strings of numbers.
    split_nonviolation_row = []
    for i in row['nonviolation'].split(";"):
        split_nonviolation_row.append(re.split(r'\+|\-', i)[0])
    split_nonviolation_row += find_protocols(row['nonviolation'])
    # Convert the article column into a list of strings of numbers.
    split_article_row = []
    for i in row['article'].split(";"):
        split_article_row.append(re.split(r'\+|\-', i)[0])
    split_article_row += find_protocols(row['article'])
    # Concatenate the violation and non-violation lists.
    con_list = split_violation_row+split_nonviolation_row
    # Find the intersection of the articles, violations, and nonviolations lists and store it in a
    # list.
    mentioned_article_list = list(set(con_list) & set(split_article_row))
    key_list = [str(i) for i in range(1, 60)]
    key_list.extend([f'P{i}' for i in range(1, 17)])
    key_list[:0] = ['ecli']
    write_binary(row['ecli'], split_violation_row, key_list, CSV_ECHR_VIOLATIONS)
    write_binary(row['ecli'], split_nonviolation_row, key_list, CSV_ECHR_NONVIOLATIONS)
    write_binary(row['ecli'], split_article_row, key_list, CSV_ECHR_ARTICLES)


# Find the protocol numbers that are mentioned in the articles column
def find_protocols(articles):
    article_list = articles.split(';')
    article_arr = np.asarray(article_list)
    article_protocols_list = [] # This list will contain all of the found protocol names. 
    for i in range(1, 17):
        substring = f'P{i}'
        for s in article_arr:
            if s.find(substring) == -1: # Checks if a protocol is contained in the articles array.
                pass
            else:
                article_protocols_list.append(substring) 
                break
    return article_protocols_list


"""
Create a new csv file which stores the ecli and the judgement year. Caution is advised because
NaNs are cast to 0.
"""
def separate_years(row):
    date = row["date_decision"]
    year = 0 if pd.isna(date) else date.year #date.dt.year
    key_list = ["ecli", "year"]
    file = open(CSV_ECHR_YEARS, 'a', newline='')
    with file:
        writer = csv.writer(file)
        if is_empty_csv(CSV_ECHR_YEARS):
            writer.writerow(key_list)
        writer.writerow(np.array([row["ecli"], year]))
