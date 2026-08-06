"""
Builds lido.db, a local SQLite metadata + citations + legislation database,
from the LIDO bulk export (data.overheid.nl) and the separate BWBIdList
export, via the rechtspraak-lido-sqlite package -- then merges the
legislation/case-law-link/alias tables into cle_v2 (cases/legislation/
legal_provision/legislation_alias/case_law_reference).

rechtspraak_extraction.py reads lido.db through rechtspraak_extractor's
fetch_eclis_via_sqlite()/get_rechtspraak_metadata(method="sqlite") instead of
hitting the live per-ECLI Rechtspraak metadata API and the live LIDO citations
API for every case -- issue #31 was HTTP 403s from doing exactly that at
volume, and case_law_reference/case_citation depended on the LIDO API call for
some of this data at all.

This DAG used to only build the case-metadata half of lido.db, with a
separate DAG (airflow/dags/lido/, dag_id lido_postgres) independently
downloading and parsing the same 12GB export into a second database (pg_lido)
for the legislation side, ending at legal_case/law_element/case_law/law_alias
-- tables that duplicated cases/legislation/legal_provision/case_law_reference/
legislation_alias, already in db/schema.sql, unused. That DAG is gone; its
role is now the merge_lido_db_into_cle task below, and rechtspraak-lido-sqlite
itself parses both case and law subjects in the same pass (see that package's
src/parse.py) instead of two independent downloads/parses of the same file.

Uses its own data directory (data/lido_sqlite/), kept from when a second DAG
shared the bind-mounted data/ tree and could otherwise race this one.
"""

from datetime import datetime

from airflow.operators.python import PythonOperator
from etl_factory import DEFAULT_ARGS
from lido.tasks.merge_into_cle import merge_lido_db_into_cle_v2
from lido_sqlite_paths import get_lido_sqlite_paths
from src.bwbidlist import build_law_aliases
from src.download import download
from src.parse import parse_into_db

from airflow import DAG

dag = DAG(
    dag_id="lido_sqlite_build",
    default_args=DEFAULT_ARGS,
    description="Build lido.db (metadata + citations + legislation) from the LIDO export, "
    "monthly, and merge legislation/case-law-links into cle_v2",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    schedule="0 0 8 * *",  # monthly, 8th at midnight UTC
)


def _download_lido_export():
    ttl_gz_path, _ = get_lido_sqlite_paths()
    download(ttl_gz_path)


def _build_lido_sqlite_db():
    ttl_gz_path, db_path = get_lido_sqlite_paths()
    parse_into_db(ttl_gz_path, db_path)


def _build_law_aliases():
    _, db_path = get_lido_sqlite_paths()
    bwb_zip_path = db_path.parent / "BWBIdList.xml.zip"
    build_law_aliases(db_path, bwb_zip_path)


def _merge_into_cle():
    _, db_path = get_lido_sqlite_paths()
    merge_lido_db_into_cle_v2(str(db_path))


with dag:
    download_task = PythonOperator(
        task_id="download_lido_export",
        python_callable=_download_lido_export,
    )
    build_task = PythonOperator(
        task_id="build_lido_sqlite_db",
        python_callable=_build_lido_sqlite_db,
    )
    build_aliases_task = PythonOperator(
        task_id="build_law_aliases",
        python_callable=_build_law_aliases,
    )
    merge_task = PythonOperator(
        task_id="merge_lido_db_into_cle",
        python_callable=_merge_into_cle,
    )
    download_task >> build_task >> build_aliases_task >> merge_task
