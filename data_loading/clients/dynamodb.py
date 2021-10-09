import boto3
import logging
import sys
import botocore

# to be able to deploy your DynamoDB table locally, follow these steps first:
# https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.DownloadingAndRunning.html


class DynamoDBClient:
    def __init__(self, table_name, storage='aws'):
        ddb = boto3.resource('dynamodb')
        if table_name not in [table.name for table in ddb.tables.all()]:
            logging.error(f'DynamoDB table {table_name} does not exist! Create table first and try again.')
            sys.exit(2)
        self.table = ddb.Table(table_name)
        if storage == 'local':
            ddb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")
            gs_indexes = []
            for gsi in self.table.global_secondary_indexes:
                gs_indexes.append({
                    'IndexName': gsi['IndexName'],
                    'KeySchema': gsi['KeySchema'],
                    'Projection': gsi['Projection'],
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': gsi['ProvisionedThroughput']['ReadCapacityUnits'],
                        'WriteCapacityUnits': gsi['ProvisionedThroughput']['WriteCapacityUnits']
                    }
                })
            try:
                ddb.create_table(
                    AttributeDefinitions=self.table.attribute_definitions,
                    TableName=self.table.name,
                    KeySchema=self.table.key_schema,
                    GlobalSecondaryIndexes=gs_indexes,
                    ProvisionedThroughput={
                        'ReadCapacityUnits': self.table.provisioned_throughput['ReadCapacityUnits'],
                        'WriteCapacityUnits': self.table.provisioned_throughput['WriteCapacityUnits']
                    }
                )
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Code'] == 'ResourceInUseException':
                    print('Table already exists.')
                else:
                    raise error
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
