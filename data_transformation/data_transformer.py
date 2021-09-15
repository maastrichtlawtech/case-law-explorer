from os.path import dirname, abspath, basename
import sys
sys.path.append(dirname(dirname(abspath(__file__))))

from definitions.mappings.field_names_maps import *
from data_transformation.utils import *
from definitions.storage_handler import Storage, CSV_RS_CASES, CSV_RS_OPINIONS, CSV_LI_CASES, \
    get_path_raw, get_path_processed
import time
import argparse


def process_row(row, tool_map, fieldname_map):
    row_clean = dict.fromkeys(fieldname_map.values())
    for col, value in row.items():
        if value:
            if col in tool_map:
                row_clean[fieldname_map[col]] = tool_map[col](value.strip())
            else:
                row_clean[fieldname_map[col]] = value.strip()

    return row_clean


def process_csv(in_path, out_path, tool_map, fieldname_map):
    with open(out_path, 'w', newline='') as out_file:
        writer = DictWriter(out_file, fieldnames=list(fieldname_map.values()))
        writer.writeheader()

        with open(in_path, 'r', newline='') as in_file:
            reader = DictReader(in_file)
            writer.writerows(process_row(row, tool_map, fieldname_map) for row in reader)

start = time.time()

input_path = get_path_raw(CSV_RS_CASES)
output_path = get_path_processed(CSV_RS_CASES)

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
args = parser.parse_args()
print('\n--- PREPARATION ---\n')
print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('INPUT:\t\t\t\t', basename(input_path))
print('OUTPUTS:\t\t\t', f'{basename(output_path)}\n')
storage = Storage(location=args.storage)
storage.setup_pipeline(output_paths=[output_path], input_path=input_path)
last_updated = storage.pipeline_last_updated
print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

print('\n--- START ---\n')


"""
Define tool_maps
"""
tool_map_rs = {
    'language': format_jurisdiction,
    'creator': format_instance,
    'procedure': format_rs_list,
    'subject': format_domains,
    'relation': format_rs_list,
    'references': format_rs_list,
    'hasVersion': format_rs_alt_sources,
    'inhoudsindicatie': format_rs_xml,
    'info': format_rs_xml,
    'full_text': format_rs_xml
}

tool_map_li = {
    'Jurisdiction': format_jurisdiction,
    'LawArea': format_li_domains,
    'IssuingInstitution': format_instance,
    'PublicationDate': format_li_date,
    'EnactmentDate': format_li_date,
    'DateAdded': format_li_date,
    'Sources': format_li_list,
    'SearchNumbers': format_li_list
}


"""
Transform csvs
"""

print('Processing RS cases ...')
process_csv(input_path, output_path, tool_map_rs, MAP_RS)
print('Completed processing RS cases.')

#print('Processing RS opinions...')
#process_csv(CSV_RS_OPINIONS, CSV_RS_OPINIONS_PROC, tool_map_rs, MAP_RS_OPINION)
#print('Completed processing RS opinions.')

#print('Processing LI cases...')
#process_csv(CSV_LI_CASES, CSV_LI_CASES_PROC, tool_map_li, MAP_LI)
#print('Completed processing LI cases.')

print(f"\nUpdating {args.storage} storage ...")
storage.finish_pipeline()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
