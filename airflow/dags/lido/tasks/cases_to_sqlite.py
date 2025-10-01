import sys

from lido.config import TBL_CASE_LAW, TBL_CASES, TBL_LAWS
from lido.utils.helpers import strip_lido_law_id
from lido.utils.sqlite import get_conn

# from lido.utils.benchmarking import TimerCollector
from lido.utils.stream import stream_triples


def get_law_element_by_lido_id(cursor, lido_id):
    stripped_id = strip_lido_law_id(lido_id)  # -> BWBR0001826/1711894/1821-08-01/1821-08-01
    if stripped_id is None:  # could be due to being ref to ecli
        return (None, None)

    cursor.execute(
        f"SELECT id FROM {TBL_LAWS} INDEXED BY sqlite_autoindex_law_element_1 WHERE lido_id = ? LIMIT 1",
        (stripped_id,),
    )
    result = cursor.fetchone()
    if result:
        return (stripped_id, result[0])

    # # print("not found:", lido_id)
    bwb_id, bwb_label_id = stripped_id.split("/")[0:2]
    # https://linkeddata.overheid.nl/terms/bwb/id/BWBR0001826/1711894
    cursor.execute(
        f"SELECT id FROM {TBL_LAWS} INDEXED BY idx_bwb_id WHERE bwb_id = ? AND bwb_label_id = ? LIMIT 1",
        (
            bwb_id,
            bwb_label_id,
        ),
    )
    result = cursor.fetchone()
    if result:
        return ("/".join([bwb_id, bwb_label_id]), result[0])

    # https://linkeddata.overheid.nl/terms/bwb/id/BWBR0001826
    cursor.execute(
        f"SELECT id FROM {TBL_LAWS} INDEXED BY idx_bwb_id WHERE bwb_id = ? LIMIT 1", (bwb_id,)
    )
    result = cursor.fetchone()
    if result:
        return (bwb_id, result[0])

    return (None, None)


def insert_case(cursor, case):
    assert all(key in case and case[key] is not None for key in ["ecli_id"])

    cursor.execute(
        f"INSERT OR IGNORE INTO {TBL_CASES} (ecli_id, title, zaaknummer, uitspraakdatum) VALUES (?, ?, ?, ?)",
        (
            case["ecli_id"],
            case.get("title"),
            case.get("zaaknummer"),
            case.get("uitspraakdatum"),
        ),
    )
    if cursor.rowcount > 0:
        return cursor.lastrowid
    else:
        cursor.execute(f"SELECT id FROM {TBL_CASES} WHERE ecli_id = ? LIMIT 1;", (case["ecli_id"],))
        row = cursor.fetchone()
        if not row:
            print("NOT FOUND ecli:", case["ecli_id"])
        return row[0] if row else None


def insert_caselaw(cursor, caselaw):
    assert all(
        key in caselaw and caselaw[key] is not None
        for key in ["case_id", "law_id", "source", "lido_id"]
    )

    cursor.execute(
        f"INSERT OR IGNORE INTO {TBL_CASE_LAW} (case_id, law_id, source, jc_id, lido_id, opschrift) VALUES (?, ?, ?, ?, ?, ?)",
        (
            caselaw["case_id"],
            caselaw["law_id"],
            caselaw["source"],
            caselaw.get("jc_id"),
            caselaw["lido_id"],
            caselaw.get("opschrift"),
        ),
    )


# map_terms = {
#     'http://purl.org/dc/terms/identifier': 'ecli_id',
#     'http://purl.org/dc/terms/type': 'dct_type',
#     'http://www.w3.org/1999/02/22-rdf-syntax-ns#type': 'lido_type',
#     'http://purl.org/dc/terms/title': 'title_1',
#     'http://www.w3.org/2000/01/rdf-schema#label': 'title_2',
#     'http://www.w3.org/2004/02/skos/core#prefLabel': 'title_3',
#     'http://linkeddata.overheid.nl/terms/refereertAan': 'link_ref',
#     'http://linkeddata.overheid.nl/terms/linkt': 'link_linkt',
#     'http://linkeddata.overheid.nl/terms/heeftUitspraakdatum': 'datum_uitspraak',
#     'http://linkeddata.overheid.nl/terms/heeftZaaknummer': 'zaaknummer',
# }


