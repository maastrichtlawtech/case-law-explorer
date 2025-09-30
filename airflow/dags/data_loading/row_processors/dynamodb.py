from definitions.storage_handler import *
from definitions.terminology.attribute_names import *
from definitions.terminology.attribute_values import ItemType, DocType, DataSource

KEY_SEP = '_'  # used to separate compound key values
key_sdd = 'SourceDocDate'  # name of secondary sort key
LI = '_li'  # suffix of attributes from LI data
SET_SEP = '; '  # used to separate set items in string


class DynamoDB_RS_Processor:
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
            turns csv row (1 RS case) into item(s) for DynamoDB table 
            according to this schema
            :param row: dict representation of csv row with RS case attributes
            :return: list of dict representation of items in schema format
            """
            put_items = []
            update_set_items = []
            # split set attributes (domain, case citations, legislation citations)
            # RS_SUBJECT is "domains"
            if RS_SUBJECT in row:
                for val in row[RS_SUBJECT].split(SET_SEP):
                    put_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DOM.value + KEY_SEP + val,
                        key_sdd: DataSource.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                        RS_SUBJECT[:-1]: val
                    })
            # Why are we separating these here? 
            for attribute in [RS_RELATION, RS_REFERENCES, RS_SUBJECT]:
                if attribute in row:
                    update_set_items.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DATA.value,
                        attribute: set(row[attribute].split(SET_SEP))
                    })
                    row.pop(attribute)
<<<<<<< HEAD
            put_items.append({
                self.pk: row[ECLI],
                self.sk: ItemType.DATA.value,
                key_sdd: DataSource.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                **row
            })
=======
            if ECLI in row:
                put_items.append({
                    self.pk: row[ECLI],
                    self.sk: ItemType.DATA.value,
                    key_sdd: DataSource.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                    **row
                })
            else:
                print(f"NO ECLI FOUND")
>>>>>>> origin/airflow
            return put_items, [], update_set_items

        return row_processor_rs_cases

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
        for item in put_items:
            if item[self.pk] and item[self.sk]:
                try:
                    self.table.put_item(Item=item)
                    item_counter += 1
                except Exception as e:
                    print(e, item[self.pk], item[self.sk], ";while retreving lists of items to put and update")
                    with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                        f.write(item[self.pk] + '\n')
<<<<<<< HEAD
                        f.write(e + '\n')
=======
                        f.write(str(e) + '\n')
>>>>>>> origin/airflow

        # update item attributes
        for item in update_items:
            if item[self.pk] and item[self.sk]:
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
                    print(e, item[self.pk], item[self.sk], ";while updating item attributes")
                    with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                        f.write(item[self.pk] + '\n')
<<<<<<< HEAD
                        f.write(e + '\n')
=======
                        f.write(str(e) + '\n')
>>>>>>> origin/airflow

        # update item set attributes
        for item in update_set_items:
            if item[self.pk] and item[self.sk]:
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
                    print(e, item[self.pk], item[self.sk], ";while updating item set attributes")
                    with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                        f.write(item[self.pk] + '\n')
<<<<<<< HEAD
                        f.write(e + '\n')
=======
                        f.write(str(e) + '\n')
>>>>>>> origin/airflow

        return item_counter


class DynamoDBRowCelexProcessor:
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

        def row_processor_cellar_cases(row):
            put_items = []
            update_items = []
            update_set_items = []
            put_items.append({
                self.pk: row[CELLAR_CELEX],
                self.sk: 'cellar',
                key_sdd: DataSource.EURLEX.value + KEY_SEP + DocType.DEC.value,
                **row
            })
            return put_items, update_items, update_set_items

        return row_processor_cellar_cases

    def upload_row(self, row):
        item_counter = 0
        # retrieve lists of items to put and update
        put_items, update_items, update_set_items = self.row_processor(row)
        for item in put_items:
            try:
                self.table.put_item(Item=item)
                item_counter += 1
            except Exception as e:
                print(e, item[self.pk], item[self.sk], ";while retreving lists of items to put and update")
                with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                    f.write(item[self.pk] + '\n')
                    f.write(str(e) + '\n')

        return item_counter


class DynamoDBRowItemidProcessor:
    '''
    This class is used to upload rows to DynamoDB table
    Item id is the primary key. Due to trasformation, key is renamed to document_id
    '''

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
        def row_processor_echr(row):
            put_items = []
            update_set_items = []
            if ECHR_ARTICLES in row:
                for val in row[ECHR_ARTICLES].split(SET_SEP):
                    put_items.append({
                        self.pk: row[ECHR_DOCUMENT_ID],
                        self.sk: ItemType.DOM.value + KEY_SEP + val,
                        key_sdd: DataSource.ECHR.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[
                            ECHR_JUDGMENT_DATE],
                        ECHR_ARTICLES[:-1]: val
                    })
            for attribute in [ECHR_ARTICLES]:
                if attribute in row:
                    update_set_items.append({
                        self.pk: row[ECHR_DOCUMENT_ID],
                        self.sk: ItemType.DATA.value,
                        attribute: set(row[attribute].split(SET_SEP))
                    })
                    row.pop(attribute)
            put_items.append({
                self.pk: row[ECHR_DOCUMENT_ID],
                self.sk: ItemType.DATA.value,
                key_sdd: DataSource.ECHR.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[ECHR_JUDGMENT_DATE],
                **row
            })
            return put_items, [], update_set_items

        return row_processor_echr

    def upload_row(self, row):
        item_counter = 0
        # retrieve lists of items to put and update
        put_items, update_items, update_set_items = self.row_processor(row)
        for item in put_items:
            # print(item)
            try:
                self.table.put_item(Item=item)
                item_counter += 1
            except Exception as e:
                print(e, item[self.pk], item[self.sk], ";while retreving lists of items to put and update")
                with open(get_path_processed(CSV_DDB_ECLIS_FAILED), 'a') as f:
                    f.write(item[self.pk] + '\n')
                    f.write(str(e) + '\n')

        return item_counter
