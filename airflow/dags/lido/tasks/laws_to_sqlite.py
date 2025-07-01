import logging
import sys
from lido.utils.sqlite import get_conn
from lido.utils.stream import stream_triples
from lido.config import FILE_SQLITE_DB, MAX_PARSE_ERR_COUNT

TERM_URI_TYPE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'

REGELING_ONDERDELEN = {
    'http://linkeddata.overheid.nl/terms/Wet': 'wet',
    'http://linkeddata.overheid.nl/terms/Deel': 'deel',
    'http://linkeddata.overheid.nl/terms/Boek': 'boek',
    'http://linkeddata.overheid.nl/terms/Titeldeel': 'titeldeel',
    'http://linkeddata.overheid.nl/terms/Hoofdstuk': 'hoofdstuk',
    'http://linkeddata.overheid.nl/terms/Artikel': 'artikel',
    'http://linkeddata.overheid.nl/terms/Paragraaf': 'paragraaf',
    'http://linkeddata.overheid.nl/terms/SubParagraaf': 'subparagraaf',
    'http://linkeddata.overheid.nl/terms/Afdeling': 'afdeling',
}

def insert_law_element(cursor, law_element):
    assert all(key in law_element and law_element[key] is not None for key in ['type', 'bwb_id', 'lido_id', 'title'])
    
    # if cursor_is_sqlite(cursor):
    cursor.execute("INSERT OR IGNORE INTO law_element (type, bwb_id, bwb_label_id, lido_id, jc_id, number, title) VALUES (?, ?, ?, ?, ?, ?, ?);",
        (
            law_element['type'], 
            law_element['bwb_id'],
            law_element.get('bwb_label_id'),
            law_element['lido_id'],
            law_element.get('jc_id'),
            law_element.get('number'),
            law_element.get('title'),
            # law_element['title'],
        )
    )
    # else:
    #     cursor.execute("""
    #         INSERT INTO law_element
    #             (type, bwb_id, bwb_label_id, lido_id, jc_id, number, title)
    #         VALUES
    #             (%s, %s, %s, %s, %s, %s, %s)
    #         ON CONFLICT DO NOTHING;
    #     """,
    #         (
    #             law_element['type'], 
    #             law_element['bwb_id'],
    #             law_element.get('bwb_label_id'),
    #             law_element['lido_id'],
    #             law_element.get('jc_id'),
    #             law_element.get('number'),
    #             law_element.get('title'),
    #             # law_element['title'],
    #         )
    #     )
        

def strip_lido_law_id(lido_law_id):
    if lido_law_id[0:43] == "http://linkeddata.overheid.nl/terms/bwb/id/" and len(lido_law_id) > 43:
        return lido_law_id[43:]
    return None

def process_law_element(cursor, type, subject, predicates):
    le = {}

    le["type"] = "law"

    # http://linkeddata.overheid.nl/terms/bwb/id/BWBR0001831/799354/1827-12-13/1827-12-13
    stripped_id = strip_lido_law_id(subject)
    if stripped_id is None:
        logging.error("Item with subject", subject, "has incorrect format")
        return False
    
    le["lido_id"] = stripped_id

    bwb_match = le["lido_id"].split("/")[0]
    if bwb_match:
        le['bwb_id'] = bwb_match
    else:
        logging.error("No BWB-id for subject:", subject)
        return False

    bwb_label_id_match = le["lido_id"].split("/")[1]
    if bwb_label_id_match:
        le['bwb_label_id'] = bwb_label_id_match

    le["title"] = predicates.get('http://purl.org/dc/terms/title', [None])[0]
    if le["title"] is None:
        le["title"] = predicates.get('http://www.w3.org/2004/02/skos/core#prefLabel', [None])[0]
    if le["title"] is None:
        le["title"] = predicates.get('http://www.w3.org/2000/01/rdf-schema#label', [None])[0]
    
    le["type"] = type
    le['jc_id'] = None

    jcid = predicates.get('http://linkeddata.overheid.nl/terms/heeftJuriconnect')
    if jcid is not None:
        jci13 = next((x for x in jcid if x[0:6]=='jci1.3'), None) # first jc
        if jci13 is not None:
            le['jc_id'] = jci13

    onderdeel_nummer = predicates.get('http://linkeddata.overheid.nl/terms/heeftOnderdeelNummer')
    if onderdeel_nummer is not None and len(onderdeel_nummer) == 1:
        le['number'] = onderdeel_nummer[0]

    insert_law_element(cursor, le)

def process_law_triples(db_path, triples_path):
    
    conn = get_conn(db_path)

    cursor = conn.cursor()

    i = 0
    last_law_count = 0
    law_count = 0
    err_count = 0

    print("Start processing law items")

    for subject, props in stream_triples(triples_path):
        try:
            i+=1
            
            if i % 50000 == 0:
                delta = law_count - last_law_count
                last_law_count = law_count
                print("-", i, "->", law_count, f"(+ {delta})" if delta > 0 else "")

            type = props.get(TERM_URI_TYPE, [None])[0]
            if type is not None and type in REGELING_ONDERDELEN:
                law_count += 1
                
                # with tc.timed("process element"):
                process_law_element(cursor, REGELING_ONDERDELEN[type], subject, props)

                # with tc.timed("commit to db"):
                if law_count % 50000 == 0:
                    print(" ", i, "->", law_count, "*commit*")
                    conn.commit()
            elif type is not None:
                pass
                # logging.error(f"Uncaught type {type} for subject {subject}")
        
        except Exception as err:
            logging.error("** Error:", err)
            logging.error("** i, subject, props:", i, subject,"\n")
            err_count+=1
            if err_count>=MAX_PARSE_ERR_COUNT:
                logging.error("Max error count exceeded. Raising error.")
                raise err
            continue
    
    conn.commit()
    cursor.close()
    print(f"Finished processing {law_count} law elements (with {err_count} errors)")
