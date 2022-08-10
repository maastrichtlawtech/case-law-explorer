import pandas as pd
import numpy as np
from definitions.terminology.attribute_names import ECLI
from definitions.mappings.attribute_value_maps import *
from definitions.terminology.attribute_values import Domain
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
    return '; '.join(i for i in set(text.split(', ')))


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
# from original RS date format DD-MM-YYYY
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


def compare(a, b, operator, data, number=5):
    """
    prints number of cases fulfilling comparison condition and examples deviating from condition
    :param a: first column to compare
    :param b: second column to compare
    :param operator: how to compare columns (one of: {'==', '<=', '<'})
    :param data: dataframe to use as source
    :param number: number of examples to print
    :return: examples deviating from condition
    """
    if operator == '==':
        comparison = data[a] == data[b]
    elif operator == '<=':
        comparison = data[a] <= data[b]
    elif operator == '<':
        comparison = data[a] < data[b]
    else:
        print('Invalid operator!')
    print(f'CASES WHERE {a} {operator} {b}:')
    print(comparison.value_counts())
    print(f'\nEXAMPLES OF CASES WHERE {a} NOT {operator} {b}:')
    differing_cases = data[~comparison]
    return differing_cases[~differing_cases[[a, b]].isnull().any(axis=1)].head(number)
