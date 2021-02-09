#%%
import boto3
from boto3.dynamodb import conditions
from boto3.dynamodb.conditions import Key, Attr
from csv import DictReader
import csv
import sys
csv.field_size_limit(sys.maxsize)
from definitions.terminology.field_names import *
from definitions.file_paths import CSV_RS_CASES_PROC, CSV_LI_CASES_PROC, CSV_RS_OPINIONS_PROC, CSV_CASE_CITATIONS, CSV_LEGISLATION_CITATIONS
import time
#%%
"""
(COMPOSITE) KEY EXPLANATIONS:

ecli:
    - format: <ecli> # can be either decision ecli or opinion ecli
    - example: ECLI:NL:HR:1234
    
doc-id: 
    - format: <doctype-value>, example: DEC-ECLI:NL:HR:1234
    - possible doctypes (one of):
        DEC         # decision to given case ecli, value = decision ecli
        OPI         # opinion to given case ecli, value = opinion ecli
        C-CIT-LIDO  # case citation to given case ecli (extracted with LIDO), value = cited case ecli
        L-CIT-LIDO  # legislation citation to given case ecli (extracted with LIDO), value = cited legislation/article
        C-CIT-RS    # referenced case (predecessor/successor case) to given case ecli (extracted from RS meta data), value = referenced case ecli
        L-CIT-RS    # referenced legislation citation to given case ecli (extracted from RS meta data), value = referenced legislation/article
        DOM-RS      # associated domain to given case ecli (extracted from RS meta data), value = domain name
        DOM-LI      # associated domain to given case ecli (extracted from LI meta data)

source-date:
    - format: <source-doctype-date>, example: RS-DEC-2021-02-07
    - possible values for source:
        RS          # case from Rechtspraak
        CJEU        # case from the Court of Justice of the European Union
        ECHR        # case from the European Court of Human Rights
    - possible values for doctype:
        DEC         # decision of case
        OPI         # opinion of case
    - date of decision in format YYYY-MM-DD
    
instance:
    
"""

dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")  # remove 'endpoint_url' to use web service

#%% CREATE TABLE
SEP = '-'
# key attribute names:
PK = ECLI
SK = 'doc' + SEP + 'id'
PK2 = RS_CREATOR
SK2 = 'source' + SEP + 'doc' + SEP + 'date'

# possible values for 'doc':
doc_map = {
    'uitspraak': 'DEC',
    'conclusie': 'OPI',
    RS_RELATION: 'C-CIT',
    LIDO_JURISPRUDENTIE: 'C-CIT',
    RS_REFERENCES: 'L-CIT',
    LIDO_WET: 'L-CIT',
    RS_SUBJECT: 'DOM'
}

# possible values for 'source':
LIDO = 'LIDO'
LI = 'LI'
RS = 'RS'
CJEU = 'CJEU'
ECHR = 'ECHR'


caselaw_table = dynamodb.create_table(
    TableName='caselaw-v2',
    KeySchema=[
        {   # partition key
            'AttributeName': PK,
            'KeyType': 'HASH'
        },
        {   # sort key
            'AttributeName': SK,
            'KeyType': 'RANGE'
        },
    ],
    AttributeDefinitions=[
        {
            'AttributeName': PK,            # can be decision ecli or opinion ecli
            'AttributeType': 'S'
        },
        {
            'AttributeName': SK,         # see above
            'AttributeType': 'S'
        },
        {
            "AttributeName": SK2,     #
            "AttributeType": "S"
        },
                {
            "AttributeName": PK2,        # name of instance
            "AttributeType": "S"
        },
    ],
    GlobalSecondaryIndexes=[
        {
            'IndexName': 'GSI' + SK,
            'KeySchema': [
                {
                    'AttributeName': SK,
                    'KeyType': 'HASH'
                },
                                {
                    'AttributeName': SK2,
                    'KeyType': 'RANGE'
                },
            ],
            'Projection': {
                'ProjectionType': 'KEYS_ONLY',
            },
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 20,
                'WriteCapacityUnits': 20
            },
        },
        {
            'IndexName': 'GSI' + PK2,
            'KeySchema': [
                {
                    'AttributeName': PK2,
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': SK2,
                    'KeyType': 'RANGE'
                },
            ],
            'Projection': {
                'ProjectionType': 'KEYS_ONLY',
            },
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 20,
                'WriteCapacityUnits': 20
            },
        },
    ],
    ProvisionedThroughput={
        'ReadCapacityUnits': 20,
        'WriteCapacityUnits': 20
    }
)
print("Table status:", caselaw_table.table_status)

