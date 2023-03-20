from os.path import dirname, abspath, basename, exists
import sys
from os import remove
sys.path.append(dirname(dirname(abspath(__file__))))

from definitions.mappings.attribute_name_maps import *
from data_transformation.utils import *
from definitions.storage_handler import Storage, CSV_RS_CASES, CSV_RS_OPINIONS, CSV_LI_CASES, \
    get_path_raw, get_path_processed, CSV_CELLAR_CASES, CSV_ECHR_CASES
import time
import argparse
from csv import DictReader, DictWriter

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
tool_map_cellar = {
    'YEAR OF THE LEGAL RESOURCE': format_cellar_year,
    'CELEX IDENTIFIER' : format_cellar_celex

}
tool_map_echr = {
    'judgementdate': format_echr_date
}
tool_maps = {
    get_path_raw(CSV_RS_CASES): tool_map_rs,
    get_path_raw(CSV_RS_OPINIONS): tool_map_rs,
    get_path_raw(CSV_LI_CASES): tool_map_li,
    get_path_raw(CSV_CELLAR_CASES): tool_map_cellar,
    get_path_raw(CSV_ECHR_CASES): tool_map_echr
}

field_maps = {
    get_path_raw(CSV_RS_CASES): MAP_RS,
    get_path_raw(CSV_RS_OPINIONS): MAP_RS_OPINION,
    get_path_raw(CSV_LI_CASES): MAP_LI,
    get_path_raw(CSV_CELLAR_CASES): MAP_CELLAR,
    get_path_raw(CSV_ECHR_CASES): MAP_ECHR
}


def transform_data(argsT):
    """
    Start processing
    """
    start = time.time()

    input_paths = [
        get_path_raw(CSV_RS_CASES),
        get_path_raw(CSV_RS_OPINIONS),
        get_path_raw(CSV_LI_CASES),
        get_path_raw(CSV_CELLAR_CASES),
        get_path_raw(CSV_ECHR_CASES)
    ]
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'],
                        help='location to take input data from and save output data to')
    args = parser.parse_args(args=argsT)

    print('INPUT/OUTPUT DATA STORAGE:\t', args.storage)
    print('INPUTS:\t\t\t\t', [basename(input_path) for input_path in input_paths])
    print('OUTPUTS:\t\t\t', [basename(get_path_processed(basename(input_path))) for input_path in input_paths], '\n')

    # run data transformation for each input file
    for input_path in input_paths:
        storage = Storage(location=args.storage)
        if not exists(input_path):
            print(f"No such file found as {input_path}")
            continue
        file_name = basename(input_path)
        output_path = get_path_processed(file_name)
        print(f'\n--- PREPARATION {file_name} ---\n')
        storage.setup_pipeline(output_paths=[output_path], input_path=input_path)
        last_updated = storage.pipeline_last_updated
        print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())
        print(f'\n--- START {file_name} ---\n')

        field_map = field_maps.get(input_path)
        tool_map = tool_maps.get(input_path)

        with open(output_path, 'a', newline='', encoding='utf-8') as out_file:
            writer = DictWriter(out_file, fieldnames=list(field_map.values()))
            writer.writeheader()

            with open(input_path, 'r', newline='', encoding='utf-8') as in_file:

                reader = DictReader(in_file)
                # process input file by row
                for row in reader:
                    row_clean = dict.fromkeys(field_map.values())
                    for col, value in row.items():                        
                        if value:
                            if col in tool_map :
                                row_clean[field_map[col]] = tool_map[col](value.strip())
                            else:
                                row_clean[field_map[col]] = value.strip()
                    # write processed row to output file only if ECLI is not empty
                    if row_clean['ECLI'] != None:
                        writer.writerow(row_clean)

        print(f"\nUpdating {args.storage} storage ...")
        remove(input_path)
    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))


if __name__ == '__main__':
    # giving arguments to the funtion
    transform_data(sys.argv[1:])
