import zipfile
from definitions.file_paths import DIR_RECHTSPRAAK, join
import os
import io
import time

start_script = time.time()
# extract all files in directory "filename" and all subdirectories:
print('Extracting directories...')
new_path = DIR_RECHTSPRAAK
os.makedirs(new_path)
z = zipfile.ZipFile(DIR_RECHTSPRAAK + '.zip')
for f in z.namelist():
    if f.endswith('.zip'):
        # get directory name from file
        dirname = os.path.dirname(f)
        if not os.path.exists(join(new_path, dirname)):
            os.mkdir(join(new_path, dirname))
        new_dir = os.path.splitext(f)[0]
        # create new directory
        os.mkdir(join(new_path, new_dir))
        # read inner zip file into bytes buffer
        content = io.BytesIO(z.read(f))
        zip_file = zipfile.ZipFile(content)
        for i in zip_file.namelist():
            zip_file.extract(i, join(new_path, new_dir))
print('All files extracted.')
end_script = time.time()
print("Time taken: ", (end_script - start_script), "s")
