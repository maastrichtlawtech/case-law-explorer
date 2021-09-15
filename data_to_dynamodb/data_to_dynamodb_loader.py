# %%
from os.path import dirname, abspath, basename
import sys
sys.path.append(dirname(dirname(abspath(__file__))))
import boto3
import botocore.exceptions
from csv import DictReader
import csv
from data_to_dynamodb.utils.row_processors import row_processor_rs_cases, row_processor_rs_opinions, row_processor_li_cases, \
    row_processor_c_citations, row_processor_l_citations
from data_to_dynamodb.utils.table_truncator import truncate_dynamodb_table
from definitions.storage_handler import Storage, CSV_RS_CASES, CSV_LI_CASES, CSV_RS_OPINIONS, CSV_CASE_CITATIONS, \
    CSV_LEGISLATION_CITATIONS, get_path_processed, DDB_TABLE_NAME, get_path_raw
import time
import argparse

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
                        try:
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
                        except Exception as e:
                            print(e, val_pk, val_sk)
                            with open('reschedule.txt', 'a') as f:
                                f.write(val_pk + val_sk + '\n')

                    # update item set attributes
                    for item in update_items:
                        try:
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
                        except Exception as e:
                            print(e, val_pk, val_sk)
                            with open('reschedule.txt', 'a') as f:
                                f.write(val_pk + val_sk + '\n')

                if case_counter % 1000 == 0:
                    print(case_counter, 'rows processed.')

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


processor_map = {
    get_path_processed(CSV_RS_CASES): row_processor_rs_cases,
    get_path_processed(CSV_RS_OPINIONS): row_processor_rs_opinions,
    get_path_processed(CSV_LI_CASES): row_processor_li_cases,
    get_path_raw(CSV_CASE_CITATIONS): row_processor_c_citations,
    get_path_raw(CSV_LEGISLATION_CITATIONS): row_processor_l_citations
}

start = time.time()

input_paths = [get_path_processed(CSV_RS_CASES), get_path_processed(CSV_RS_OPINIONS), get_path_processed(CSV_LI_CASES),
               get_path_raw(CSV_CASE_CITATIONS), get_path_raw(CSV_LEGISLATION_CITATIONS)]

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
args = parser.parse_args()

print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('INPUT:\t\t\t\t', basename(input_paths[0]), basename(input_paths[1]), basename(input_paths[2]),
      basename(input_paths[3]), basename(input_paths[4]))

if args.storage == 'local':
    # https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.DownloadingAndRunning.html
    online_table = boto3.resource('dynamodb').Table(DDB_TABLE_NAME)
    ddb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")
    ddb.create_table(
        AttributeDefinitions=online_table.attribute_definitions,
        TableName=DDB_TABLE_NAME,
        KeySchema=online_table.key_schema,
        GlobalSecondaryIndexes=online_table.global_secondary_indexes
    )
    TABLE = ddb.Table(DDB_TABLE_NAME)
elif args.storage == 'aws':
    TABLE = boto3.resource('dynamodb').Table(DDB_TABLE_NAME)

# remove all items from table without deleting table itself
#truncate_dynamodb_table(TABLE)


for input_path in input_paths:
    print(f'\n--- PREPARATION {basename(input_path)} ---\n')
    storage = Storage(location=args.storage)
    storage.fetch_data([input_path])
    last_updated = storage.fetch_last_updated([input_path])
    print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

    print(f'\n--- START {basename(input_path)} ---\n')
    
    print(f'Processing {basename(input_path)} ...')
    csv_to_dynamo(input_path, TABLE, processor_map.get(input_path))



end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
