"""Decoupled weekly enrichment & auto-resolution DAG.

Each task runs independently (parallel fan-out, zero strict inter-dependencies)
so a failure in one external endpoint (e.g. EUR-Lex Cellar SPARQL) never blocks
any other enrichment or local late-binding pass:

  * refresh_cellar_uuid_cache    - refreshes persistent Cellar UUID -> dossier /
                                   CELEX caches used by cellar_relations;
  * sync_eu_legislation          - discovers newly cited EU CELEX acts in
                                   case_law_reference, fetches metadata from
                                   Cellar SPARQL, writes a hashed ActRecord
                                   artifact, and resolves pending refs;
  * sync_cjeu_appeal_outcomes    - fetches multi-valued Cellar fd_100 procedure
                                   outcomes & overturned appeal statuses, writes
                                   hashed OutcomeRecord/StatusRecord artifacts;
  * resolve_late_citations       - runs global late binding on unresolved
                                   case_citation rows whose targets arrived in
                                   another corpus DAG;
  * resolve_pending_law_refs     - resolves pending CELEX and unique BWB rows
                                   in case_law_reference against legislation.

All five tasks converge on register_promotion (trigger_rule="all_done"), so
etl-promoter replays the verified artifacts and runs the same idempotent
resolutions on production even if one sibling task failed.
"""

import json
import logging
import os
from datetime import datetime

from airflow.operators.python import PythonOperator
from dotenv import find_dotenv, load_dotenv
from etl_factory import DEFAULT_ARGS, get_data_path, get_schedule, register_promotion

from airflow import DAG

RECONCILIATION_DIR = "reconciliation"

dag = DAG(
    dag_id="enrichment_sync_etl",
    default_args=DEFAULT_ARGS,
    description="Decoupled weekly EU legislation sync, Cellar appeal/UUID sync, and automatic late resolution",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule=get_schedule("ENRICHMENT_SYNC", "0 6 * * 1"),
    max_active_runs=1,
    max_active_tasks=5,
)


def _run_tag(context) -> str:
    dag_run = context.get("dag_run")
    conf = (getattr(dag_run, "conf", None) or {}) if dag_run else {}
    if conf.get("window_end"):
        return str(conf["window_end"])[:10]
    logical = context.get("data_interval_end") or context.get("logical_date")
    if logical is not None:
        return logical.strftime("%Y-%m-%d")
    return datetime.utcnow().strftime("%Y-%m-%d")


def _out_dir(context) -> str:
    path = os.path.join(get_data_path(), "processed", RECONCILIATION_DIR, _run_tag(context))
    os.makedirs(path, exist_ok=True)
    return path


