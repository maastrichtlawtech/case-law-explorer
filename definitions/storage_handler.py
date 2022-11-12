from os.path import basename, dirname, abspath, join, exists, relpath, isfile
from os import makedirs, getenv, listdir, remove
import re
import boto3
from botocore.exceptions import ClientError
import logging
from dotenv import load_dotenv
load_dotenv()
import sys
from datetime import date, datetime

"""
Purpose of script:
a)  Define directory paths.
b)  Define the terminology to be used throughout all data processing steps.
    The original terms used in the raw data of "Rechtspraak" and "Legal intelligence" are mapped to each other
    and replaced by a global label.
    Variable names correspond to the original terms and are denoted with the prefix of their source (RS = Rechtspraak, 
    LI = Legal Intelligence). Variables without prefix don't exist in the raw data and are generated by script.
"""

# local data folder structure
DIR_ROOT = dirname(dirname(abspath(__file__)))
DIR_DATA = join(DIR_ROOT, 'data')
DIR_DATA_RAW = join(DIR_DATA, 'raw')
DIR_DATA_PROCESSED = join(DIR_DATA, 'processed')

# data file names
DIR_RECHTSPRAAK = join(DIR_DATA, 'Rechtspraak', 'OpenDataUitspraken')
DIR_ECHR = join(DIR_DATA, 'echr')
CELLAR_DIR = join(DIR_DATA, 'cellar')
CSV_OPENDATA_INDEX = DIR_RECHTSPRAAK + '_index.csv'         # eclis and decision dates of OpenDataUitspraken files
CSV_RS_CASES = 'RS_cases.csv'                               # metadata of RS cases
CSV_RS_OPINIONS = 'RS_opinions.csv'                         # metadata of RS opinions
CSV_RS_INDEX = 'RS_index.csv'                               # eclis, decision dates and relations of RS cases and opinions
CSV_LI_CASES = 'LI_cases.csv'                               # metadata of LI cases
CSV_CASE_CITATIONS = 'caselaw_citations.csv'                # citations of RS cases and opinions
CSV_LEGISLATION_CITATIONS = 'legislation_citations.csv'     # cited legislation of RS cases and opinions
CSV_LIDO_ECLIS_FAILED = 'LIDO_eclis_failed.csv'
CSV_DDB_ECLIS_FAILED = 'DDB_eclis_failed.csv'
CSV_OS_ECLIS_FAILED = 'OS_eclis_failed.csv'
CSV_ECHR_CASES = join(DIR_ECHR, 'ECHR_metadata.csv')
CSV_ECHR_CASES_NODES = join(DIR_ECHR, 'ECHR_nodes.csv')
CSV_ECHR_CASES_EDGES = join(DIR_ECHR, 'ECHR_edges.csv')
CSV_ECHR_CASES_EDGES_JSON = join(DIR_ECHR, 'ECHR_edges_json.json')
CSV_ECHR_CASES_NODES_JSON = join(DIR_ECHR, 'ECHR_nodes_json.json')



# raw data:
def get_path_raw(file_name):
    return join(DIR_DATA_RAW, file_name)


# processed data
def get_path_processed(file_name):
    last_slash_index = file_name.rfind('\\')+1 # This is necissary when a path is passed as a file name.
    if last_slash_index != 0:
        file_name = file_name[last_slash_index:]
    return join(DIR_DATA_PROCESSED, file_name.split('.csv')[0] + '_clean.csv')


