from os.path import dirname, abspath, splitext, basename
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import zipfile
from definitions.storage_handler import Storage, DIR_RECHTSPRAAK, join, CSV_RECHTSPRAAK_INDEX
from os import makedirs
import io
import time
import argparse
import pandas as pd
from datetime import date

input_path = DIR_RECHTSPRAAK + '.zip'
output_path_dir = DIR_RECHTSPRAAK
output_path_index = CSV_RECHTSPRAAK_INDEX

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
args = parser.parse_args()
storage = Storage(location=args.storage, output_paths=[output_path_dir, output_path_index], input_path=input_path)
print('Input/Output data storage:', args.storage)
last_updated = storage.last_updated
print('Data will be processed from:', last_updated.isoformat())

start_script = time.time()

# extract all files in directory "filename" and all subdirectories:
print('Extracting directories...')
outer_zip = zipfile.ZipFile(input_path)
# for each year directory in dataset create folder structure
for year_dir in outer_zip.namelist():
    if year_dir.endswith('.zip'):
        year = splitext(year_dir)[0]
        if int(year) < last_updated.year:
            continue
        # create new directory
        makedirs(join(output_path_dir, year), exist_ok=True)
        # read inner zip file into bytes buffer
        content = io.BytesIO(outer_zip.read(year_dir))
        inner_zip = zipfile.ZipFile(content)
        # for each month directory in year folder extract content
        for file in inner_zip.namelist():
            if file.endswith('.xml'):
                month = dirname(file)[-2:]
                if int(year) == last_updated.year and int(month) < last_updated.month:
                    continue
                inner_zip.extract(file, join(output_path_dir, year))
                ecli = basename(file).split('.xml')[0].replace('_', ':')
                date_decision = date(int(year), int(month), 1)
                with open(output_path_index, 'a') as f:
                    pd.DataFrame({'ecli': [ecli],
                                  'date_decision': [date_decision]}).to_csv(f, mode='a', header=not f.tell(), index=False)

print(f"Updating {args.storage} storage ...")
storage.update_data()

print('Done.')

end_script = time.time()
print("Time taken: ", (end_script - start_script), "s")
