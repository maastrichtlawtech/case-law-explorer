from os.path import dirname, abspath, splitext
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import zipfile
from definitions.storage_handler import Storage, DIR_RECHTSPRAAK, join
from os import makedirs
import io
import time
import argparse
import datetime
from dotenv import load_dotenv
load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
parser.add_argument('-d', '--date', type=datetime.date.fromisoformat, help='start decision date to fetch data from')
parser.add_argument('-u', '--update', action='store_true', help='update data from most recent decision date on storage')
args = parser.parse_args()
storage = Storage(args.storage)
print('Input/Output data storage:', args.storage)

input_path = DIR_RECHTSPRAAK + '.zip'
output_path = DIR_RECHTSPRAAK

if args.update:
    from_date = storage.last_updated(output_path)
elif args.date:
    from_date = args.date
else:
    from_date = datetime.date(1900, 1, 1)

print('Data will be processed from:', from_date.isoformat())

start_script = time.time()



print(f"Fetching data from {args.storage} storage...")
storage.fetch(input_path)
# extract all files in directory "filename" and all subdirectories:
print('Extracting directories...')
outer_zip = zipfile.ZipFile(input_path)
# for each year directory in dataset create folder structure
for year_dir in outer_zip.namelist():
    if year_dir.endswith('.zip'):
        year = splitext(year_dir)[0]
        if int(year) < from_date.year:
            continue
        # create new directory
        makedirs(join(output_path, year), exist_ok=True)
        # read inner zip file into bytes buffer
        content = io.BytesIO(outer_zip.read(year_dir))
        inner_zip = zipfile.ZipFile(content)
        # for each month directory in year folder extract content
        for month_dir in inner_zip.namelist():
            if month_dir.endswith('.xml'):
                month = dirname(month_dir)[-2:]
                if int(year) == from_date.year and int(month) < from_date.month:
                    continue
                inner_zip.extract(month_dir, join(output_path, year))

print(f"Updating {args.storage} storage ...")
storage.update(output_path)

print('Done.')

end_script = time.time()
print("Time taken: ", (end_script - start_script), "s")
