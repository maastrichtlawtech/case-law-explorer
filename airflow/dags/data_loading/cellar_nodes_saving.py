import boto3
import os
from os import getenv
from os.path import basename
from definitions.storage_handler import get_path_raw, TXT_CELLAR_NODES, TXT_CELLAR_EDGES
from dotenv import load_dotenv
load_dotenv()

bucket_name = getenv('CELLAR_NODES_BUCKET_NAME')  # .env file instead?
region = getenv('AWS_REGION')
location = {'LocationConstraint': region}
access_key = getenv('AWS_ACCESS_KEY_ID')
secret_key = getenv('AWS_SECRET_ACCESS_KEY')
s3 = boto3.resource('s3')


def upload_nodes():
    paths = [get_path_raw(TXT_CELLAR_NODES), get_path_raw(TXT_CELLAR_EDGES)]
    if s3.Bucket(bucket_name) not in s3.buckets.all():
        print(f"Bucket {bucket_name} does not exist. Creating bucket...")
        s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration=location)
    else:
        print(f"Bucket {bucket_name} already exists. Updating bucket...")
    for path in paths:
        if not os.path.exists(path):
            print(f"FILE {path} DOES NOT EXIST")
            continue
        with open(path,'r') as f:
            data = f.read()
        print(f'Processing {basename(path)} ...')
        try:
            obj = s3.Object(bucket_name=bucket_name,key=basename(path))
            response = obj.get()
            old_data=response['Body'].read().decode("utf-8")
            print('File already exists, merging 2 files....')

            old_data_set = set(old_data.splitlines())
            new_data = data.splitlines()

            old_data_set.update(new_data)

            merged = '\n'.join(old_data_set)

            s3.Object(bucket_name, basename(path)).put(Body=merged)
        except:# file does not exist
            print('File does not yet exist on the bucket. Uploading...')
            s3.Object(bucket_name=bucket_name, key=basename(path)).put(Body=data)
        os.remove(path)



if __name__ == '__main__':
    upload_nodes()


