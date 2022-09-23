import json
from os.path import dirname, abspath, basename, join
from os import getenv
import sys
import shutil
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import urllib.request
import time, glob
from datetime import datetime
from definitions.storage_handler import CELLAR_DIR, Storage,CELLAR_ARCHIVE_DIR

import argparse

from SPARQLWrapper import SPARQLWrapper, JSON, POST
from os.path import exists

start = time.time()

# We set the filename to the current date/time for later reference if we want to incrementally build.
run_date = datetime.now().isoformat(timespec='seconds')
output_path = join(CELLAR_DIR, run_date.replace(':', '_') + '.json')


def get_all_eclis(starting_ecli=None, starting_date=None):
    """Gets a list of all ECLIs in CELLAR. If this needs to be picked up from a previous run,
    the last ECLI parsed in that run can be used as starting point for this run

    :param starting_ecli: ECLI to start working from - alphabetically, defaults to None
    :type starting_ecli: str, optional
    :param starting_date: Document modification date to start off from.
        Can be set to last run to only get updated documents.
        Ex. 2020-03-19T09:41:10.351+01:00
    :type starting_date: str, optional
    :return:  A list of all (filtered) ECLIs in CELLAR.
    :rtype: list[str]
    """

    # This query essentially gets all things from cellar that have an ECLI.
    # It then sorts that list, and if necessary filters it based on an ECLI to start off from.
    endpoint = 'https://publications.europa.eu/webapi/rdf/sparql'
    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)

    sparql.setQuery('''
        prefix cdm: <http://publications.europa.eu/ontology/cdm#> 
        select 
        distinct ?ecli
        where { 
            ?doc cdm:case-law_ecli ?ecli .
            ?doc <http://publications.europa.eu/ontology/cdm/cmr#lastModificationDate> ?date .
            %s
            %s
        }
        order by asc(?ecli)
    ''' % (
        f'FILTER(STR(?ecli) > "{starting_ecli}")' if starting_ecli else '',
        f'FILTER(STR(?date) >= "{starting_date}")' if starting_date else ''
    )
                    )
    ret = sparql.queryAndConvert()

    eclis = []

    # Extract the actual results
    for res in ret['results']['bindings']:
        eclis.append(res['ecli']['value'])

    return eclis


def get_raw_cellar_metadata(eclis, get_labels=True, force_readable_cols=True, force_readable_vals=False):
    """Gets cellar metadata

    :param eclis: The ECLIs for which to retrieve metadata
    :type eclis: list[str]
    :param get_labels: Flag to get human-readable labels for the properties, defaults to True
    :type get_labels: bool, optional
    :param force_readable_cols: Flag to remove any non-labelled properties from the resulting dict, defaults to True
    :type force_readable_cols: bool, optional
    :param force_readable_vals: Flag to remove any non-labelled values from the resulting dict, defaults to False
    :type force_readable_vals: bool, optional
    :return: Dictionary containing metadata. Top-level keys are ECLIs, second level are property names
    :rtype: Dict[str, Dict[str, list[str]]]
    """

    # Find every outgoing edge from an ECLI document and return it (essentially giving s -p> o)
    # Also get labels for p/o (optionally) and then make sure to only return distinct triples
    endpoint = 'https://publications.europa.eu/webapi/rdf/sparql'
    query = '''
        prefix cdm: <http://publications.europa.eu/ontology/cdm#> 
        prefix skos: <http://www.w3.org/2004/02/skos/core#>
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        select 
        distinct ?ecli ?p ?o ?plabel ?olabel
        where { 
            ?doc cdm:case-law_ecli ?ecli .
            FILTER(STR(?ecli) in ("%s"))
            ?doc ?p ?o .
            OPTIONAL {
                ?p rdfs:label ?plabel
            }
            OPTIONAL {
                ?o skos:prefLabel ?olabel .
                FILTER(lang(?olabel) = "en") .
            }
        }
    ''' % ('", "'.join(eclis))

    sparql = SPARQLWrapper(endpoint)

    sparql.setReturnFormat(JSON)
    sparql.setMethod(POST)
    sparql.setQuery(query)
    ret = sparql.queryAndConvert()

    # Create one dict for each document
    metadata = {}
    for ecli in eclis:
        metadata[ecli] = {}

    # Take each triple, check which source doc it belongs to, key/value pair into its dict derived from the p and o in
    # the query
    for res in ret['results']['bindings']:
        ecli = res['ecli']['value']
        # We only want cdm predicates
        if not res['p']['value'].startswith('http://publications.europa.eu/ontology/cdm'):
            continue

        # Check if we have predicate labels
        if 'plabel' in res and get_labels:
            key = res['plabel']['value']
        elif force_readable_cols:
            continue
        else:
            key = res['p']['value']
            key = key.split('#')[1]

        # Check if we have target labels
        if 'olabel' in res and get_labels:
            val = res['olabel']['value']
        elif force_readable_vals:
            continue
        else:
            val = res['o']['value']

        # We store the values for each property in a list.
        # For some properties this is not necessary, but if a property can be assigned multiple times, this is important.
        # Notable, for example is citations.b
        if key in metadata[ecli]:
            metadata[ecli][key].append(val)
        else:
            metadata[ecli][key] = [val]

    return metadata

# def download_locally():
#     print('\n--- PREPARATION ---\n')
#     print('OUTPUT DATA STORAGE:\t', args.storage)
#     print('OUTPUT:\t\t\t', output_path)
#     storage = Storage(location="local")
#     storage.setup_pipeline(output_paths=[output_path])
#     last_updated = storage.pipeline_last_updated
#     print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

