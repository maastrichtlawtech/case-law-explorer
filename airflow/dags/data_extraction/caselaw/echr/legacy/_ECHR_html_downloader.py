import pandas as pd
import sys
import requests
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'


def metadata_to_html(filename_metadata):
    def download_html(item_ids, timeout, retry, n_downloaded=0, n_empty=0, n_failed=0):
        retry_ids = []

        for counter, item_id in enumerate(item_ids):
            if counter % 100 == 0:
                print(f'{counter}/{len(item_ids)} items processed ...')
            try:
                r = requests.get(base_url + item_id, timeout=1)
                print(base_url+item_id)
                if r.text == '':
                    n_empty += 1
                    with open (f'../../../data/echr/{filename_metadata}_empty.txt', 'a') as f:
                        f.write(item_id + '\n')
                    #print(f'Document {item_id} empty.')
                else:
                    n_downloaded += 1
                    with open(f'../../../data/echr/{item_id}.html', 'w') as f:
                        f.write(str(r.text.encode(sys.stdout.encoding, errors='replace')))
            except Exception as e:
                if retry:
                    retry_ids.append(item_id)
                else:
                    n_failed += 1
                    with open (f'../../../data/echr/{filename_metadata}_failed.txt', 'a') as f:
                        f.write(item_id + '\n')
                    print(f'Download of document {item_id} failed. ', e)

        return retry_ids, n_downloaded, n_empty, n_failed

    df = pd.read_csv('../../../data/echr/' + filename_metadata, usecols=['itemid'])
    base_url = 'https://hudoc.echr.coe.int/app/conversion/docx/html/body?library=ECHR&id='

    # download html pages for each document
    retry_ids, n_downloaded, n_empty, n_failed = download_html(item_ids=df['itemid'], timeout=1, retry=True)
    _, n_downloaded, n_empty, n_failed = download_html(item_ids=retry_ids, timeout=5, retry=False,
                                                       n_downloaded=n_downloaded, n_empty=n_empty, n_failed=n_failed)

    print(f"Done! {n_downloaded}/{len(df)} documents downloaded ({n_empty} empty, {n_failed} failed).")

metadata_to_html(filename_metadata='ECHR_metadata.csv')