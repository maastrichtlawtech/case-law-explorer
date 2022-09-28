import requests, json, xmltodict, pandas as pd, argparse
from datetime import date, datetime

from os.path import dirname, abspath
import sys
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_RECHTSPRAAK


# Check whether the API is working
def check_api(url):
    response = requests.get(f"{url}")

    # Return with the response code
    return response.status_code

def get_date(url):
    res = requests.get(url)
    res.raw.decode_content = True

    xpars = xmltodict.parse(res.text)
    json_string = json.dumps(xpars)
    json_object = json.loads(json_string)
    json_object = json_object['feed']['entry']

    return json_object

def save_csv(json_object, file_name):
    # Define the dataframe to enter the data
    df = pd.DataFrame(columns=['id', 'title', 'summary', 'updated', 'link'])
    ecli_id = []
    title = []
    summary = []
    updated = []
    link = []

    for i in json_object:
        ecli_id.append(i['id'])
        title.append(i['title']['#text'])
        if '#text' in i['summary']:
            summary.append(i['summary']['#text'])
        else:
            summary.append("No summary available")
        updated.append(i['updated'])
        link.append(i['link']['@href'])

    df['id'] = ecli_id
    df['title'] = title
    df['summary'] = summary
    df['updated'] = updated
    df['link'] = link

    print(df.head())
    print(df.shape)

    # Save CSV file
    df.to_csv(DIR_DATA_RECHTSPRAAK + "\\" + file_name + '.csv', index=False)


def rechspraak_downloader(args):
    # Define the base URL
    base_url = "https://data.rechtspraak.nl/uitspraken/zoeken?"
    print("Rechtspraak dump downloader API")

    # Arguements to pass to API
    parser = argparse.ArgumentParser()
    parser.add_argument('--max', help='Maximum number of ECLIs to retrieve', type=int, required=False, default=10)
    parser.add_argument('--starting-date', help='Starting date', required=False, default='2022-08-01')
    parser.add_argument('--ending-date', help='Ending date', required=False)
    args = parser.parse_args(args)

    amount = args.max
    starting_date = args.starting_date

    # If end date is not entered, the current date is taken
    today = date.today()
    ending_date = today.strftime("%Y-%m-%d")
    if args.ending_date:
        ending_date = args.ending_date

    # Build the URL after getting all the arguements
    url = base_url + 'max=' + str(amount) + '&date=' + starting_date + '&date=' + ending_date

    print("Checking the API")
    # Check the working of API
    response_code = check_api(url)
    if response_code == 200:
        print("API is working fine!")
        print("Getting " + str(amount) + " documents from " + starting_date + " till " + ending_date)
        json_object = get_date(url)
        if json_object:
            # Get current time
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")

            # Make file name
            file_name = 'Rechtspraak_' + starting_date + '_' + ending_date + '_' + current_time

            save_csv(json_object, file_name)
            print("Data saved to CSV file successfully.")
    else:
        print(f"URL returned with a {response_code} error code")

if __name__ == '__main__':
    rechspraak_downloader(sys.argv[1:])