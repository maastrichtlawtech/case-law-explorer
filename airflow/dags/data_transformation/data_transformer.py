"""
Main data transformer. Transforms files from the data/raw file onto data/processed. Cleans up the data, renames columns,
removes some unnecessary data.
"""

import logging
import sys
import time
from csv import DictReader, DictWriter
from os import makedirs
from os.path import abspath, basename, dirname, exists, join

from data_transformation.utils import (
    format_cellar_celex,
    format_cellar_year,
    format_domains,
    format_echr_date,
    format_instance,
    format_jurisdiction,
    format_rs_alt_sources,
    format_rs_list,
    format_rs_newline_list,
    format_rs_xml,
)
from definitions.mappings.attribute_name_maps import MAP_CELLAR, MAP_ECHR, MAP_RS
from definitions.storage_handler import (
    CSV_CELLAR_CASES,
    CSV_ECHR_CASES,
    CSV_RS_CASES,
    Storage,
    get_path_processed,
    get_path_raw,
)

sys.path.append(dirname(dirname(abspath(__file__))))

"""
Per-source column-rename maps (field) and value-cleaning functions (tool),
keyed by caselaw type.
"""
tool_map_rs = {
    "language": format_jurisdiction,
    "creator": format_instance,
    "procedure": format_rs_list,
    "subject": format_domains,
    "relation": format_rs_list,
    "references": format_rs_list,
    "hasVersion": format_rs_alt_sources,
    "inhoudsindicatie": format_rs_xml,
    "info": format_rs_xml,
    "full_text": format_rs_xml,
    # citations_outgoing/legislations_cited: newline-joined by both
    # rechtspraak_extractor's live-API fallback and lido.db (built by
    # lido_sqlite_build), not comma-joined like the fields format_rs_list
    # handles above.
    "citations_outgoing": format_rs_newline_list,
    "legislations_cited": format_rs_newline_list,
}

# Keyed on the extractor's column names, like the maps above, so these follow
# cellar-extractor 2.x out of the raw CDM predicate labels it used to emit.
tool_map_cellar = {
    "year_of_resource": format_cellar_year,
    "celex": format_cellar_celex,
}
tool_map_echr = {"judgementdate": format_echr_date}

SOURCE_MAPS = {
    "RS": (MAP_RS, tool_map_rs),
    "CELLAR": (MAP_CELLAR, tool_map_cellar),
    "ECHR": (MAP_ECHR, tool_map_echr),
}


def _infer_caselaw_type(file_name):
    """Map an input file name to its caselaw type via the known source file names."""
    if file_name == CSV_CELLAR_CASES:
        return "CELLAR"
    if file_name == CSV_ECHR_CASES:
        return "ECHR"
    return "RS"


def transform_data(caselaw_type=None, input_paths=None, output_dir=None):
    """
    Transform raw per-source CSVs into the unified processed format.

    caselaw_type: 'RS' | 'CELLAR' | 'ECHR'; inferred from each file name
        when omitted.
    output_dir: directory for the *_clean.csv outputs. Defaults to the
        global processed dir; monthly ETL tasks pass a month-scoped dir so
        parallel tasks never share output files.
    Returns the list of written output paths.
    """
    start = time.time()
    if input_paths is None:
        input_paths = [
            get_path_raw(CSV_RS_CASES),
            get_path_raw(CSV_CELLAR_CASES),
            get_path_raw(CSV_ECHR_CASES),
        ]

    logging.info("INPUT/OUTPUT DATA STORAGE:\t" + "local")
    logging.info("INPUTS:\t\t\t\t" + ",".join([basename(input_path) for input_path in input_paths]))
    logging.info(
        "OUTPUTS:\t\t\t"
        + ",".join(
            [basename(get_path_processed(basename(input_path))) for input_path in input_paths]
        )
    )
    # run data transformation for each input file
    Storage()  # ensure the data directory tree exists
    output_paths = []
    for input_path in input_paths:
        if not exists(input_path):
            logging.warning(f"No such file found as {input_path}")
            continue
        file_name = basename(input_path)
        if output_dir is not None:
            makedirs(output_dir, exist_ok=True)
            output_path = join(output_dir, file_name.split(".csv")[0] + "_clean.csv")
        else:
            output_path = get_path_processed(file_name)
        logging.info(f"--- START {file_name} ---")
        field_map, tool_map = SOURCE_MAPS[caselaw_type or _infer_caselaw_type(file_name)]
        # overwrite any previous output for this file: keeping a stale
        # processed CSV around means the loader re-ingests old data
        with open(output_path, "w", newline="", encoding="utf-8") as out_file:
            writer = DictWriter(out_file, fieldnames=list(field_map.values()))
            writer.writeheader()

            with open(input_path, "r", newline="", encoding="utf-8") as in_file:
                reader = DictReader(in_file)
                # process input file by row
                for row in reader:
                    row_clean = dict.fromkeys(field_map.values())
                    for col, value in row.items():
                        if value:
                            if (
                                col in field_map
                            ):  # check if column is in field map, as we dont need all the columns
                                if col in tool_map:
                                    row_clean[field_map[col]] = tool_map[col](value.strip())
                                else:
                                    row_clean[field_map[col]] = value.strip()
                    # write processed row to output file only if ECLI is not empty
                    if (
                        row_clean["ECLI"] is not None
                        and row_clean["ECLI"] == row_clean["ECLI"]
                        and row_clean["ECLI"] != ""
                    ):
                        row_clean = {k: v for k, v in row_clean.items() if v is not None}
                        writer.writerow(row_clean)
        output_paths.append(output_path)
    end = time.time()
    logging.info("--- DONE ---")
    logging.info(f"Time taken: {time.strftime('%H:%M:%S', time.gmtime(end - start))}")
    return output_paths


if __name__ == "__main__":
    transform_data()