#     print('\n--- START ---\n')
#     date_time_obj = datetime.now()
#     date = str(date_time_obj.year) + '-' + str(date_time_obj.month) + '-' + str(date_time_obj.day)

#     print(f"Downloading {'all'} CELLAR documents")


#     print('Starting from the last update the script can find')
#     eclis = get_all_eclis(starting_date=last_updated.isoformat())

#     # print(args)

#     print(f"Found {len(eclis)} ECLIs")

#     if args.amount:
#         eclis = eclis[:args.amount]

#     all_eclis = {}

#     for i in range(0, len(eclis), args.concurrent_docs):
#         new_eclis = get_raw_cellar_metadata(eclis[i:(i + args.concurrent_docs)])
#         all_eclis = {**all_eclis, **new_eclis}

#     with open(output_path, 'w') as f:
#         json.dump(all_eclis, f)

    """ Code for getting individual ECLIs
    all_eclis = {}
    new_eclis = {}

    # Check if ECLI already exists
    print(f'Checking for duplicate ECLIs')
    duplicate = 0;
    temp_eclis = []
    for i in range(0, len(eclis)):
    	temp_path = join(CELLAR_DIR, eclis[i] + '.json')
    	if exists(temp_path):
    	    duplicate = 1
    	temp_eclis.append(eclis[i])


    if duplicate == 1:
    	print(f'Duplicate data found. Ignoring duplicate data.')
    else:
    	print(f'No duplicate data found.')

    if len(temp_eclis) > 0:
        for i in range(0, len(temp_eclis), args.concurrent_docs):
        	new_eclis = get_raw_cellar_metadata(temp_eclis[i:(i + args.concurrent_docs)])
        	# all_eclis = {**all_eclis, **new_eclis}
        	temp_path = join(CELLAR_DIR, temp_eclis[i] + '.json')

        	with open(temp_path, 'w') as f:
        		json.dump(new_eclis, f, indent=4)
        	new_eclis.clear()
    """

    # print(f"\nUpdating {args.storage} storage ...")
    # storage.finish_pipeline()

    # end = time.time()
    # print("\n--- DONE ---")
    # print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

def cellar_extract(args):
    # set up storage location
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument('--amount', help='number of documents to retrieve', type=int, required=False)
    parser.add_argument('--concurrent-docs', default=200, type=int,
                        help='default number of documents to retrieve concurrently', required=False)
    parser.add_argument('--starting-date', help='Last modification date to look forward from', required=False)
    parser.add_argument('--fresh', help='Flag for running a complete download regardless of existing downloads',
                        action='store_true')
    args = parser.parse_args(args)

    print('\n--- PREPARATION ---\n')
    print('OUTPUT DATA STORAGE:\t', args.storage)
    print('OUTPUT:\t\t\t', output_path)
    storage = Storage(location=args.storage)
    storage.setup_pipeline(output_paths=[output_path])
    last_updated = storage.pipeline_last_updated
    print('\nSTART DATE (LAST UPDATE):\t', last_updated.isoformat())

    print('\n--- START ---\n')

    date_time_obj = datetime.now()
    date = str(date_time_obj.year) + '-' + str(date_time_obj.month) + '-' + str(date_time_obj.day)

    print(f"Downloading {args.amount if 'amount' in args and args.amount is not None else 'all'} CELLAR documents")

    if args.fresh:
        print('Starting a fresh download')
        eclis = get_all_eclis()
    elif args.starting_date:
        print(f'Starting from manually specified date: {args.starting_date}')
        eclis = get_all_eclis(
            starting_date=args.starting_date
        )
    else:
        print('Starting from the last update the script can find')
        eclis = get_all_eclis(
            starting_date=last_updated.isoformat()
        )

    # print(args)

    print(f"Found {len(eclis)} ECLIs")

    if args.amount:
        eclis = eclis[:args.amount]

    all_eclis = {}

    for i in range(0, len(eclis), args.concurrent_docs):
        new_eclis = get_raw_cellar_metadata(eclis[i:(i + args.concurrent_docs)])
        all_eclis = {**all_eclis, **new_eclis}

    json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))
    if len(json_files) >0: #have to check if there is already a file or no
        source=json_files[0]
        outsource=source.replace(CELLAR_DIR,CELLAR_ARCHIVE_DIR)
        shutil.move(source,outsource)

    with open(output_path, 'w') as f:
        json.dump(all_eclis, f)

    """ Code for getting individual ECLIs
    all_eclis = {}
    new_eclis = {}

    # Check if ECLI already exists
    print(f'Checking for duplicate ECLIs')
    duplicate = 0;
    temp_eclis = []
    for i in range(0, len(eclis)):
    	temp_path = join(CELLAR_DIR, eclis[i] + '.json')
    	if exists(temp_path):
    	    duplicate = 1
    	temp_eclis.append(eclis[i])


    if duplicate == 1:
    	print(f'Duplicate data found. Ignoring duplicate data.')
    else:
    	print(f'No duplicate data found.')

    if len(temp_eclis) > 0:
        for i in range(0, len(temp_eclis), args.concurrent_docs):
        	new_eclis = get_raw_cellar_metadata(temp_eclis[i:(i + args.concurrent_docs)])
        	# all_eclis = {**all_eclis, **new_eclis}
        	temp_path = join(CELLAR_DIR, temp_eclis[i] + '.json')

        	with open(temp_path, 'w') as f:
        		json.dump(new_eclis, f, indent=4)
        	new_eclis.clear()
    """

    print(f"\nUpdating {args.storage} storage ...")
    storage.finish_pipeline()

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))

if __name__ == '__main__':

    #giving arguments to the funtion
    cellar_extract(sys.args[1:])
