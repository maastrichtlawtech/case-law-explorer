import urllib.request
import time
from datetime import datetime

start = time.time()

dateTimeObj = datetime.now()
date = str(dateTimeObj.year) + '-' + str(dateTimeObj.month) + '-' + str(dateTimeObj.day)

print()
print("Downloading Rechtspraak.nl dump - " + date + " ...")
print()

urllib.request.urlretrieve("http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip", "../data/OpenDataUitspraken.zip")

end = time.time()

print()
print("Done!")
print()
print("Time taken: ", (end - start), "s")