def process_case_block(cursor, subject, props):
    case = {}

    # props = {map_terms[k]: v for k, v in props.items()}

    ecli_id = subject.split("/")[-1]  # approach one to get ecli
    # if not ecli_id or ecli_id[0:4] != "ECLI":
    #     ecli_id = props.get('ecli_id', [None])[0] # approach two to get ecli
    if not ecli_id or ecli_id[0:4] != "ECLI":
        print("No ecli-id found in subject:", subject)
        return
    case["ecli_id"] = ecli_id

    # case["title"] = props['title_1'] or props['title_2'] or props['title_3'] or []
    case["title"] = props.get(
        "http://purl.org/dc/terms/title",
        props.get(
            "http://www.w3.org/2000/01/rdf-schema#label",
            props.get("http://www.w3.org/2004/02/skos/core#prefLabel", [None]),
        ),
    )[0]

    case["zaaknummer"] = (
        ",".join(props.get("http://linkeddata.overheid.nl/terms/heeftZaaknummer", [])) or None
    )
    case["uitspraakdatum"] = props.get(
        "http://linkeddata.overheid.nl/terms/heeftUitspraakdatum", [None]
    )[0]

    # print(case)
    case_id = insert_case(cursor, case)
    if case_id is None:
        raise Exception("NO CASE ID!", subject)

    links = props.get("http://linkeddata.overheid.nl/terms/linkt", [])
    for link in links:
        # print("LINK", link)
        matched_law_lido_id, law_id = get_law_element_by_lido_id(cursor, link)
        if law_id is None:
            continue
        caselaw = {
            "case_id": case_id,
            "law_id": law_id,
            "source": "lido-linkt",
            "jc_id": None,
            "lido_id": matched_law_lido_id,
            "opschrift": None,
        }
        insert_caselaw(cursor, caselaw)

    referenties = props.get("http://linkeddata.overheid.nl/terms/refereertAan", [])
    for ref in referenties:
        # linktype=http://linkeddata.overheid.nl/terms/linktype/id/lx-referentie|target=bwb|uri=jci1.3:c:BWBR0005288&boek=5&titeldeel=1&artikel=1&z=2024-01-01&g=2024-01-01|lido-id=http://linkeddata.overheid.nl/terms/bwb/id/BWBR0005288/1723924/1992-01-01/1992-01-01|opschrift=artikel 5:1 BW
        ref_props = dict(
            ((item.split("=", 1) + [None])[:2]) for item in ref.split("|")
        )  # <- split first on pipe, then on equal (=) max 2, then pad right with None
        if ref_props.get("lido-id") is not None:
            # print("REF LINK", ref_props.get('lido-id'))
            matched_law_lido_id, law_id = get_law_element_by_lido_id(
                cursor, ref_props.get("lido-id")
            )
            if law_id is None:
                continue
            caselaw = {
                "case_id": case_id,
                "law_id": law_id,
                "source": "lido-ref",
                "jc_id": ref_props.get("uri"),
                "lido_id": matched_law_lido_id,
                "opschrift": ref_props.get("opschrift"),
            }
            insert_caselaw(cursor, caselaw)


def process_case_triples(db_path, triples_path):

    conn = get_conn(db_path)

    cursor = conn.cursor()

    i = 0
    case_count = 0
    # last_case_count = 0
    err_count = 0

    print("Start processing case items")

    for subject, props in stream_triples(triples_path):
        try:
            case_count += 1

            # if case_count % 50000 == 0:
            #     delta = case_count - last_case_count
            #     last_case_count = case_count
            #     print("-", case_count, f"(+ {delta})" if delta > 0 else "")

            process_case_block(cursor, subject, props)

            # with tc.timed("commiting"):
            if case_count % 50000 == 0:
                # delta = case_count - last_case_count
                print(" ", case_count, "*commit*")
                conn.commit()

        except Exception as err:
            print("** Error:", err, file=sys.stderr)
            print("** i, subject, props:", i, subject, "\n", props, file=sys.stderr)
            err_count += 1
            if err_count >= 100:
                print("Max error count exceeded. Raising error.")
                raise err
            continue

    conn.commit()
    cursor.close()
    print(f"Finished processing {case_count} cases (with {err_count} errors)")
