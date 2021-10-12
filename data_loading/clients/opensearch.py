import boto3
import botocore
import time
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import os
import sys


class OpenSearchServiceClient:
    """
    taken from:
    https://docs.aws.amazon.com/opensearch-service/latest/developerguide/configuration-samples.html#configuration-samples-python
    """
    def __init__(self, domain_name):
        self.oss = boto3.client('opensearch')
        self.domain_name = domain_name

    def create_domain(self, instance_type, instance_count, storage_size):
        """Creates an Amazon OpenSearch Service domain with the specified options.
        If a domain with the same name already exists, no error is reported
        but the details for the existing domain are returned."""
        self.oss.create_domain(
            DomainName=self.domain_name,
            ClusterConfig={
                'InstanceType': instance_type,
                'InstanceCount': instance_count,
                'DedicatedMasterEnabled': False,
            },
            # Many instance types require EBS storage.
            EBSOptions={
                'EBSEnabled': True,
                'VolumeType': 'gp2',
                'VolumeSize': storage_size
            },
            NodeToNodeEncryptionOptions={
                'Enabled': True
            }
        )
        print("Creating domain...")
        self.wait_for_domain_processing()

    def update_domain(self):
        """Updates the domain to use three data nodes instead of five."""
        try:
            self.oss.update_domain_config(
                DomainName=self.domain_name,
                ClusterConfig={
                    'InstanceCount': 3
                }
            )
            print('Sending domain update request...')
            self.wait_for_domain_processing()

        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ResourceNotFoundException':
                print('Domain not found. Please check the domain name.')
            else:
                raise error

    def delete_domain(self):
        """Deletes an OpenSearch Service domain. Deleting a domain can take several minutes."""
        try:
            self.oss.delete_domain(DomainName=self.domain_name)
            print('Sending domain deletion request...')
            self.wait_for_domain_processing()

        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ResourceNotFoundException':
                print('Domain not found. Please check the domain name.')
            else:
                raise error

    def wait_for_domain_processing(self):
        """Waits for the domain to finish processing changes."""
        try:
            response = self.oss.describe_domain(DomainName=self.domain_name)
            # Every 15 seconds, check whether the domain is processing.
            while response["DomainStatus"]["Processing"]:
                print('Domain still processing...')
                time.sleep(15)
                response = self.oss.describe_domain(DomainName=self.domain_name)

            # Once we exit the loop, the domain is available.
            print('Amazon OpenSearch Service has finished processing changes for your domain.')
            #print('Domain description:')
            #print(response)

        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ResourceNotFoundException':
                print('Domain not found. Please check the domain name.')
            else:
                raise error


class OpenSearchClient(OpenSearchServiceClient):
    def __init__(self, domain_name, index_name, instance_type='t3.small.search', instance_count=1, storage_size=40):
        super().__init__(domain_name)
        self.index_name = index_name
        # create domain (nothing happens, if domain already exists)
        self.create_domain(instance_type=instance_type, instance_count=instance_count, storage_size=storage_size)

        aws_auth = AWS4Auth(
            os.getenv('AWS_ACCESS_KEY_ID'),
            os.getenv('AWS_SECRET_ACCESS_KEY'),
            os.getenv('AWS_REGION'),
            'es',
            session_token=os.getenv('AWS_SESSION_TOKEN')
        )
        self.es = OpenSearch(
            hosts=[{
                'host': self.oss.describe_domain(DomainName=self.domain_name)['DomainStatus']['Endpoint'],
                'port': 443,
                'use_ssl': True
            }],
            http_auth=aws_auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30
        )

        # create index, if it doesn't exist
        if not self.es.indices.exists(index=self.index_name):
            response = self.es.indices.create(
                index=self.index_name,
                body={
                    'mappings': {
                        'properties': {
                            'ecli': {'type': 'keyword'},
                            'SourceDocDate': {'type': 'keyword'},
                            'ItemType': {'type': 'keyword'},
                            'document_type': {'type': 'keyword'},
                            'domains': {'type': 'keyword'},
                            'domains_li': {'type': 'keyword'},
                            'ecli_decision': {'type': 'keyword'},
                            'ecli_opinion': {'type': 'keyword'},
                            'instance': {'type': 'keyword'},
                            'instance_li': {'type': 'keyword'},
                            'jurisdiction_country': {'type': 'keyword'},
                            'jurisdiction_country_li': {'type': 'keyword'},
                            'language': {'type': 'keyword'},
                            'procedure_type': {'type': 'keyword'},
                            'source': {'type': 'keyword'},
                            'source_li': {'type': 'keyword'},
                            'cites': {'type': 'keyword'},
                            'cited_by': {'type': 'keyword'},
                            'date_decision': {'type': 'date', 'format': 'yyyy-MM-dd'},
                            'date_decision_li': {'type': 'date', 'format': 'yyyy-MM-dd'}
                        }
                    }
                },
                wait_for_active_shards=1
            )
            print('\nCreating index:')
            print(response)
