"""
Very simple function - removes the logs in the log directory of an airflow instance.
"""

from os import listdir
from os.path import join
from shutil import rmtree

from definitions.storage_handler import DIR_LOGS


def log_clean():
    all_to_remove = listdir(DIR_LOGS)
    paths = [join(DIR_LOGS, x) for x in all_to_remove if 'dag_id' not in x]
    for file in paths:
        print(f"REMOVING FOLDER : {file}")
        rmtree(file)
    print("Log cleanup finished!")
    return


if __name__ == "__main__":
    log_clean()
