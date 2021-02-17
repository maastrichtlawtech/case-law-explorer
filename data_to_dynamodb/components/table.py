import boto3


class Table:
    def __init__(self, name, schema, local=False):
        self.name = name
        self.schema = schema
        if local:
            resource = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")
        else:
            resource = boto3.resource('dynamodb')
        try:
            self.dynamodb_table = resource.create_table(
                TableName=self.name,
                KeySchema=self.schema.key_schema,
                AttributeDefinitions=self.schema.attribute_definitions,
                GlobalSecondaryIndexes=self.schema.global_secondary_indexes,
                ProvisionedThroughput=self.schema.provisioned_throughput
            )
        except resource.meta.client.exceptions.ResourceInUseException:
            self.dynamodb_table = resource.Table(self.name)
        except resource.meta.client.exceptions.ResourceNotFoundException:
            self.dynamodb_table = resource.Table(self.name)
        print("Table status:", self.dynamodb_table.table_status)
