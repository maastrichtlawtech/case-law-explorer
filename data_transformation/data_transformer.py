from os.path import dirname, abspath, basename
import sys
sys.path.append(dirname(dirname(abspath(__file__))))

from definitions.mappings.attribute_name_maps import *
from data_transformation.utils import *
from definitions.storage_handler import Storage, CSV_RS_CASES, CSV_RS_OPINIONS, CSV_LI_CASES, \
    get_path_raw, get_path_processed
import time
import argparse


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

tool_maps = {
    get_path_raw(CSV_RS_CASES): tool_map_rs,
    get_path_raw(CSV_RS_OPINIONS): tool_map_rs,
    get_path_raw(CSV_LI_CASES): tool_map_li
}

field_maps = {
    get_path_raw(CSV_RS_CASES): MAP_RS,
    get_path_raw(CSV_RS_OPINIONS): MAP_RS_OPINION,
    get_path_raw(CSV_LI_CASES): MAP_LI
}


"""
Start processing
"""
start = time.time()

input_paths = [get_path_raw(CSV_RS_CASES), get_path_raw(CSV_RS_OPINIONS), get_path_raw(CSV_LI_CASES)]
output_paths = [get_path_processed(CSV_RS_CASES), get_path_processed(CSV_RS_OPINIONS), get_path_processed(CSV_LI_CASES)]

parser = argparse.ArgumentParser()
parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and save output data to')
args = parser.parse_args()

print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
print('INPUTS:\t\t\t\t', basename(input_paths[0]), basename(input_paths[1]), basename(input_paths[2]))
print('OUTPUTS:\t\t\t', f'{basename(output_paths[0])}, {basename(output_paths[1])}, {basename(output_paths[2])}\n')

# run data transformation for each input file
for i, input_path in enumerate(input_paths):
    output_path = output_paths[i]
    print(f'\n--- PREPARATION {basename(input_path)} ---\n')
    storage = Storage(location=args.storage)
    storage.setup_pipeline(output_paths=[output_path], input_path=input_path)
    last_updated = storage.pipeline_last_updated
    print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

    print(f'\n--- START {basename(input_path)} ---\n')

    field_map = field_maps.get(input_path)
    tool_map = tool_maps.get(input_path)

    with open(output_path, 'a', newline='') as out_file:
        writer = DictWriter(out_file, fieldnames=list(field_map.values()))
        writer.writeheader()

        with open(input_path, 'r', newline='') as in_file:
            reader = DictReader(in_file)
            # process input file by row
            for row in reader:
                row_clean = dict.fromkeys(field_map.values())
                for col, value in row.items():
                    if value:
                        if col in tool_map:
                            row_clean[field_map[col]] = tool_map[col](value.strip())
                        else:
                            row_clean[field_map[col]] = value.strip()
                # write processed row to output file
                writer.writerow(row_clean)

    print(f"\nUpdating {args.storage} storage ...")
    storage.finish_pipeline()

end = time.time()
print("\n--- DONE ---")
print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
