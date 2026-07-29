"""
Loads Rechtspraak law references from the pg_lido database into
cle_v2.case_law_reference.

The lido_postgres DAG builds pg_lido monthly from the LIDO export at
data.overheid.nl. This reads what it built rather than asking the LIDO web
service for the same thing again: the extraction already stopped calling that
service, and the export is the same data without a credential or a rate limit
in front of it.

The two schemas were made for each other. pg_lido's case_law.source is
'lido-ref' or 'lido-linkt', and case_law_reference.source_dataset documents
'rs_lido_ref' and 'rs_lido_linkt'; case_law.opschrift is the verbatim citation
string that raw_reference is described as holding. This is the join those
comments were written for.

Case-to-case citations are not here. pg_lido links cases to legislation and
nothing else, so case_citation is not something this can populate.
"""

import logging

from airflow.providers.postgres.hooks.postgres import PostgresHook

CONN_PG_LIDO = "pg_lido"

# pg_lido's own vocabulary on the left, cle_v2's on the right. 'custom' is a
# third value the staging table allows; it is passed through under its own name
# rather than folded into either of the LIDO ones, because provenance is the
# entire point of the column.
SOURCE_DATASETS = {
    "lido-ref": "rs_lido_ref",
    "lido-linkt": "rs_lido_linkt",
    "custom": "rs_lido_custom",
}

REFERENCES_FOR_ECLIS = """
    SELECT lc.ecli_id,
           cl.source,
           cl.opschrift,
           le.bwb_id,
           le.bwb_label_id
    FROM case_law cl
    JOIN legal_case lc ON lc.id = cl.case_id
    JOIN law_element le ON le.id = cl.law_id
    WHERE lc.ecli_id = ANY(%(eclis)s)
"""


def load_law_references(client, eclis, lido_conn_id: str = CONN_PG_LIDO) -> int:
    """Copy law references for `eclis` from pg_lido into case_law_reference.

    `client` is a PostgresCLEClient. Returns the number of references written.

    Unreachable pg_lido is logged and returns zero rather than raising: the
    references are an enrichment of cases that are already loaded, and failing
    the whole run over them would throw away a good extraction.
    """
    eclis = [e for e in (eclis or []) if e]
    if not eclis:
        return 0

    try:
        rows = PostgresHook(postgres_conn_id=lido_conn_id).get_records(
            REFERENCES_FOR_ECLIS, parameters={"eclis": eclis}
        )
    except Exception:
        logging.exception(
            "Could not read law references from %s. The cases are loaded; their "
            "legislation references are not.",
            lido_conn_id,
        )
        return 0

    if not rows:
        logging.info("pg_lido holds no law references for these %d cases.", len(eclis))
        return 0

    # One lookup per ECLI rather than per reference: a case cites many acts.
    case_ids: dict[str, int | None] = {}
    written = 0
    unresolved = set()

    for ecli, source, opschrift, bwb_id, bwb_label_id in rows:
        if ecli not in case_ids:
            case_ids[ecli] = client.resolve_case_id(ecli=ecli)
        case_id = case_ids[ecli]
        if case_id is None:
            unresolved.add(ecli)
            continue

        client.upsert_law_reference(
            case_id=case_id,
            raw_reference=opschrift or bwb_id or "",
            raw_resource=bwb_id,
            role="cited",
            source_dataset=SOURCE_DATASETS.get(source, "rs_lido"),
        )
        written += 1

    if unresolved:
        # Expected rather than alarming: pg_lido covers all of Rechtspraak,
        # while cle_v2 holds whatever windows have been extracted so far.
        logging.info(
            "%d ecli(s) in pg_lido are not in cle_v2 yet; their references were skipped.",
            len(unresolved),
        )

    logging.info("Wrote %d law reference(s) from pg_lido.", written)
    return written
