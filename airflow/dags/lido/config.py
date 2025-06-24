from os.path import join, dirname, abspath
from os import getenv

MAX_PARSE_ERR_COUNT=200

DB_URL_POSTGRES = getenv('DB_URL_POSTGRES')

DIR_ROOT = dirname(dirname(dirname(abspath(__file__))))
DIR_DATA = join(DIR_ROOT, 'data')
DIR_LOGS = join(DIR_ROOT, 'logs')
DIR_DATA_LIDO = join(DIR_DATA, 'lido')

FILE_LIDO_TTL_GZ = join(DIR_DATA_LIDO, 'lido-export.ttl.gz')

FILE_LAWS_NT = join(DIR_DATA_LIDO, 'lido-laws.nt')
FILE_CASES_NT = join(DIR_DATA_LIDO, 'lido-cases.nt')

FILE_SQLITE_DB = join(DIR_DATA_LIDO, 'stage.db')

FILE_LAWS_CSV = join(DIR_DATA_LIDO, 'export-laws.csv')
FILE_CASES_CSV = join(DIR_DATA_LIDO, 'export-cases.csv')
FILE_CASELAW_CSV = join(DIR_DATA_LIDO, 'export-caselaw.csv')
FILE_LAWALIAS_CSV = join(DIR_DATA_LIDO, 'export-lawalias.csv')
