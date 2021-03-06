from os.path import dirname, abspath, join, exists
from os import makedirs
"""
Purpose of script:
a)  Define directory paths.
b)  Define the terminology to be used throughout all data processing steps.
    The original terms used in the raw data of "Rechtspraak" and "Legal intelligence" are mapped to each other
    and replaced by a global label.
    Variable names correspond to the original terms and are denoted with the prefix of their source (RS = Rechtspraak, 
    LI = Legal Intelligence). Variables without prefix don't exist in the raw data and are generated by script.
"""

# URL DEFINITIONS:
URL_LI_ENDPOINT = 'https://api.legalintelligence.com'
URL_RS_ARCHIVE = 'http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip'
URL_RS_ARCHIVE_SAMPLE = 'https://surfdrive.surf.nl/files/index.php/s/WaEWoCfKlaS0gD0/download'

# data folder structure
DIR_ROOT = dirname(dirname(abspath(__file__)))
DIR_DATA = join(DIR_ROOT, 'data')
DIR_DATA_RAW = join(DIR_DATA, 'raw')
DIR_DATA_PROCESSED = join(DIR_DATA, 'processed')
DIR_RECHTSPRAAK = join(DIR_DATA, 'OpenDataUitspraken')
for d in [DIR_DATA, DIR_DATA_RAW, DIR_DATA_PROCESSED]:
    if not exists(d):
        makedirs(d)

# raw data
CSV_RS_CASES = join(DIR_DATA_RAW, 'RS_cases.csv')
CSV_RS_OPINIONS = join(DIR_DATA_RAW, 'RS_opinions.csv')
CSV_LI_CASES = join(DIR_DATA_RAW, 'LI_cases.csv')
CSV_CASE_CITATIONS = join(DIR_DATA_RAW, 'caselaw_citations.csv')
CSV_LEGISLATION_CITATIONS = join(DIR_DATA_RAW, 'legislation_citations.csv')

# processed data
CSV_RS_CASES_PROC = join(DIR_DATA_PROCESSED, 'RS_cases_clean.csv')
CSV_RS_OPINIONS_PROC = join(DIR_DATA_PROCESSED, 'RS_opinions_clean.csv')
CSV_LI_CASES_PROC = join(DIR_DATA_PROCESSED, 'LI_cases_clean.csv')
CSV_CASE_CITATIONS_PROC = join(DIR_DATA_PROCESSED, 'caselaw_citations_clean.csv')
CSV_LEGISLATION_CITATIONS_PROC = join(DIR_DATA_PROCESSED, 'legislation_citations_clean.csv')

# list of ECLIs (output of RS extractor, input to LIDO extractor)
CSV_RS_ECLIS = join(DIR_DATA, 'RS_eclis.csv')