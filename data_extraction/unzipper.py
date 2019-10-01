import os
import zipfile

from progressbar import ProgressBar, SimpleProgress, Percentage, ETA, AdaptiveETA, UnknownLength

dirs = []
files = os.listdir(".")

# List all top-level directories
for file in files:
    if os.path.isdir(file):
        if file == "2000" or file == "1913" or file == "2016" or file == "1998" or file == "1965" or file == "1943":
            # Append the directories
            dirs.append(file)

extracted_total = 0
print('Unzipping files...')

for directory in dirs:
    files_in_dir = os.listdir(directory)
    file_index = 0

    print("Looking in %s directory..." % directory)

    for file in files_in_dir:
        current_file = files_in_dir[file_index]
        if current_file[-4:].lower() == ".zip":
            with zipfile.ZipFile(directory+"/"+file, "r") as zip_ref:
                zip_ref.extractall(directory+"/")
                print("\tUnzipped %s file." % file)
        file_index += 1

    extracted_total += len(files_in_dir)-12
    print("\tExtracted %i files." % (len(files_in_dir)-12))

print("Extracted %i total files." % extracted_total)

