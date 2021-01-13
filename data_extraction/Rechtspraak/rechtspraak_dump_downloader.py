import urllib.request
import time
from datetime import datetime
from definitions import DIR_DATA, DIR_RECHTSPRAAK
import os

start = time.time()

dateTimeObj = datetime.now()
date = str(dateTimeObj.year) + '-' + str(dateTimeObj.month) + '-' + str(dateTimeObj.day)

print("Downloading Rechtspraak.nl dump - " + date + " ...")

urllib.request.urlretrieve("http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip",
                           DIR_RECHTSPRAAK + '.zip')

end = time.time()

print("Done!")
print("Time taken: ", (end - start), "s")
