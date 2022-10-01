import boto3
import logging


class DynamoDBClient:
    def __init__(
            self, table_name,
            hash_key_name='ecli',
            range_key_name='ItemType',
            hash_key_type='S',
            range_key_type='S'
    ):

        ddb = boto3.resource('dynamodb')
        #ddb = boto3.resource("dynamodb", endpoint_url = "http://localhost:8000", region_name = "eu-central-1",
                 #             aws_access_key_id = "local", aws_secret_access_key = "local")                                     #for local testing

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
