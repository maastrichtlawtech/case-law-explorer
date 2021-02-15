# %%
import botocore.exceptions
from csv import DictReader
import csv
import sys
from data_to_dynamodb.components.schemas import SchemaCaselaw
from data_to_dynamodb.components.table import Table
from definitions.file_paths import CSV_RS_CASES_PROC, CSV_LI_CASES_PROC, CSV_RS_OPINIONS_PROC, CSV_CASE_CITATIONS, \
    CSV_LEGISLATION_CITATIONS
import time
csv.field_size_limit(sys.maxsize)


def csv_to_dynamo(path_to_csv, table):
    """
    :param path_to_csv:
    :param table:
    :return:
    """
    dynamodb_table = table.dynamodb_table
    schema = table.schema

    case_counter = 0
    item_counter = 0
    with open(path_to_csv, 'r', newline='') as in_file:
        reader = DictReader(in_file)
        # write items in batches to dynamo
        with dynamodb_table.batch_writer(overwrite_by_pkeys=[schema.PK_ecli, schema.SK_id.name]) as batch:
            # for each row in csv:
            for row in reader:
                case_counter += 1
                if row != '':
                    items = schema.row_processor(path_to_csv, row)
                    for item in items:
                        item_counter += 1
                        try:
                            batch.put_item(Item=item)
                            # batch.put_item(Item=item, ConditionExpression='attribute_not_exists(ecli)')
                            # batch.put_item(Item=item, ConditionExpression=Attr('ecli').not_exists())
                        except botocore.exceptions.ClientError:
                            dynamodb_table.put_item(Item=item)

    print(f'{case_counter} cases ({item_counter} items) added.')


start = time.time()

caselaw_table = Table('caselaw-v2', SchemaCaselaw(), local=True)

print('Uploading RS cases...')
csv_to_dynamo(CSV_RS_CASES_PROC, caselaw_table)

print('\nProcessing RS opinions...')
csv_to_dynamo(CSV_RS_OPINIONS_PROC, caselaw_table)

print('\nProcessing LI cases...')
csv_to_dynamo(CSV_LI_CASES_PROC, caselaw_table)

print('\nProcessing case citations...')
csv_to_dynamo(CSV_CASE_CITATIONS, caselaw_table)

print('\nProcessing legislation citations...')
csv_to_dynamo(CSV_LEGISLATION_CITATIONS, caselaw_table)

end = time.time()
print("\n\nTime taken: ", (end - start), "s")
