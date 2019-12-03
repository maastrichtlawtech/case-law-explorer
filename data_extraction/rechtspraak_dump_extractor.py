import zipfile
import sys
import os
from os import walk
import time
import concurrent.futures

start = time.time()

def unzip_archive(filename):
	if (len(filename) < 20) or (filename[-4:].lower() != ".zip") or ("opendatauitspraken.zip" in filename.lower()):
		return -1

	filen = filename[-10:]
	year_dir = filen[:4] + "/"
	with zipfile.ZipFile(filename, 'r') as zip_ref:
		zip_ref.extractall("cases/"+year_dir+"/")
	return 0

print()
print("Extracting yearly directories from OpenDataUitspraken.zip...")
print()

with zipfile.ZipFile("cases/OpenDataUitspraken.zip", 'r') as zip_ref:
		zip_ref.extractall("cases/")

print("Done!")
print()

if __name__ == '__main__': 
	zipfiles = []
	for (dirpath, dirnames, filenames) in walk("cases/"):
	    zipfiles.extend(filenames)

	fullfilepaths = []
	for item in zipfiles:
		year = item[:4].lower()
		fullfilepaths.append("cases/"+year+"/"+item)

	num_files = len(zipfiles)
	index = 1

	print("Extracting cases XMLs from monthly zip archives ...")
	print()

	with concurrent.futures.ProcessPoolExecutor() as executor:
		for file, zippedresult in zip(fullfilepaths, executor.map(unzip_archive, fullfilepaths)):
			print("unzipping (",index,"/",num_files,") ...")
			index+=1

end = time.time()

print("Done!")
print()

print("Time taken: ", (end - start), "s")