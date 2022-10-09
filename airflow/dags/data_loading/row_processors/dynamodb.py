from definitions.terminology.attribute_names import *
from definitions.storage_handler import *
from definitions.terminology.attribute_values import ItemType, DocType, DataSource

KEY_SEP = '_'  # used to separate compound key values
key_sdd = 'SourceDocDate'  # name of secondary sort key
LI = '_li'  # suffix of attributes from LI data
SET_SEP = '; '  # used to separate set items in string


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

        def row_processor_cellar_cases(row):
            put_items = []
            update_items = []
            update_set_items = []
            for sets in [CELLAR_KEYWORDS, CELLAR_CITING, CELLAR_CITED_BY, CELLAR_SUBJECT_MATTER, CELLAR_DIRECTORY_CODES,
                         CELLAR_COMMENTED_AGENT]:
                add_separated(put_items, row, sets)
            put_items.append({
                self.pk: row[ECLI],
                self.sk: ItemType.DATA.value,
                key_sdd: DataSource.EURLEX.value + KEY_SEP + DocType.DEC.value,
                **row
            })
            return put_items, update_items, update_set_items

        # Method to add items separately, when in the data row they are a list
        def add_separated(list, row, name):
            if name in row:
                for val in row[name].split(SET_SEP):
                    list.append({
                        self.pk: row[ECLI],
                        self.sk: ItemType.DATA.value,
                        key_sdd: DataSource.ECHR.value + KEY_SEP + DocType.DEC.value,
                        name[:-1]: val
                    })

        def row_processor_l_citations(row):
            update_set_items = [{
                self.pk: row[ECLI],
                self.sk: ItemType.DATA.value,
                'legal_provisions': {row[LIDO_ARTIKEL_TITLE]}
            }]
            return [], [], update_set_items

        processor_map = {
            get_path_processed(CSV_RS_CASES): row_processor_rs_cases,
            get_path_processed(CSV_RS_OPINIONS): row_processor_rs_opinions,
            get_path_processed(CSV_LI_CASES): row_processor_li_cases,
            get_path_processed(CSV_CELLAR_CASES): row_processor_cellar_cases,
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
