#%%
import boto3
from boto3.dynamodb import conditions
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import json
import csv
from pprint import pprint
from botocore.exceptions import ClientError
import pandas as pd
import numpy as np
import string
from datetime import datetime
import dateutil.parser

# format of a sort key: datasource|doctype|id (example: RS|c-citation|ECLI:NL:GHARN:1958:38)
# --> can search for: 'RS|decision' (all RS cases)
DOCTYPE_IDS = {
    'RS': {             # Rechtspraak cases
        'decision': '',                             # decision to given case ecli
        'opinion': '<opinion_ecli>',                # opinion to given case ecli
        'c-citation': '<cited_ecli>',               # case citation to given case ecli (extracted with LIDO)
        'l-citation': '<cited_legislation>',        # legislation citation to given case ecli (extracted with LIDO)
        'c-reference': '<referenced_case_id>',      # referenced cases (predecessor/successor cases) to given case ecli (extracted from RS meta data)
        'l-reference': '<referenced_legislation>'   # referenced legislation citation to given case ecli (extracted from RS meta data)
    },
    'CJEU': {},         # cases of the Court of Justice of the European Union
    'ECHR': {}          # cases of the European Court of Human Rights (?)
}

dynamodb = boto3.resource('dynamodb')  #, endpoint_url="http://localhost:8000")  # remove 'endpoint_url' to use web service

#%%
caselaw_table = dynamodb.create_table(
    TableName='Caselaw',
    KeySchema=[
        {
            'AttributeName': 'ecli',
            'KeyType': 'HASH'  # Partition key
        },
        {
            'AttributeName': 'doctype',
            'KeyType': 'RANGE'  # Sort key
        },
    ],
    AttributeDefinitions=[
        {
            'AttributeName': 'ecli',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'doctype',  # format: datasource|doctype|id, example: RS|opinion|op_ecli
            'AttributeType': 'S'
        },
        {
            "AttributeName": "court",
            "AttributeType": "S"
        },
                {
            "AttributeName": "date",
            "AttributeType": "S"
        },
    ],
    GlobalSecondaryIndexes=[
        {
            'IndexName': 'GSI-court',
            'KeySchema': [
                {
                    'AttributeName': 'doctype',
                    'KeyType': 'HASH'
                },
                                {
                    'AttributeName': 'court',
                    'KeyType': 'RANGE'
                },
            ],
            'Projection': {
                'ProjectionType': 'ALL',
            },
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 20,
                'WriteCapacityUnits': 20
            },
        },
                {
            'IndexName': 'GSI-date',
            'KeySchema': [
                {
                    'AttributeName': 'doctype',
                    'KeyType': 'HASH'
                },
                                {
                    'AttributeName': 'date',
                    'KeyType': 'RANGE'
                },
            ],
            'Projection': {
                'ProjectionType': 'ALL',
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
caselaw_table = dynamodb.Table('Caselaw')

# ensure right datatypes (datetime, set, ..?)
# add/rename primary (case ecli) & sort keys
# (decision, opinion, case citation, leg citation, case-reference, legislation-reference, filters)
# make related cases (pre/successors) & referenced_legislation separate entries (see above)
# first load RS cases, then update LI cases

def load_data(table, data, output=False):
    keys = [key['AttributeName'] for key in table.key_schema]
    counter = 0
    with table.batch_writer() as batch:
        #for item in data:
        for item in data.iterrows():
            item = item[1].to_dict()
            counter += 1
            if output:
                values = [item[key] for key in keys]
                print("Adding item:", dict(zip(keys, values)))
            #batch.put_item(Item=item, ConditionExpression='attribute_not_exists(ecli)')
            #batch.put_item(Item=item, ConditionExpression=Attr('ecli').not_exists())
            batch.put_item(Item=item)
    print(f'{counter} items added.')

