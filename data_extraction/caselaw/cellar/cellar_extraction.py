import json
from os.path import dirname, abspath, basename
from os import getenv
import sys

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
import urllib.request
import time
from datetime import datetime
from definitions.storage_handler import Storage, CELLAR_METADATA
import argparse

from SPARQLWrapper import SPARQLWrapper, JSON

start = time.time()

output_path = CELLAR_METADATA


def get_all_eclis(starting_point=None):
    sparql = SPARQLWrapper('https://publications.europa.eu/webapi/rdf/sparql')
    sparql.setReturnFormat(JSON)
    sparql.setQuery('''
        prefix cdm: <http://publications.europa.eu/ontology/cdm#> 
        prefix celex: <http://publications.europa.eu/resource/celex/>
        prefix owl: <http://www.w3.org/2002/07/owl#>
        prefix xsd: <http://www.w3.org/2001/XMLSchema#>
        prefix skos: <http://www.w3.org/2004/02/skos/core#>
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        select 
        distinct ?ecli
        where { 
            ?doc cdm:case-law_ecli ?ecli .
            %s
        }
        order by asc(?ecli)
    ''' % (f'FILTER(str(?ecli) > "{starting_point}")' if starting_point else '')
    )
    ret = sparql.queryAndConvert()

    eclis = []

    for res in ret['results']['bindings']:
        eclis.append(res['ecli']['value'])

    return eclis


def get_raw_cellar_metadata(eclis, get_labels=True, force_readable_cols=True, force_readable_vals=False):
    """
    Same as `get_citations`, but uses SPARQL, greatly speeding up the process.
    If required, can probably be adapted to go to any depth in one query using subqueries.
    """
    sparql = SPARQLWrapper('https://publications.europa.eu/webapi/rdf/sparql')
    sparql.setReturnFormat(JSON)
    sparql.setQuery('''
        prefix cdm: <http://publications.europa.eu/ontology/cdm#> 
        prefix celex: <http://publications.europa.eu/resource/celex/>
        prefix owl: <http://www.w3.org/2002/07/owl#>
        prefix xsd: <http://www.w3.org/2001/XMLSchema#>
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
    ''' % ('", "'.join(eclis)))
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
        if not res['p']['value'].startswith('http://publications.europa.eu/ontology/cdm#'):
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

        if key in metadata[ecli]:
            metadata[ecli][key].append(val)
        else:
            metadata[ecli][key] = [val]

    return metadata


if __name__ == '__main__':
    # set up storage location
    parser = argparse.ArgumentParser()
    parser.add_argument('storage', choices=['local', 'aws'], help='location to save output data to')
    parser.add_argument('--amount', help='number of documents to retrieve', type=int, required=False)
    parser.add_argument('--concurrent-docs', default=200, type=int,
                        help='default number of documents to retrieve concurrently', required=False)
    args = parser.parse_args()

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

    print(f"Downloading {args.amount if 'amount' in args else 'all'} CELLAR documents")

    eclis = get_all_eclis()

    print(f"Found {len(eclis)} ECLIs")

    if 'amount' in args:
        eclis = eclis[:args.amount]

    all_eclis = {}

    for i in range(0, len(eclis), args.concurrent_docs):
        new_eclis = get_raw_cellar_metadata(eclis[i:(i + args.concurrent_docs)])
        all_eclis = {**all_eclis, **new_eclis}

    with open(output_path, 'w') as f:
        json.dump(all_eclis, f)

    print(f"\nUpdating {args.storage} storage ...")
    storage.finish_pipeline()

    end = time.time()
    print("\n--- DONE ---")
    print("Time taken: ", time.strftime('%H:%M:%S', time.gmtime(end - start)))
