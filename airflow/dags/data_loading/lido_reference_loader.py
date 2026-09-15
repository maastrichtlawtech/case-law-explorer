"""
DEPRECATED. Used to load Rechtspraak law references from a separate pg_lido
database into cle_v2.case_law_reference, built monthly by a standalone
lido_postgres DAG (airflow/dags/lido/) that independently downloaded and
parsed the same 12GB LIDO export as lido_sqlite_build.

pg_lido is gone. lido_postgres's parsing logic now lives in the
rechtspraak-lido-sqlite package itself (case AND law subjects, one pass,
one lido.db), and its former Postgres-loading role is
airflow/dags/lido/tasks/merge_into_cle.py, run as the last task of
lido_sqlite_build -- it merges lido.db's law_element/case_law/law_alias
tables straight into cle_v2 (legislation/legal_provision/legislation_alias/
case_law_reference), no intermediate database. rechtspraak_etl.py no longer
calls this module.

Do not remove this file until that merge path's case_law_reference coverage
(source_dataset='rs_lido_ref'/'rs_lido_linkt') has been spot-checked against
what this module used to produce from pg_lido, in case anything relied on it
running from rechtspraak_etl specifically rather than from lido_sqlite_build.
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
