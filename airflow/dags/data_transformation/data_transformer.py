"""
Main data transformer. Transforms files from the data/raw file onto data/processed. Cleans up the data, renames columns,
removes some unnecessary data.
"""
import logging
import time
from csv import DictReader, DictWriter
from os import remove
from os.path import dirname, abspath, basename, exists

from data_transformation.utils import *
from definitions.mappings.attribute_name_maps import *
from definitions.storage_handler import Storage, CSV_RS_CASES, get_path_raw, get_path_processed, CSV_CELLAR_CASES, \
    CSV_ECHR_CASES

sys.path.append(dirname(dirname(abspath(__file__))))

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

tool_map_cellar = {
    'YEAR OF THE LEGAL RESOURCE': format_cellar_year,
    'CELEX IDENTIFIER': format_cellar_celex

}
tool_map_echr = {
    'judgementdate': format_echr_date
}
tool_maps = {
    get_path_raw(CSV_RS_CASES): tool_map_rs,
    get_path_raw(CSV_CELLAR_CASES): tool_map_cellar,
    get_path_raw(CSV_ECHR_CASES): tool_map_echr
}

field_maps = {
    get_path_raw(CSV_RS_CASES): MAP_RS,
    get_path_raw(CSV_CELLAR_CASES): MAP_CELLAR,
    get_path_raw(CSV_ECHR_CASES): MAP_ECHR
}


def transform_data(caselaw_type=None, input_paths=None):
    """
    Start processing
    """
    start = time.time()
    if input_paths is None:
        input_paths = [
            get_path_raw(CSV_RS_CASES),
            get_path_raw(CSV_CELLAR_CASES),
            get_path_raw(CSV_ECHR_CASES)
        ]

    logging.info('INPUT/OUTPUT DATA STORAGE:\t' + 'local')
    logging.info('INPUTS:\t\t\t\t' + ','.join([basename(input_path) for input_path in input_paths]))
    logging.info(
        'OUTPUTS:\t\t\t' + ','.join([basename(get_path_processed(basename(input_path))) for input_path in input_paths]))
    # run data transformation for each input file
    for input_path in input_paths:
        storage = Storage()
        if not exists(input_path):
            logging.info(f"No such file found as {input_path}")
            continue
        file_name = basename(input_path)
        output_path = get_path_processed(file_name)
        logging.info(f'--- PREPARATION {file_name} ---')
        try:
            storage.setup_pipeline(output_paths=[output_path], input_path=input_path)
        except Exception as e:
            logging.info(e)
            return
        logging.info(f'--- START {file_name} ---')
        if caselaw_type == 'RS':
            field_map = MAP_RS
            tool_map = tool_map_rs
        else:
            field_map = field_maps[input_path]
            tool_map = tool_maps[input_path]
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
                            if col in field_map:  # check if column is in field map, as we dont need all the columns
                                if col in tool_map:
                                    row_clean[field_map[col]] = tool_map[col](value.strip())
                                else:
                                    row_clean[field_map[col]] = value.strip()
                    # write processed row to output file only if ECLI is not empty
                    if row_clean['ECLI'] is not None and row_clean['ECLI'] == row_clean['ECLI'] and row_clean['ECLI'] != "":
                        row_clean = {k: v for k, v in row_clean.items() if v is not None}
                        writer.writerow(row_clean)
        # remove(input_path)
    end = time.time()
    logging.info("\n--- DONE ---")
    logging.info("Time taken: ", str(time.strftime('%H:%M:%S', time.gmtime(end - start))))


if __name__ == '__main__':
    # giving arguments to the funtion
    transform_data()
