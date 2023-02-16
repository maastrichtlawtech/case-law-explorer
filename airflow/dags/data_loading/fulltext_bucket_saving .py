import boto3
import os
from definitions.storage_handler import Storage, CSV_RS_CASES, CSV_LI_CASES, CSV_RS_OPINIONS, CSV_CASE_CITATIONS, \
    CSV_LEGISLATION_CITATIONS, get_path_processed, get_path_raw,CSV_CELLAR_CASES,CSV_ECHR_CASES, JSON_FULL_TEXT_CELLAR, \
    JSON_FULL_TEXT_ECHR
from dotenv import load_dotenv
load_dotenv() 

region = getenv('AWS_REGION')
bucket_name = 'full-text-data'
s3 = boto3.resource('s3')

# if bucket dont exist, create it
if s3.Bucket(bucket_name) not in s3.buckets.all():
    s3.create_bucket(Bucket=bucket_name)

def upload_fulltext():
    files_location_path = [JSON_FULL_TEXT_CELLAR,JSON_FULL_TEXT_ECHR]
    # for the files location check the json files exist or not in the path, if exists then upload the json into bucket
    for file_location_path in files_location_path:
        if not os.path.exists(file_location_path):
            print(f"FILE {file_location_path} DOES NOT EXIST")
            continue
        with file_location_path.open('rb') as f:
            s3.upload_fileobj(f, bucket_name, file_location_path)
            print(f"FILE {file_location_path} UPLOADED")



if __name__ == '__main__':
    upload_fulltext()


