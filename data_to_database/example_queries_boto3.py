#%%
import boto3
from boto3.dynamodb import conditions
from boto3.dynamodb.conditions import Key, Attr
from pprint import pprint

# example queries to the data that's currently in dynamo
# (will be updated and probably have a slightly different key schema)

dynamodb = boto3.resource('dynamodb')  #, endpoint_url="http://localhost:8000")  # remove 'endpoint_url' to use web service
caselaw_table = dynamodb.Table('Caselaw')

#%% request specific item for given partition and sort key
pprint(caselaw_table.get_item(Key={'id': 'ECLI:NL:RBHAA:2006:1006',
                                   'doctype': 'uitspraak'}))
#%% query on primary index with limited output
pprint(caselaw_table.query(
    ProjectionExpression="id, subject",  # specifies which output to return
    KeyConditionExpression=Key('id').eq('ECLI:NL:RBHAA:2006:1006') &
                           Key('doctype').eq('uitspraak'))
)


#%% query on primary index

pprint(caselaw_table.query(
    KeyConditionExpression=Key('id').eq('ECLI:NL:GHARN:1958:38') &
                           Key('doctype').begins_with('c-citation'))  # all items for which sort key begins with
)

#%% query & filter on secondary index
pprint(caselaw_table.query(
    IndexName='GSI-court',  # only needs to be specified if secondary index is used
    ProjectionExpression="id, court, subject, doctype",
    FilterExpression=Attr('subject').contains('Ambtenarenrecht'),
    KeyConditionExpression=Key('doctype').eq('uitspraak') & Key('court').begins_with('R'))
)
