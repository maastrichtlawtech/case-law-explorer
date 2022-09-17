from os.path import dirname, abspath, basename
from os import getenv
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import urllib.request
import time
from datetime import datetime
from airflow_folder.dags.definitions.storage_handler import Storage, DIR_RECHTSPRAAK
import argparse

start = time.time()

output_path = DIR_RECHTSPRAAK + '.zip'

# set up storage location
parser = argparse.ArgumentParser()
parser.add_argument(
    'storage',
    choices=['local', 'aws'],
    help='location to save output data to'
)
args = parser.parse_args()
print('\n--- PREPARATION ---\n')
print('OUTPUT DATA STORAGE:\t', args.storage)
print('OUTPUT:\t\t\t', basename(output_path))
storage = Storage(location=args.storage)
storage.setup_pipeline(output_paths=[output_path])
last_updated = storage.pipeline_last_updated
print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

print('\n--- START ---\n')

if getenv('SAMPLE_TEST') == 'TRUE':
    rs_url = getenv('URL_RS_ARCHIVE_SAMPLE')
else:
    rs_url = getenv('URL_RS_ARCHIVE')

dateTimeObj = datetime.now()
date = str(dateTimeObj.year) + '-' + str(dateTimeObj.month) + '-' + str(dateTimeObj.day)

print("Downloading Rechtspraak.nl dump - " + date + " - " + rs_url + " ...")
# for testing:
#urllib.request.urlretrieve('https://surfdrive.surf.nl/files/index.php/s/zvrWcsriC5PU9xx/download', output_path)
urllib.request.urlretrieve(rs_url, output_path)

print(f"\nUpdating {args.storage} storage ...")
storage.finish_pipeline()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
