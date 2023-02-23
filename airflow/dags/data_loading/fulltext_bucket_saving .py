import boto3
import json
import os,sys
import argparse
from os import getenv,basename,dirname, abspath
sys.path.append(dirname(dirname(abspath(__file__))))
from definitions.storage_handler import Storage, JSON_FULL_TEXT_CELLAR, \
    JSON_FULL_TEXT_ECHR
from dotenv import load_dotenv
load_dotenv() 

bucket_name = 'full-text-data'

region = getenv('AWS_REGION')
access_key = getenv('AWS_ACCESS_KEY_ID')
secret_key = getenv('AWS_SECRET_ACCESS_KEY')
s3 = boto3.client('s3', region_name=region,
                    aws_access_key_id = access_key, 
                    aws_secret_access_key =secret_key)

def upload_fulltext(storage,files_location_path):

    for file_location_path in files_location_path:

        if not os.path.exists(file_location_path):
            print(f"FILE {file_location_path} DOES NOT EXIST")
            continue
        # load the json file
        with open(file_location_path) as json_file:
            data = json.load(json_file.read())
        if storage == 'aws':
             # if bucket dont exist, create it
            if s3.Bucket(bucket_name) not in s3.buckets.all():
                s3.create_bucket(Bucket=bucket_name)
        #    iterating throught the json
            for i in range(len(data)):
                ecli = data[i]['ecli']
                new_json_path = f"{ecli}.json"
                # dump each ecli json file to s3
                s3.Object(bucket_name, new_json_path).put(Body=json.dumps(data[i]))
            os.remove(file_location_path)
        if storage == 'local':
            # iterating throught the json
            for i in range(len(data)):
                ecli = data[i]['ecli']
                new_json_path = f"{ecli}.json"
                # dump each ecli json file to s3
                with open(new_json_path, 'w') as outfile:
                    json.dump(data[i], outfile)    
        #delete the json file
        # os.remove(file_location_path) 
        print(f"{len(data)} files uploaded")





if __name__ == '__main__':
    upload_fulltext(sys.argv[1:])