#%%
caselaw_table = dynamodb.Table('caselaw-v2')


def csv_to_dynamo(path_to_csv, dynamo_table, row_processor):
    """

    :param path_to_csv:
    :param dynamo_table:
    :param row_processor:
    :return:
    """
    case_counter = 0
    item_counter = 0
    with open(path_to_csv, 'r', newline='') as in_file:
        reader = DictReader(in_file)
        # write items in batches to dynamo
        with dynamo_table.batch_writer() as batch:
            # for each row in csv:
            for row in reader:
                case_counter += 1
                if row != '':
                    items = row_processor(row)
                    for item in items:
                        item_counter += 1
                        try:
                            batch.put_item(Item=item)
                            # batch.put_item(Item=item, ConditionExpression='attribute_not_exists(ecli)')
                            # batch.put_item(Item=item, ConditionExpression=Attr('ecli').not_exists())
                        except:
                            try:
                                dynamo_table.put_item(Item=item)
                            except Exception as e:
                                print(e)
    print(f'{case_counter} cases ({item_counter} items) added.')


def row_processor_rs_cases(row):
    items = []
    # split set attributes (domain, case citations, legislation citations)
    for attribute in [RS_SUBJECT, RS_RELATION, RS_REFERENCES]:
        if row[attribute] != '':
            for item in row[attribute].split('; '):
                items.append({
                    PK: row[ECLI],
                    SK: doc_map[attribute] + SEP + RS + SEP + item
                })
            row.pop(attribute)
    items.append({
        SK: doc_map['uitspraak'] + SEP + RS + SEP + row[ECLI],
        SK2: doc_map['uitspraak'] + SEP + RS + SEP + row[RS_DATE],
        **row
    })
    return items


def row_processor_rs_opinions(row):
    items = [{
        SK: doc_map['conclusie'] + SEP + RS + SEP + row[ECLI],
        SK2: doc_map['conclusie'] + SEP + RS + SEP + row[RS_DATE],
        **row
    }]
    if row[ECLI_DECISION] != '':
        items.append({
            PK: row[ECLI],
            SK: doc_map['uitspraak'] + SEP + RS + SEP + row[ECLI_DECISION],
        })
        items.append({
            PK: row[ECLI_DECISION],
            SK: doc_map['conclusie'] + SEP + RS + SEP + row[ECLI],
        })
    return items


def row_processor_li_cases(row):
    items = []
    if row[LI_LAW_AREA] != '':
        items.append({PK: row[ECLI],
                      SK: doc_map[LI_LAW_AREA] + SEP + LI + SEP + row[LI_LAW_AREA]})
    row.pop(LI_LAW_AREA)
    items.append({
        SK: doc_map['uitspraak'] + SEP + LI + SEP + row[ECLI],
        SK2: doc_map['uitspraak'] + SEP + LI + SEP + row[RS_DATE],
        **row
    })
    return items


def row_processor_c_citations(row):
    items = [{
        PK: row[LIDO_ECLI],
        SK: doc_map[LIDO_JURISPRUDENTIE] + SEP + LIDO + SEP + row[LIDO_JURISPRUDENTIE],
        **row
    }]
    return items


def row_processor_l_citations(row):
    items = [{PK: row[LIDO_ECLI],
              SK: doc_map[LIDO_WET] + SEP + LIDO + SEP + row[LIDO_WET],
              **row}]
    return items


start = time.time()

print('Uploading RS cases...')
csv_to_dynamo(CSV_RS_CASES_PROC, caselaw_table, row_processor_rs_cases)

print('\nProcessing RS opinions...')
csv_to_dynamo(CSV_RS_OPINIONS_PROC, caselaw_table, row_processor_rs_opinions)

print('\nProcessing LI cases...')
csv_to_dynamo(CSV_LI_CASES_PROC, caselaw_table, row_processor_li_cases)

print('\nProcessing case citations...')
csv_to_dynamo(CSV_CASE_CITATIONS, caselaw_table, row_processor_c_citations)

print('\nProcessing legislation citations...')
csv_to_dynamo(CSV_LEGISLATION_CITATIONS, caselaw_table, row_processor_l_citations)

end = time.time()
print("\n\nTime taken: ", (end - start), "s")



