# %%
import boto3
import botocore.exceptions
from csv import DictReader
import csv
import sys
import time
from definitions.file_paths import CSV_RS_CASES_PROC, CSV_LI_CASES_PROC, CSV_RS_OPINIONS_PROC, CSV_CASE_CITATIONS, \
    CSV_LEGISLATION_CITATIONS
from .utils.row_processors import row_processor_rs_cases, row_processor_rs_opinions, row_processor_li_cases, \
    row_processor_c_citations, row_processor_l_citations

csv.field_size_limit(sys.maxsize)



def csv_to_dynamo(path_to_csv, table, row_processor):
    """
    :param path_to_csv:
    :param table:
    :return:
    """

    # identify key schema
    schema = TABLE.key_schema

    if schema[0]['KeyType'] == 'HASH':
        pk = schema[0]['AttributeName']
        sk = schema[1]['AttributeName']
    else:
        pk = schema[1]['AttributeName']
        sk = schema[0]['AttributeName']

    case_counter = 0
    item_counter = 0
    reschedule = []

    with open(path_to_csv, 'r', newline='') as in_file:
        reader = DictReader(in_file)
        # write items in batches to dynamo
        with table.batch_writer(overwrite_by_pkeys=[pk, sk]) as batch:
            # for each row in csv (if not ''):
            for row in reader:
                case_counter += 1
                if row != '':

                    # remove empty attributes
                    atts = list(row.items())
                    for att in atts:
                        if att[1] == '':
                            row.pop(att[0])

                    # retrieve lists of items to put and update
                    put_items, update_items, update_set_items = row_processor(row, pk, sk)

                    # add items
                    for item in put_items:
                        try:
                            batch.put_item(Item=item)
                            item_counter += 1
                        except botocore.exceptions.ClientError:
                            try:
                                table.put_item(Item=item)
                                item_counter += 1
                            except botocore.exceptions.ClientError:
                                reschedule.append(item)
                                print('rescheduling', item[pk])

                    # work-around for weird bug that causes identical items to fail in some batches
                    # while succeeding in other batches?!
                    for old_item in reschedule:
                        try:
                            batch.put_item(Item=old_item)
                            reschedule.remove(old_item)
                            item_counter += 1
                        except botocore.exceptions.ClientError:
                            print('could not reschedule', old_item[pk], 'trying again')

                    # update item attributes
                    for item in update_set_items:
                        val_pk, val_sk, expression_att_names, expression_att_values = extract_attributes(item, pk, sk)
                        update_expression = f'ADD {list(expression_att_names.keys())[0]} {list(expression_att_values.keys())[0]}'
                        table.update_item(
                            Key={pk: val_pk, sk: val_sk},
                            UpdateExpression=update_expression,
                            ExpressionAttributeNames=expression_att_names,
                            ExpressionAttributeValues={
                                list(expression_att_values.keys())[0]: list(expression_att_values.values())[0]
                            }
                        )
                        item_counter += 1

                    # update item set attributes
                    for item in update_items:
                        val_pk, val_sk, expression_att_names, expression_att_values = extract_attributes(item, pk, sk)
                        update_expression = 'SET ' + ', '.join(list(expression_att_names.keys())[i] + '=' +
                                                               list(expression_att_values.keys())[i]
                                                               for i in range(len(expression_att_names)))
                        table.update_item(
                            Key={pk: val_pk, sk: val_sk},
                            UpdateExpression=update_expression,
                            ExpressionAttributeNames=expression_att_names,
                            ExpressionAttributeValues=expression_att_values
                        )
                        item_counter += 1

    print(f'{case_counter} cases ({item_counter} items) added.')


def extract_attributes(item, pk, sk):
    pk_value = item.pop(pk)
    sk_value = item.pop(sk)
    atts = list(item.keys())
    vals = list(item.values())
    expression_att_names = dict()
    expression_att_values = dict()
    for i in range(len(atts)):
        expression_att_names['#' + str(i)] = atts[i]
        expression_att_values[':' + str(i)] = vals[i]
    return pk_value, sk_value, expression_att_names, expression_att_values


start = time.time()

local = False

if local:
    TABLE = boto3.resource('dynamodb', endpoint_url="http://localhost:8000").Table('CaselawV6-hmq6fy5a6fcg7isx5lar3yewdy-dev')
else:
    TABLE = boto3.resource('dynamodb').Table('CaselawV6-hmq6fy5a6fcg7isx5lar3yewdy-dev')


#print('Uploading RS cases...')
#csv_to_dynamo(CSV_RS_CASES_PROC, TABLE, row_processor_rs_cases)

#print('\nProcessing RS opinions...')
#csv_to_dynamo(CSV_RS_OPINIONS_PROC, TABLE, row_processor_rs_opinions)

#print('\nProcessing LI cases...')
#csv_to_dynamo(CSV_LI_CASES_PROC, TABLE, row_processor_li_cases)

print('\nProcessing legislation citations...')
csv_to_dynamo(CSV_LEGISLATION_CITATIONS, TABLE, row_processor_l_citations)

print('\nProcessing case citations...')
csv_to_dynamo(CSV_CASE_CITATIONS, TABLE, row_processor_c_citations)

end = time.time()
print("\n\nTime taken: ", (end - start), "s")





