import requests, pandas as pd, os, glob, sys, urllib.request, time

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_RECHTSPRAAK_CSV

from bs4 import BeautifulSoup


def extract_data_from_html(filename):
    soup = BeautifulSoup(open(filename), "html.parser")
    return soup

def check_api(url):
    response = requests.get(f"{url}")

    # Return with the response code
    return response.status_code

def save_csv(dataframe, file_name):
    # df = pd.DataFrame(columns=['id', 'uitspraak'])
    # ecli_id = []
    # uitspraak = []
    dataframe.to_csv(DIR_RECHTSPRAAK_CSV + "/" + file_name + "_metadata.csv")
    print("Metadata of " + file_name + " saved" + "\n")

def read_csv():
    path = DIR_RECHTSPRAAK_CSV
    csv_files = glob.glob(path + "/*.csv")
    files = []
    for i in csv_files:
        if 'metadata' not in i:
            files.append(i)
    print("Found " + str(len(files)) + " CSV file(s)")
    return files

def metadata_api():
    print("Reading CSV files...")
    csv_files = read_csv()

    if len(csv_files) > 0:
        print("Rechtspraak metadata API")

        # Get start time
        st = time.time()

        for f in csv_files:
            df = pd.read_csv(f)

            rechtspraak_df = pd.DataFrame(columns=['ecli_id', 'uitspraak'])
            ecli_df = []
            uitspraak_df = []

            for k in df.itertuples():
                # Build the URL
                ecli_id = str(k.id)
                url = "https://uitspraken.rechtspraak.nl/InzienDocument?id=" + ecli_id
                # url = "https://data.rechtspraak.nl/uitspraken/content?id=" + ecli_id

                # Check if API is working
                response_code = check_api(url)
                if response_code == 200:
                    uitspraak = ''

                    print("API is working!")

                    print("Getting metadata for " + ecli_id)

                    # Create HTML file
                    html_file = ecli_id + ".html"
                    urllib.request.urlretrieve(url, html_file)

                    # Extract data frp, HTML
                    html_object = extract_data_from_html(html_file)

                    soup = BeautifulSoup(str(html_object), features='lxml')

                    # Get data
                    uitspraak_info = soup.find_all("div", {"class": "uitspraak-info"})
                    section = soup.find_all("div", {"class": "section"})

                    uitspraak = BeautifulSoup(str(uitspraak_info), features='lxml').get_text()
                    uitspraak = uitspraak + BeautifulSoup(str(section), features='lxml').get_text()

                    ecli_df.append(ecli_id)
                    uitspraak_df.append(uitspraak)

                    print("Metadata obtained for " + ecli_id)
                    print("\n")

                    uitspraak = ''
                    ecli_id = ''

                    if os.path.exists(html_file):
                        os.remove(html_file)

            print("Creating CSV file...")
            rechtspraak_df['ecli_id'] = ecli_df
            rechtspraak_df['uitspraak'] = uitspraak_df
            save_csv(rechtspraak_df, f.split('/')[-1][:len(f.split('/')[-1]) - 4])

            # Get end time
            et = time.time()

            elapsed_time = et - st

            print("Total time taken: " + str(round(elapsed_time, 2)) + " seconds")

if __name__ == '__main__':
    metadata_api()