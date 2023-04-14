import boto3
import json
import os,sys
from os import getenv
from os.path import basename,dirname, join, abspath
sys.path.append(dirname(dirname(abspath(__file__))))
from definitions.storage_handler import DIR_DATA_FULL_TEXT, JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR
# from dotenv import load_dotenv
# load_dotenv() 

bucket_name = 'full-text-data'  # .env file instead?

# Incase of running the instance locally
# region = getenv('AWS_REGION')
# location = {'LocationConstraint': region}
# access_key = getenv('AWS_ACCESS_KEY_ID')
# secret_key = getenv('AWS_SECRET_ACCESS_KEY')
# s3 = boto3.resource('s3', region_name=region,
#                     aws_access_key_id = access_key, 
#                     aws_secret_access_key =secret_key)

# incase of runnning the instance in AWS
s3 = boto3.resource('s3')

def upload_fulltext(storage: str ,files_location_paths: list):
    for file_location_path in files_location_paths:

        if not os.path.exists(file_location_path):
            print(f"FILE {file_location_path} DOES NOT EXIST")
            continue
        # load the json file
        with open(file_location_path, encoding='utf-8') as json_file:
            data = json.load(json_file)
        if storage == 'aws':
             # if bucket dont exist, create it
            if s3.Bucket(bucket_name) not in s3.buckets.all():
                print(f"Bucket {bucket_name} does not exist. Creating bucket...")
                # s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration=location)
                s3.create_bucket(Bucket=bucket_name)
            else:
                print(f"Bucket {bucket_name} already exists. Updating bucket...")
            
            print(f'Processing {basename(file_location_path)} ...')
        #    iterating throught the json
            for i in range(len(data)):
                if file_location_path == JSON_FULL_TEXT_ECHR:
                    item_id = data[i]['item_id']
                    # dump each ecli json file to s3 with ecli as name
                    s3.Object(bucket_name, f"{item_id}.json").put(Body=json.dumps(data[i]))
                if file_location_path == JSON_FULL_TEXT_CELLAR:
                    celex = data[i]['celex']
                    # dump each celex json file to s3 with celex as name
                    s3.Object(bucket_name, f"{celex}.json").put(Body=json.dumps(data[i]))
            os.remove(file_location_path)
        if storage == 'local':
            # iterating throught the json
            for i in range(len(data)):
                if file_location_path == JSON_FULL_TEXT_ECHR:
                    item_id = data[i]['item_id']
                    new_json_path = join(DIR_DATA_FULL_TEXT,f"{item_id}.json")                
                    # dump each ecli json file to local
                    with open(os.path.join(new_json_path),'w') as json_file:
                        json.dump(data[i],json_file)
                if file_location_path == JSON_FULL_TEXT_CELLAR:
                    celex = data[i]['celex']
                    new_json_path = join(DIR_DATA_FULL_TEXT,f"{celex}.json")
                    # dump each celex json file to local
                    with open(os.path.join(new_json_path),'w') as json_file:
                        json.dump(data[i],json_file)
        print(f"{len(data)} files uploaded to {bucket_name} in {storage} storage")





if __name__ == '__main__':
    upload_fulltext(sys.argv[1:])


