from os.path import dirname, abspath, splitext, basename, join
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import zipfile
from definitions.storage_handler import Storage, DIR_RECHTSPRAAK, CSV_OPENDATA_INDEX, get_path_raw
from definitions.terminology.attribute_names import ECLI, RS_DATE
from os import makedirs
import io
import time
import argparse
import pandas as pd
from datetime import date

start = time.time()

input_path = DIR_RECHTSPRAAK + '.zip'
output_path_dir = DIR_RECHTSPRAAK
output_path_index = CSV_OPENDATA_INDEX

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
args = parser.parse_args()
print('\n--- PREPARATION ---\n')
print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('INPUT:\t\t\t\t', basename(input_path))
print('OUTPUTS:\t\t\t', f'{basename(output_path_dir)}, {basename(output_path_index)}\n')
storage = Storage(location=args.storage)
storage.setup_pipeline(output_paths=[output_path_dir, output_path_index], input_path=input_path)
last_updated = storage.pipeline_last_updated
print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

print('\n--- START ---\n')

# extract all files in directory "filename" and all subdirectories:
print('Extracting directories...')
outer_zip = zipfile.ZipFile(input_path)
# for each year directory in dataset create folder structure
for outer_file in outer_zip.namelist():
    if outer_file.endswith('.zip'):
        year, month = splitext(outer_file)[0][:4], splitext(outer_file)[0][-2:]
        if int(year) < last_updated.year:
            continue
        # create new directory
        makedirs(join(output_path_dir, splitext(outer_file)[0]), exist_ok=True)
        # read inner zip file into bytes buffer
        content = io.BytesIO(outer_zip.read(outer_file))
        inner_zip = zipfile.ZipFile(content)
        # for each month directory in year folder extract content
        for inner_file in inner_zip.namelist():
            if inner_file.endswith('.xml'):
                if int(year) == last_updated.year and int(month) < last_updated.month:
                    continue
                inner_zip.extract(inner_file, join(output_path_dir, year, year + month))
                ecli = basename(inner_file).split('.xml')[0].replace('_', ':')
                date_decision = date(int(year), int(month), 1)
                with open(output_path_index, 'a') as f:
                    pd.DataFrame({ECLI: [ecli],
                                  RS_DATE: [date_decision]}).to_csv(f, mode='a', header=not f.tell(), index=False)

print(f"\nUpdating {args.storage} storage ...")
storage.finish_pipeline()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
