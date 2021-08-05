from os.path import dirname, abspath
from os import getenv
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import urllib.request
import time
from datetime import datetime
from definitions.storage_handler import Storage, URL_RS_ARCHIVE, URL_RS_ARCHIVE_SAMPLE, DIR_RECHTSPRAAK

import argparse

start = time.time()

# set up storage location
parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
args = parser.parse_args()
storage = Storage(args.storage)
print('Output data storage:', args.storage)

output_path = DIR_RECHTSPRAAK + '.zip'

if getenv('SAMPLE_TEST') == 'TRUE':
    rs_url = URL_RS_ARCHIVE_SAMPLE
else:
    rs_url = URL_RS_ARCHIVE

dateTimeObj = datetime.now()
date = str(dateTimeObj.year) + '-' + str(dateTimeObj.month) + '-' + str(dateTimeObj.day)

print("Downloading Rechtspraak.nl dump - " + date + " - " + rs_url + " ...")
#urllib.request.urlretrieve('https://surfdrive.surf.nl/files/index.php/s/WaEWoCfKlaS0gD0/download', output_path)  # for testing
urllib.request.urlretrieve(rs_url, output_path)
print(f"Updating {args.storage} storage ...")
storage.update(output_path)

end = time.time()

print("Done.")
print("Time taken: ", (end - start), "s")