class Storage:
    def __init__(self, location):
        if location not in ('local', 'aws'):
            print('Storage location must be either "local" or "aws". Setting to "local".')
            location = 'local'
        self.location = location
        self.s3_bucket_name = getenv('S3_BUCKET_NAME')
        self.s3_bucket = None
        self.s3_client = None
        self.pipeline_input_path = None
        self.pipeline_output_paths = None
        self.pipeline_last_updated = date(1900, 1, 1)

        print(f'\nSetting up {self.location} storage ...')
        self._setup()

    def _setup(self):
        # create local data folder structure, if it doesn't exist yet
        for d in [dirname(DIR_RECHTSPRAAK), DIR_DATA_RAW, DIR_DATA_PROCESSED, CELLAR_DIR, DIR_ECHR]:
            makedirs(d, exist_ok=True)

        if self.location == 'aws':
            # create an S3 bucket in the region of the configured AWS IAM user account
            try:
                region = getenv('AWS_REGION')
                s3_client = boto3.client('s3', region_name=region)
                aws_location = {'LocationConstraint': region}
                s3_client.create_bucket(Bucket=self.s3_bucket_name, CreateBucketConfiguration=aws_location)
            except ClientError as e:
                if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou' or \
                        e.response['Error']['Code'] == 'BucketAlreadyExists':
                    logging.warning(f'S3 bucket "{self.s3_bucket_name}" already exists. Content might be overwritten.')
                else:
                    raise e
            self.s3_bucket = boto3.resource('s3').Bucket(self.s3_bucket_name)
            self.s3_client = boto3.client('s3')
        print('Storage set up.')

    def setup_pipeline(self, output_paths=None, input_path=None):
        self.pipeline_input_path = input_path
        self.pipeline_output_paths = output_paths

        # fetch output data
        if self.pipeline_output_paths:
            print(f'\nFetching output data from {self.location} storage ...')
            for path in self.pipeline_output_paths:
                if exists(path):
                    logging.error(f'{path} exists locally! Move/rename local file before starting pipeline.')
                    sys.exit(2)
                if path.endswith('.csv'):
                    self.fetch_data([path])
            
            # retrieve output date of last update
            self.pipeline_last_updated = self.fetch_last_updated(self.pipeline_output_paths)
            if self.location == "aws":
                for path in self.pipeline_output_paths:
                    remove(path)

        # fetch input data
        if self.pipeline_input_path:
            print(f'\nFetching input data from {self.location} storage ...')
            self.fetch_data([self.pipeline_input_path])
            # retrieve input date of last update
            last_updated_input = self.fetch_last_updated([self.pipeline_input_path])

            # if output date of last update after input date of last update: need to update input first
            if last_updated_input < self.pipeline_last_updated:
                logging.error(f'Input data {basename(self.pipeline_input_path)} is older than output data. '
                              f'Please update input data first.')
                remove(self.pipeline_input_path)
                sys.exit(2)

    def finish_pipeline(self):
        if self.pipeline_output_paths:
            self.upload_data(self.pipeline_output_paths)
            to_remove = self.pipeline_output_paths+[self.pipeline_input_path]
        else:
            to_remove = [self.pipeline_input_path]
        to_remove = [path for path in to_remove if path is not None]
        if self.location == "aws":
            for path in to_remove:
                remove(path)

    def fetch_data(self, paths):
        def not_found(file_path):
            msg = file_path + ' does not exist! Consider switching storage location' \
                         ' or re-running earlier steps of the pipeline.'
            if file_path == self.pipeline_input_path:
                logging.error(msg)
                sys.exit(2)
            else:
                logging.warning(msg)

        def fetch_data_local(file_path):
            # exit if input does not exist
            if not exists(file_path):
                not_found(file_path)
            else:
                print('Local data ready.')

        def fetch_data_aws(file_path):
            if exists(file_path):
                logging.error(f'{file_path} exists locally! Move/rename local file before fetching data from aws.')
                sys.exit(2)

            if file_path == DIR_RECHTSPRAAK:
                # paginate through all items listed in folder
                paginator = self.s3_client.get_paginator('list_objects_v2')
                folder_name = relpath(file_path, DIR_ROOT) + '/'
                pages = paginator.paginate(Bucket=self.s3_bucket_name, Prefix=folder_name)
                empty = True
                for page in pages:
                    empty = False
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            yearmonth = dirname(relpath(obj['Key'], folder_name)).split('/')[1]
                            if date(int(yearmonth[:4]), int(yearmonth[4:]), 1) > self.pipeline_last_updated:
                                key = obj['Key']
                                makedirs(dirname(join(DIR_ROOT, key)), exist_ok=True)
                                self.s3_bucket.download_file(key, join(DIR_ROOT, key))
                if empty:
                    not_found(file_path)

            else:
                try:
                    makedirs(dirname(file_path), exist_ok=True)
                    self.s3_bucket.download_file(relpath(file_path, DIR_ROOT), file_path)
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        not_found(file_path)

            print(f'{basename(file_path)} fetched.')

        if self.location == 'local':
            for path in paths:
                fetch_data_local(path)
        elif self.location == 'aws':
            for path in paths:
                fetch_data_aws(path)

    def upload_data(self, paths):
        def upload_to_aws(file_path):
            if isfile(file_path):
                try:
                    self.s3_bucket.upload_file(file_path, relpath(file_path, DIR_ROOT))
                except ClientError as e:
                    logging.error(e)
            else:
                for sub_path in listdir(file_path):
                    upload_to_aws(join(file_path, sub_path))

        if self.location == 'aws':
            for path in paths:
                upload_to_aws(path)
                print(basename(path), 'loaded to aws.')
        else:
            print('Local data updated.')

    def fetch_last_updated(self, paths):
        def date_map(file_path):
            default = ('date_decision', lambda x: date.fromisoformat(x))
            d_map = {
                get_path_raw(CSV_LI_CASES): ('EnactmentDate', lambda x: datetime.strptime(x, "%Y%m%d").date()),
                get_path_raw(CSV_ECHR_CASES): ('judgementdate', lambda x: datetime.strptime(x, "%d/%m/%Y %H:%M:%S").date()),
            }
            return d_map.get(file_path, default)

        def default_date(file_path):
            print(f'Setting start date of {basename(file_path)} to 1900-01-01.')
            return date(1900, 1, 1)

        def last_updated(file_path):
            if file_path == DIR_RECHTSPRAAK:
                self.fetch_data([CSV_OPENDATA_INDEX])
                file_path = CSV_OPENDATA_INDEX
            if re.match(rf'^{CELLAR_DIR}/.*'.replace('\\', '/')+'\.json$', file_path.replace('\\', '/')):
                if self.location == 'local':
                    # Go through existing JSON files and use their filename to determine when the last 
                    # update was.
                    # Alternatively, this could be switched to loading all the JSONs and checking the
                    # max last modification date.
                    new_date = datetime(1900, 1, 1)
                    for filename in listdir(CELLAR_DIR):
                        match = re.match(
                            r'^(\d{4})-(\d{2})-(\d{2})T(\d{2})_(\d{2})\_(\d{2})\.json$', filename)
                        if not match:
                            continue

                        new_date = max(
                            new_date,
                            datetime(
                                int(match[1]), int(match[2]), int(match[3]),
                                int(match[4]), int(match[5]), int(match[6])
                            )
                        )
                    return new_date

            if file_path.endswith('.csv'):
                import pandas as pd
                try:
                    date_name, date_function = date_map(file_path)
                    df = pd.read_csv(file_path, usecols=[date_name], dtype=str)
                    return max(df[date_name].apply(date_function))
                except FileNotFoundError:
                    logging.warning(file_path + ' not found.')
                    return default_date(file_path)

            logging.warning(basename(file_path) + ' is not a .csv file.')
            return default_date(file_path)

        last_updated_dates = []
        for path in paths:
            this_last_updated = last_updated(path)
            print(f'- Last updated {basename(path)}:\t {this_last_updated}')
            last_updated_dates.append(this_last_updated)

        return min(last_updated_dates)
