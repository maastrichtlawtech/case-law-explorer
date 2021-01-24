import urllib.request
import time
from datetime import datetime
from definitions import DIR_DATA, DIR_RECHTSPRAAK, URL_RS_ARCHIVE, URL_RS_ARCHIVE_SAMPLE
import os

start = time.time()

if os.getenv('SAMPLE_TEST') == 'TRUE':
    rs_url = URL_RS_ARCHIVE_SAMPLE
else:
    rs_url = URL_RS_ARCHIVE

dateTimeObj = datetime.now()
date = str(dateTimeObj.year) + '-' + str(dateTimeObj.month) + '-' + str(dateTimeObj.day)

print("Downloading Rechtspraak.nl dump - " + date + " - " + rs_url + " ...")

urllib.request.urlretrieve(rs_url,
                           DIR_RECHTSPRAAK + '.zip')

end = time.time()

print("Done!")
print("Time taken: ", (end - start), "s")
