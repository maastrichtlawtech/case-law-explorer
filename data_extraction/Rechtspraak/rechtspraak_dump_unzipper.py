import zipfile
from definitions import DIR_RECHTSPRAAK
import os
import io

# extract all files in directory "filename" and all subdirectories:
print('Extracting directories...')
new_path = DIR_RECHTSPRAAK
os.makedirs(new_path)
z = zipfile.ZipFile(DIR_RECHTSPRAAK + '.zip')
n_zips = len(z.namelist())
for f in z.namelist():
    if f.endswith('.zip'):
        print(f'{f}/{n_zips}')
        # get directory name from file
        dirname = os.path.dirname(f)
        if not os.path.exists(new_path + dirname):
            os.mkdir(new_path + dirname)
        new_dir = os.path.splitext(f)[0]
        # create new directory
        os.mkdir(new_path + new_dir)
        # read inner zip file into bytes buffer
        content = io.BytesIO(z.read(f))
        zip_file = zipfile.ZipFile(content)
        for i in zip_file.namelist():
            zip_file.extract(i, new_path + new_dir)
print('All files extracted.')
