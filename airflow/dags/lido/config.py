from os.path import join, dirname, abspath
from os import getenv, makedirs

MAX_PARSE_ERR_COUNT=200

CONN_PG_LIDO = "pg_lido"

DIR_ROOT = dirname(dirname(dirname(abspath(__file__))))
DIR_DATA = join(DIR_ROOT, 'data')
DIR_LOGS = join(DIR_ROOT, 'logs')
DIR_DATA_LIDO = join(DIR_DATA, 'lido')
DIR_DATA_BWB = join(DIR_DATA_LIDO, 'bwb')

FILE_LIDO_TTL_GZ = join(DIR_DATA_LIDO, 'lido-export.ttl.gz')
URL_LIDO_TTL_GZ = 'https://linkeddata.overheid.nl/export/lido-export.ttl.gz'

FILE_LAWS_NT = join(DIR_DATA_LIDO, 'lido-laws.nt')
FILE_CASES_NT = join(DIR_DATA_LIDO, 'lido-cases.nt')

FILE_SQLITE_DB = join(DIR_DATA_LIDO, 'stage.db')

FILE_LAWS_CSV = join(DIR_DATA_LIDO, 'export-laws.csv')
FILE_CASES_CSV = join(DIR_DATA_LIDO, 'export-cases.csv')
FILE_CASELAW_CSV = join(DIR_DATA_LIDO, 'export-caselaw.csv')
FILE_LAWALIAS_CSV = join(DIR_DATA_LIDO, 'export-lawalias.csv')

TBL_LAWS = 'law_element'
TBL_CASES = 'legal_case'
TBL_CASE_LAW = 'case_law'
TBL_LAW_ALIAS = 'law_alias'

FILE_BWB_STYLESHEET = join(DIR_DATA_BWB, 'bwb-regeling-aanduiding.xslt')
FILE_BWB_IDS_ZIP = join(DIR_DATA_BWB, 'BWBIdList.xml.zip')
FILE_BWB_IDS_XML = join(DIR_DATA_BWB, 'BWBIdList.xml')
FILE_BWB_IDS_JSON = join(DIR_DATA_BWB, 'BWBIdList.json')
FILE_BWB_IDS_TRANSFORMED = join(DIR_DATA_BWB, 'BWBIdList.server.xml')
URL_BWB_IDS_ZIP = 'https://zoekservice.overheid.nl/BWBIdService/BWBIdList.xml.zip'

makedirs(DIR_DATA_LIDO, exist_ok=True)
makedirs(DIR_DATA_BWB, exist_ok=True)