def _write_summary(path: str, payload: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
    os.replace(tmp, path)


def run_refresh_cellar_uuid_cache(**_context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.linking import cellar_relations
    from data_loading.clients.postgres import PostgresCLEClient

    cache_dir = os.path.join(get_data_path(), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    dossier_cache = os.environ.get("LINK_CELLAR_UUID_CACHE") or os.path.join(
        cache_dir, "cellar_uuid_dossier.json"
    )
    celex_cache = os.environ.get("LINK_CELLAR_UUID_CELEX_CACHE") or os.path.join(
        cache_dir, "cellar_uuid_celex.json"
    )
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        dossier_added = cellar_relations.refresh_uuid_cache(conn, dossier_cache, predicate="dossier")
        celex_added = cellar_relations.refresh_uuid_cache(conn, celex_cache, predicate="celex")
    summary = {
        "dossier_cache": dossier_cache,
        "dossier_added": dossier_added,
        "celex_cache": celex_cache,
        "celex_added": celex_added,
    }
    logging.info("Cellar UUID cache refresh complete: %s", summary)
    return summary


def run_sync_eu_legislation(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.legislation import cellar_legislation_sync
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    artifact_path = os.path.join(out_dir, "legislation_cellar_sparql.jsonl")
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = cellar_legislation_sync.sync_connection(conn, out_path=artifact_path)
    _write_summary(os.path.join(out_dir, "_legislation_sync_counts.json"), summary)
    logging.info("EU legislation sync complete: %s", summary)
    return summary


def run_sync_cjeu_appeal_outcomes(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.case_context import cellar_appeal_sync
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = cellar_appeal_sync.sync_connection(conn, out_dir=out_dir, load=True)
    _write_summary(os.path.join(out_dir, "_appeal_sync_counts.json"), summary)
    logging.info("CJEU appeal outcomes sync complete: %s", summary)
    return summary


def run_resolve_late_citations(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_loading import link_loader
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        # Find cases matching currently unresolved link targets so late binding
        # runs in seconds even on multi-million-row databases.
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH unresolved AS (
                    SELECT DISTINCT target_ecli_raw, target_celex_raw,
                                    target_ref_scheme, target_ref_raw
                      FROM cle_v2.case_citation
                     WHERE target_case_id IS NULL
                       AND source_dataset = ANY(%s)
                )
                SELECT DISTINCT c.id
                  FROM cle_v2.cases c
                  JOIN unresolved u ON u.target_ecli_raw = c.ecli
                UNION
                SELECT DISTINCT c.id
                  FROM cle_v2.cases c
                  JOIN unresolved u ON u.target_celex_raw = c.celex_id
                UNION
                SELECT DISTINCT ci.case_id
                  FROM cle_v2.case_identifier ci
                  JOIN unresolved u
                    ON u.target_ref_scheme = ci.scheme
                   AND u.target_ref_raw = ci.value
                """,
                (list(link_loader.LINK_DATASETS),),
            )
            case_ids = [int(row[0]) for row in cur.fetchall()]
        conn.rollback()
        result = link_loader.resolve_late(conn, case_ids=case_ids) if case_ids else {}
    summary = {"matched_target_cases": len(case_ids), "resolved": result}
    _write_summary(os.path.join(out_dir, "_late_citations_counts.json"), summary)
    logging.info("Global late citation resolution complete: %s", summary)
    return summary


def run_resolve_pending_law_refs(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.legislation import cellar_legislation_sync
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = cellar_legislation_sync.resolve_pending_refs(conn)
    _write_summary(os.path.join(out_dir, "_law_refs_resolve_counts.json"), summary)
    logging.info("Pending law-reference resolution complete: %s", summary)
    return summary


def run_enrich_legislation_fulltext(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.legislation import legislation_enrichment
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    artifact_path = os.path.join(out_dir, "legislation_enrichment.jsonl")
    limit_celex = int(os.environ.get("LEGISLATION_ENRICH_CELEX_LIMIT", "30"))
    limit_bwb = int(os.environ.get("LEGISLATION_ENRICH_BWB_LIMIT", "30"))
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = legislation_enrichment.enrich_connection(
            conn,
            limit_celex=limit_celex,
            limit_bwb=limit_bwb,
            out_path=artifact_path,
            load=True,
        )
    _write_summary(os.path.join(out_dir, "_legislation_enrichment_counts.json"), summary)
    logging.info("Legislation full-text enrichment complete: %s", summary)
    return summary


def run_extract_cross_court_judges(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.case_context import judges
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    artifact_path = os.path.join(out_dir, "cross_court_judges.jsonl")
    limit_rs = int(os.environ.get("JUDGES_EXTRACT_RS_LIMIT", "2000"))
    limit_echr = int(os.environ.get("JUDGES_EXTRACT_ECHR_LIMIT", "2000"))
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = judges.extract_pending(
            conn,
            limit_rs=limit_rs,
            limit_echr=limit_echr,
            out_path=artifact_path,
            load=True,
        )
    _write_summary(os.path.join(out_dir, "_judges_extraction_counts.json"), summary)
    logging.info("Cross-court judge extraction complete: %s", summary)
    return summary


def run_extract_cjeu_treaties(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.linking import cjeu_treaty
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    artifact_path = os.path.join(out_dir, "cjeu_text_treaty.jsonl")
    limit = int(os.environ.get("CJEU_TREATY_EXTRACT_LIMIT", "2000"))
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = cjeu_treaty.extract_pending(
            conn,
            limit=limit,
            out_path=artifact_path,
            load=True,
        )
    _write_summary(os.path.join(out_dir, "_cjeu_treaty_counts.json"), summary)
    logging.info("CJEU treaty reference extraction complete: %s", summary)
    return summary


def run_extract_echr_text_echr(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.linking import echr_text_echr
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    artifact_path = os.path.join(out_dir, "echr_text_echr.jsonl")
    limit = int(os.environ.get("ECHR_TEXT_ECHR_LIMIT", "2000"))
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = echr_text_echr.extract_pending(
            conn,
            limit=limit,
            out_path=artifact_path,
            load=True,
        )
    _write_summary(os.path.join(out_dir, "_echr_text_echr_counts.json"), summary)
    logging.info("ECtHR empty-scl fulltext citation extraction complete: %s", summary)
    return summary


def run_extract_echr_treaties(**context):
    load_dotenv(find_dotenv(), override=True)
    from data_extraction.linking import echr_treaty
    from data_loading.clients.postgres import PostgresCLEClient

    out_dir = _out_dir(context)
    artifact_path = os.path.join(out_dir, "echr_text_treaty.jsonl")
    limit = int(os.environ.get("ECHR_TREATY_EXTRACT_LIMIT", "2000"))
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        summary = echr_treaty.extract_pending(
            conn,
            limit=limit,
            out_path=artifact_path,
            load=True,
        )
    _write_summary(os.path.join(out_dir, "_echr_treaty_counts.json"), summary)
    logging.info("ECtHR UN treaty reference extraction complete: %s", summary)
    return summary


def run_register_reconciliation_promotion(**context):
    tag = _run_tag(context)
    return register_promotion("enrichment_sync_etl", var_prefix=None, window_tag=tag, **context)


with dag:
    t_uuid = PythonOperator(
        task_id="refresh_cellar_uuid_cache",
        python_callable=run_refresh_cellar_uuid_cache,
    )
    t_leg = PythonOperator(
        task_id="sync_eu_legislation",
        python_callable=run_sync_eu_legislation,
    )
    t_appeals = PythonOperator(
        task_id="sync_cjeu_appeal_outcomes",
        python_callable=run_sync_cjeu_appeal_outcomes,
    )
    t_late = PythonOperator(
        task_id="resolve_late_citations",
        python_callable=run_resolve_late_citations,
    )
    t_law = PythonOperator(
        task_id="resolve_pending_law_refs",
        python_callable=run_resolve_pending_law_refs,
    )
    t_leg_fulltext = PythonOperator(
        task_id="enrich_legislation_fulltext",
        python_callable=run_enrich_legislation_fulltext,
    )
    t_judges = PythonOperator(
        task_id="extract_cross_court_judges",
        python_callable=run_extract_cross_court_judges,
    )
    t_cjeu_treaties = PythonOperator(
        task_id="extract_cjeu_treaties",
        python_callable=run_extract_cjeu_treaties,
    )
    t_echr_text_echr = PythonOperator(
        task_id="extract_echr_text_echr",
        python_callable=run_extract_echr_text_echr,
    )
    t_echr_treaties = PythonOperator(
        task_id="extract_echr_treaties",
        python_callable=run_extract_echr_treaties,
    )
    t_promote = PythonOperator(
        task_id="register_promotion",
        python_callable=run_register_reconciliation_promotion,
        trigger_rule="all_done",
    )
    [
        t_uuid, t_leg, t_appeals, t_late, t_law,
        t_leg_fulltext, t_judges, t_cjeu_treaties, t_echr_text_echr, t_echr_treaties,
    ] >> t_promote
