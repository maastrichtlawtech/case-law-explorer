#%%
import boto3
from boto3.dynamodb import conditions
from boto3.dynamodb.conditions import Key, Attr
from pprint import pprint

# example queries to the data that's currently in dynamo
# (will be updated and probably have a slightly different key schema)

dynamodb = boto3.resource('dynamodb')  #, endpoint_url="http://localhost:8000")  # remove 'endpoint_url' to use web service
caselaw_table = dynamodb.Table('Caselaw')


def full_query(table, **kwargs):
    response = table.query(**kwargs)
    count = response['Count']
    items = response['Items']
    scanned_count = response['ScannedCount']

    while 'LastEvaluatedKey' in response:
        response = table.query(**kwargs, ExclusiveStartKey=response['LastEvaluatedKey'])
        count += response['Count']
        items.extend(response['Items'])
        scanned_count += response['ScannedCount']

    response['Count'] = count
    response['Items'] = items
    response['ScannedCount'] = scanned_count

    return response


#%% query for list of eclis

pprint(caselaw_table.get_item(Key={'id': 'ECLI:NL:RBHAA:2006:1006',
                                   'doctype': 'uitspraak'}))

#%% query on primary index with limited output
pprint(full_query(caselaw_table,
                  ProjectionExpression="id, subject",  # specifies which output to return
                  KeyConditionExpression=Key('id').eq('ECLI:NL:RBHAA:2006:1006') & Key('doctype').eq('uitspraak'))
)


#%% query on primary index

pprint(full_query(caselaw_table,
                  KeyConditionExpression=Key('id').eq('ECLI:NL:GHARN:1958:38')
                                         & Key('doctype').begins_with('c-citation'))  # all items for which sort key begins with
)

#%% query & filter on secondary index
pprint(full_query(caselaw_table,
                  IndexName='GSI-court',  # only needs to be specified if secondary index is used
                  ProjectionExpression="id",  #"id, court, subject, doctype",
                  FilterExpression=Attr('subject').contains('Ambtenarenrecht'),
                  KeyConditionExpression=Key('doctype').eq('uitspraak') & Key('court').begins_with('G'))
)


#%%
pprint(full_query(caselaw_table,
                  IndexName='GSI-court',  # only needs to be specified if secondary index is used
                  ProjectionExpression="id, subject",  #"id, court, subject, doctype",
                  #FilterExpression=Attr('subject').contains('Ambtenarenrecht'),
                  KeyConditionExpression=Key('doctype').eq('uitspraak'))
)



#%% if ECLIs given:
# chain queries (max 10? eclis -- ueberschaubar) --> list of 10 eclis




# sources: f.e. ecli in results: GSI: doctype = c-ref-ECLI --> list of 10xN eclis
# targets: f.e. ecli in results: MI: ecli = ECLI, doctype.begins_with(c-ref) --> list of 10xN eclis

