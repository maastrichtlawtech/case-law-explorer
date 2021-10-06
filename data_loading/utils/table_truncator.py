"""
taken from https://stackoverflow.com/questions/55169952/delete-all-items-dynamodb-using-python
"""


def truncate_dynamodb_table(table):
    """
    Removes all items from a given DynamoDB table without deleting the table itself.
    :param table: DynamoDB table instance
    """
    # get the table keys
    key_names = [key.get("AttributeName") for key in table.key_schema]

    # Only retrieve the keys for each item in the table (minimize data transfer)
    projection_expression = ", ".join('#' + key for key in key_names)
    expression_attr_names = {'#' + key: key for key in key_names}

    counter = 0
    page = table.scan(ProjectionExpression=projection_expression, ExpressionAttributeNames=expression_attr_names)
    with table.batch_writer() as batch:
        while page["Count"] > 0:
            counter += page["Count"]
            # Delete items in batches
            for item_keys in page["Items"]:
                batch.delete_item(Key=item_keys)
            # Fetch the next page
            if 'LastEvaluatedKey' in page:
                page = table.scan(
                    ProjectionExpression=projection_expression, ExpressionAttributeNames=expression_attr_names,
                    ExclusiveStartKey=page['LastEvaluatedKey'])
            else:
                break
    print(f"Deleted {counter} items.")
