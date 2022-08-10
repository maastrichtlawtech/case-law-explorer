from os.path import dirname, abspath, basename
from csv import DictReader
import os
import sys
import boto3
import logging
import time

correct_dir = dirname(dirname(abspath(__file__)))
sys.path.append(correct_dir)
from definitions.storage_handler import Storage, CSV_ECHR_CASES, CSV_RS_CASES, CSV_RS_OPINIONS, CSV_LI_CASES, CSV_CASE_CITATIONS, CSV_LEGISLATION_CITATIONS, get_path_raw, get_path_processed
from definitions.terminology.attribute_names import ECLI, ECLI_DECISION, ECLI_OPINION, RS_SUBJECT, LI_LAW_AREA, RS_RELATION, LIDO_JURISPRUDENTIE, RS_REFERENCES, LIDO_ARTIKEL_TITLE, RS_DATE, ECHR_ARTICLES, ECHR_APPLICABLE_ARTICLES, ECHR_JUDGEMENT_DATE
from definitions.terminology.attribute_values import ItemType, DocType, DataSource

start = time.time()

KEY_SEP = '_'               # used to separate compound key values
key_sdd = 'SourceDocDate'   # name of secondary sort key
LI = '_li'                  # suffix of attributes from LI data
SET_SEP = '; '              # used to separate set items in string

