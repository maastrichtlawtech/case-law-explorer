from definitions.mappings.field_names_maps import *
from definitions.file_paths import *
from data_transformation.utils import *
import time


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
    'Sources': format_li_list
}


"""
Transform csvs
"""
start = time.time()

print('Processing RS cases...')
process_csv(CSV_RS_CASES, CSV_RS_CASES_PROC, tool_map_rs, MAP_RS)
print('Completed processing RS cases.')

print('Processing RS opinions...')
process_csv(CSV_RS_OPINIONS, CSV_RS_OPINIONS_PROC, tool_map_rs, MAP_RS_OPINION)
print('Completed processing RS opinions.')

print('Processing LI cases...')
process_csv(CSV_LI_CASES, CSV_LI_CASES_PROC, tool_map_li, MAP_LI)
print('Completed processing LI cases.')

end = time.time()
print("\nTime taken: ", (end - start), "s")
