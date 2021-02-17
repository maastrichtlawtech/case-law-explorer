from definitions.terminology.field_names import ECLI, ECLI_DECISION, ECLI_OPINION, RS_SUBJECT, LI_LAW_AREA, RS_RELATION, LIDO_JURISPRUDENTIE, RS_REFERENCES, LIDO_ARTIKEL_TITLE, RS_DATE, LI_ENACTMENT_DATE, RS_CREATOR
from definitions.file_paths import CSV_RS_CASES_PROC, CSV_RS_OPINIONS_PROC, CSV_LI_CASES_PROC, CSV_CASE_CITATIONS, CSV_LEGISLATION_CITATIONS
from data_to_dynamodb.components.keys import KeyDocSourceId, KeySourceDocDate
from data_to_dynamodb.components.types import Source, DocType


class SchemaCaselaw:
    def __init__(self):
        self.PK_ecli = ECLI
        self.SK_id = KeyDocSourceId()
        self.SK_date = KeySourceDocDate()
        self.PK_instance = RS_CREATOR

        self.key_schema = [
            {  # partition key
                'AttributeName': self.PK_ecli,
                'KeyType': 'HASH'
            },
            {  # sort key
                'AttributeName': self.SK_id.name,
                'KeyType': 'RANGE'
            }
        ]

        self.attribute_definitions = [
            {
                'AttributeName': self.PK_ecli,  # can be decision ecli or opinion ecli
                'AttributeType': 'S'
            },
            {
                'AttributeName': self.SK_id.name,  # see above
                'AttributeType': 'S'
            },
            {
                "AttributeName": self.SK_date.name,  #
                "AttributeType": 'S'
            },
            {
                "AttributeName": self.PK_instance,  # name of instance
                "AttributeType": 'S'
            }
        ]

        self.global_secondary_indexes = [
            {
                'IndexName': 'GSI-' + self.SK_id.name,
                'KeySchema': [
                    {
                        'AttributeName': self.SK_id.name,
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': self.SK_date.name,
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
                'IndexName': 'GSI-' + self.PK_instance,
                'KeySchema': [
                    {
                        'AttributeName': self.PK_instance,
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': self.SK_date.name,
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
        ]

        self.provisioned_throughput = {
            'ReadCapacityUnits': 20,
            'WriteCapacityUnits': 20
        }

    def row_processor(self, path, row):
        if path == CSV_RS_CASES_PROC:
            return self.__row_processor_rs_cases(row)
        elif path == CSV_RS_OPINIONS_PROC:
            return self.__row_processor_rs_opinions(row)
        elif path == CSV_LI_CASES_PROC:
            return self.__row_processor_li_cases(row)
        elif path == CSV_CASE_CITATIONS:
            return self.__row_processor_c_citations(row)
        elif path == CSV_LEGISLATION_CITATIONS:
            return self.__row_processor_l_citations(row)
        else:
            print(f'No row processor defined for csv {path}!')

    def __row_processor_rs_cases(self, row):
        """
        turns csv row (1 RS case) into item(s) for DynamoDB table according to this schema
        :param row: dict representation of csv row with RS case attributes
        :return: list of dict representation of items in schema format
        """
        items = []
        # split set attributes (domain, case citations, legislation citations)
        for attribute, doctype in {RS_SUBJECT: DocType.DOM,
                                   RS_RELATION: DocType.C_CIT,
                                   RS_REFERENCES: DocType.L_CIT}.items():
            if row[attribute] != '':
                for val in row[attribute].split('; '):
                    items.append({
                        self.PK_ecli: row[ECLI],
                        **self.SK_id.set_value(doc_type=doctype, source=Source.RS, doc_id=val),
                        attribute[:-1]: val
                    })
            row.pop(attribute)
        items.append({
            **self.SK_id.set_value(doc_type=DocType.DEC, source=Source.RS, doc_id=row[ECLI]),
            **self.SK_date.set_value(source=Source.RS, doc_type=DocType.DEC, date_decision=row[RS_DATE]),
            **row
        })
        return items

    def __row_processor_rs_opinions(self, row):
        row.pop(RS_SUBJECT)
        items = [{
            **self.SK_id.set_value(doc_type=DocType.OPI, source=Source.RS, doc_id=row[ECLI]),
            **self.SK_date.set_value(source=Source.RS, doc_type=DocType.OPI, date_decision=row[RS_DATE]),
            **row
        }]
        if row[ECLI_DECISION] != '':
            items.append({
                self.PK_ecli: row[ECLI],
                **self.SK_id.set_value(doc_type=DocType.DEC, source=Source.RS, doc_id=row[ECLI_DECISION]),
                ECLI_DECISION: row[ECLI_DECISION]
            })
            items.append({
                self.PK_ecli: row[ECLI_DECISION],
                **self.SK_id.set_value(doc_type=DocType.OPI, source=Source.RS, doc_id=row[ECLI]),
                ECLI_OPINION: row[ECLI]
            })
        return items

    def __row_processor_li_cases(self, row):
        items = []
        if row[LI_LAW_AREA] != '':
            for val in row[LI_LAW_AREA].split('; '):
                items.append({
                    self.PK_ecli: row[ECLI],
                    **self.SK_id.set_value(doc_type=DocType.DOM, source=Source.LI, doc_id=val),
                    LI_LAW_AREA[:-1]: row[LI_LAW_AREA]
                })
        row.pop(LI_LAW_AREA)
        items.append({
            **self.SK_id.set_value(doc_type=DocType.DEC, source=Source.LI, doc_id=row[ECLI]),
            **self.SK_date.set_value(source=Source.LI, doc_type=DocType.DEC, date_decision=row[LI_ENACTMENT_DATE]),
            **row
        })
        return items

    def __row_processor_c_citations(self, row):
        items = [{
            self.PK_ecli: row[ECLI],
            **self.SK_id.set_value(doc_type=DocType.C_CIT, source=Source.LIDO, doc_id=row[LIDO_JURISPRUDENTIE]),
            **row
        }]
        return items

    def __row_processor_l_citations(self, row):
        items = [{self.PK_ecli: row[ECLI],
                  **self.SK_id.set_value(doc_type=DocType.L_CIT, source=Source.LIDO, doc_id=row[LIDO_ARTIKEL_TITLE]),
                  **row}]
        return items
