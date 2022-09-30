from data_extraction.caselaw.cellar.cellar_extraction import cellar_extract
from data_extraction.caselaw.rechtspraak.rechtspraak_api import rechspraak_downloader
from data_transformation.data_transformer import transform_data
from definitions.storage_handler import DIR_DATA_RECHTSPRAAK
import sys
print(DIR_DATA_RECHTSPRAAK)
# sys.path.append(dirname(dirname(dirname(abspath(__file__)))))

# cellar_extract(['local','--amount','50'])
# rechspraak_downloader(['--max', '10', '--starting-date', '2022-08-28'])
transform_data(['local'])