class DynamoDBClient:
    def __init__(
            self, table_name,
            hash_key_name='ecli',
            range_key_name='ItemType',
            hash_key_type='S',
            range_key_type='S'
    ):
        ddb = boto3.resource("dynamodb", endpoint_url = "http://localhost:8000", region_name = "eu-central-1", aws_access_key_id = "local", aws_secret_access_key = "local") 
        if table_name not in [table.name for table in ddb.tables.all()]:
            ddb.create_table(
                AttributeDefinitions=[
                    {
                        'AttributeName': hash_key_name,
                        'AttributeType': hash_key_type
                    },
                    {
                        'AttributeName': range_key_name,
                        'AttributeType': range_key_type
                    },
                ],
                TableName=table_name,
                KeySchema=[
                    {
                        'AttributeName': hash_key_name,
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': range_key_name,
                        'KeyType': 'RANGE'
                    },
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            logging.warning(f'\nDynamoDB table {table_name} does not exist yet. '
                            f'A table with this name and default settings will be created.')
        self.table = ddb.Table(table_name)

    def truncate_table(self):
        """
        taken from https://stackoverflow.com/questions/55169952/delete-all-items-dynamodb-using-python

        Removes all items from a given DynamoDB table without deleting the table itself.
        :param table: DynamoDB table instance
        """
        # get the table keys
        key_names = [key.get("AttributeName") for key in self.table.key_schema]

        # Only retrieve the keys for each item in the table (minimize data transfer)
        projection_expression = ", ".join('#' + key for key in key_names)
        expression_attr_names = {'#' + key: key for key in key_names}

        counter = 0
        page = self.table.scan(
            ProjectionExpression=projection_expression,
            ExpressionAttributeNames=expression_attr_names
        )
        with self.table.batch_writer() as batch:
            while page["Count"] > 0:
                counter += page["Count"]
                # Delete items in batches
                for item_keys in page["Items"]:
                    batch.delete_item(Key=item_keys)
                # Fetch the next page
                if 'LastEvaluatedKey' in page:
                    page = self.table.scan(
                        ProjectionExpression=projection_expression,
                        ExpressionAttributeNames=expression_attr_names,
                        ExclusiveStartKey=page['LastEvaluatedKey']
                    )
                else:
                    break
        print(f"Deleted {counter} items.")

class DynamoDBRowProcessor:
    def __init__(self, path, table):
        self.table = table
        self.path = path
        schema = self.table.key_schema
        if schema[0]['KeyType'] == 'HASH':
            self.pk = schema[0]['AttributeName']
            self.sk = schema[1]['AttributeName']
        else:
            self.pk = schema[1]['AttributeName']
            self.sk = schema[0]['AttributeName']
        self.row_processor = self._get_row_processor()

    def _get_row_processor(self):
        def row_processor_rs_cases(row):
            """
            turns csv row (1 RS case) into item(s) for DynamoDB table according to this schema
            :param row: dict representation of csv row with RS case attributes
            :return: list of dict representation of items in schema format
            """
            put_items = []
            update_set_items = []
            # split set attributes (domain, case citations, legislation citations)
            if RS_SUBJECT in row:
                for val in row[RS_SUBJECT].split(SET_SEP):
                    put_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DOM.value + KEY_SEP + val,
                        key_sdd: DataSource.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                        RS_SUBJECT[:-1]: val
                    })
            for attribute in [RS_RELATION, RS_REFERENCES, RS_SUBJECT]:
                if attribute in row:
                    update_set_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DATA.value,
                        attribute: set(row[attribute].split(SET_SEP))
                    })
                    row.pop(attribute)
            put_items.append({
                self.sk: ItemType.DATA.value,
                key_sdd: DataSource.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                **row
            })
            return put_items, [], update_set_items

        def row_processor_rs_opinions(row):
            put_items = []
            update_items = []
            update_set_items = []
            if RS_SUBJECT in row:
                for val in row[RS_SUBJECT].split(SET_SEP):
                    put_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DOM.value + KEY_SEP + val,
                        key_sdd: DataSource.RS.value + KEY_SEP + DocType.OPI.value + KEY_SEP + row[RS_DATE],
                        RS_SUBJECT[:-1]: val
                    })
            # split set attributes (domain, case citations, legislation citations)
            for attribute in [RS_RELATION, RS_REFERENCES, RS_SUBJECT]:
                if attribute in row:
                    update_set_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DATA.value,
                        attribute: set(row[attribute].split(SET_SEP))
                    })
                    row.pop(attribute)
            put_items.append({
                self.sk: ItemType.DATA.value,
                key_sdd: DataSource.RS.value + KEY_SEP + DocType.OPI.value + KEY_SEP + row[RS_DATE],
                **row
            })
            if ECLI_DECISION in row:
                update_items.append({
                    self.pk: row[ECLI_DECISION],
                    self.sk: ItemType.DATA.value,
                    ECLI_OPINION: row[ECLI]
                })
            return put_items, update_items, update_set_items

        def row_processor_li_cases(row):
            put_items = []
            update_items = []
            update_set_items = []
            row_li = dict()
            for key in row.keys() - ECLI:
                row_li[key + LI] = row[key]
            if LI_LAW_AREA in row:
                for val in row[LI_LAW_AREA].split(SET_SEP):
                    put_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DOM_LI.value + KEY_SEP + val,
                        key_sdd: DataSource.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                        LI_LAW_AREA[:-1] + LI: val
                    })
                update_set_items.append({
                    self.pk: row[ECLI],
                    self.sk: ItemType.DATA.value,
                    LI_LAW_AREA + LI: set(row[LI_LAW_AREA].split(SET_SEP))
                })
                row_li.pop(LI_LAW_AREA + LI)
            update_items.append({
                self.pk: row[ECLI],
                self.sk: ItemType.DATA.value,
                key_sdd: DataSource.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                **row_li
            })
            return put_items, update_items, update_set_items

        # @TODO: replace attribute names with global definition
        def row_processor_c_citations(row):
            update_set_items = []
            if row['keep1'] == 'True':
                update_set_items = [{
                    self.pk: row[ECLI],
                    self.sk: ItemType.DATA.value,
                    'cites': {row[LIDO_JURISPRUDENTIE]}
                }, {
                    self.pk: row[LIDO_JURISPRUDENTIE],
                    self.sk: ItemType.DATA.value,
                    'cited_by': {row[ECLI]}
                }]
            return [], [], update_set_items

        def row_processor_l_citations(row):
            update_set_items = [{
                self.pk: row[ECLI],
                self.sk: ItemType.DATA.value,
                'legal_provisions': {row[LIDO_ARTIKEL_TITLE]}
            }]
            return [], [], update_set_items

        def row_processor_echr_cases(row):
            put_items = []
            update_set_items = []
            # split set attributes (domain, case citations, legislation citations)
            if ECHR_ARTICLES in row:
                for val in row[ECHR_ARTICLES].split(SET_SEP):
                    put_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DOM.value + KEY_SEP + val,
                        key_sdd: DataSource.ECHR.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[ECHR_JUDGEMENT_DATE],
                        ECHR_ARTICLES[:-1]: val
                    })
            for attribute in [ECHR_APPLICABLE_ARTICLES, ECHR_ARTICLES]:
                if attribute in row:
                    update_set_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DATA.value,
                        attribute: set(row[attribute].split(SET_SEP))
                    })
                    row.pop(attribute)
            put_items.append({
                self.sk: ItemType.DATA.value,
                key_sdd: DataSource.ECHR.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[ECHR_JUDGEMENT_DATE],
                **row
            })
            return put_items, [], update_set_items

        processor_map = {
            get_path_processed(CSV_RS_CASES): row_processor_rs_cases,
            get_path_processed(CSV_RS_OPINIONS): row_processor_rs_opinions,
            get_path_processed(CSV_LI_CASES): row_processor_li_cases,
            get_path_processed(CSV_ECHR_CASES): row_processor_echr_cases,
            get_path_raw(CSV_CASE_CITATIONS): row_processor_c_citations,
            get_path_raw(CSV_LEGISLATION_CITATIONS): row_processor_l_citations
        }
        return processor_map.get(self.path)

    def _extract_attributes(self, item_obj):
        item = item_obj.copy()
        pk_val = item.pop(self.pk)
        sk_val = item.pop(self.sk)
        atts = list(item.keys())
        vals = list(item.values())
        expr_att_names = dict()
        expr_att_values = dict()
        for i in range(len(atts)):
            expr_att_names['#' + str(i)] = atts[i]
            expr_att_values[':' + str(i)] = vals[i]
        return pk_val, sk_val, expr_att_names, expr_att_values

    def upload_row(self, row):
        item_counter = 0
        # retrieve lists of items to put and update
        put_items, update_items, update_set_items = self.row_processor(row)

        # add items
        for item in put_items:
            try:
                self.table.put_item(Item=item)
                item_counter += 1
            except Exception as e:
                print(e, item[self.pk], item[self.sk])
                with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                    f.write(item[self.pk] + '\n')

        # update item attributes
        for item in update_items:
            try:
                pk_val, sk_val, expression_att_names, expression_att_values = self._extract_attributes(item)
                update_expression = 'SET ' + ', '.join(list(expression_att_names.keys())[i] + '=' +
                                                       list(expression_att_values.keys())[i]
                                                       for i in range(len(expression_att_names)))
                self.table.update_item(
                    Key={self.pk: pk_val, self.sk: sk_val},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_att_names,
                    ExpressionAttributeValues=expression_att_values
                )
            except Exception as e:
                print(e, item[self.pk], item[self.sk])
                with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                    f.write(item[self.pk] + '\n')

        # update item set attributes
        for item in update_set_items:
            try:
                pk_val, sk_val, expression_att_names, expression_att_values = self._extract_attributes(item)
                update_expression = f'ADD {list(expression_att_names.keys())[0]} {list(expression_att_values.keys())[0]}'
                self.table.update_item(
                    Key={self.pk: pk_val, self.sk: sk_val},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_att_names,
                    ExpressionAttributeValues={
                        list(expression_att_values.keys())[0]: list(expression_att_values.values())[0]
                    }
                )
            except Exception as e:
                print(e, item[self.pk], item[self.sk])
                with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                    f.write(item[self.pk] + '\n')

        return item_counter

input_path = get_path_processed(CSV_ECHR_CASES)
#input_path = get_path_processed(CSV_RS_CASES)
print(f'\n--- PREPARATION {basename(input_path)} ---\n')
#storage = Storage(location='aws')
storage = Storage(location='local')
storage.fetch_data([input_path])
last_updated = storage.fetch_last_updated([input_path])
print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())
print(f'\n--- START {basename(input_path)} ---\n')
print(f'Processing {basename(input_path)} ...')
ddb_client = DynamoDBClient(os.getenv('DDB_TABLE_NAME'))
ddb_rp = DynamoDBRowProcessor(input_path, ddb_client.table)
case_counter = 0
ddb_item_counter = 0
with open(input_path, 'r', newline='') as in_file:
	reader = DictReader(in_file)
	for row in reader:
		if row != '':
			atts = list(row.items())
			for att in atts:
				if att[1] == '':
					row.pop(att[0])
			ddb_item_counter += ddb_rp.upload_row(row)
		case_counter += 1
		if case_counter%1000 == 0:
			print(case_counter, "rows processed")
	print(f"{case_counter} cases ({ddb_item_counter} ddb items) added.")

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

#table = ddb_client.table
#table.delete()
#print(ddb_client.table.scan())