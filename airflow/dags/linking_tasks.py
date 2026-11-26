"""
Cross-dataset link extraction for the weekly ETL DAGs (cjeu-migration
docs/LINKING_DESIGN.md, "Data path"; roadmap R2.x "wired into the weekly DAG
behind a config flag").

Weekly runs
-----------
With LINK_EXTRACTION_ENABLED set, build_monthly_task_group (etl_factory.py)
adds an ``extract_links`` task after ``run_window`` in the monthly task group,
so ``register_promotion`` runs only after the links are written and loaded.
The task resolves the same window as ``run_window`` and, for every month
folder that ``run_window`` wrote (``processed/<chunk start>/``, skipping a
chunk with the source's no_source_data marker):

1. reads the natural keys of the month's processed CSV (RS ``ECLI``, Cellar
   ``celex``, ECHR ``document_id``) and maps them to ``cases.id`` in the
   target database (ECHR also through ``echr_document.item_id``, because
   HUDOC variants share one case row);
2. runs the source's extractors for those case ids:

       rechtspraak  rs_text
       echr         echr_text
       cellar       cjeu_text, cellar_referrals, ag_opinions, cellar_relations

   and writes ``processed/<month>/links/<source_dataset>.jsonl`` for every
   dataset the source owns (see artifact_paths), empty when an extractor found
   nothing or was switched off;
3. loads each file with data_loading.link_loader (insert-only, so a retry or
   a re-run is safe), then runs late binding (link_loader.resolve_late) for
   the month's cases when that function exists;
4. logs the counts per dataset and writes them to
   ``processed/<month>/links/_counts.<PREFIX>.json`` (the three DAGs share the
   processed month folder, so the name carries the source prefix, like the
   no_source_data marker).

case_identifier maintenance is not repeated here: the corpus loaders already
call identifier_loader.maintain_for_keys behind CASE_IDENTIFIER_ENABLED. This
module only records whether it was on, and warns when it is off (the
extractors resolve case numbers through case_identifier).

Flags (environment variables, '1'/'true'/'yes'/'on'):

    LINK_EXTRACTION_ENABLED   master switch, default off. Off: the task is not
                              added and the DAGs are exactly as before.
    LINK_RS_TEXT, LINK_ECHR_TEXT, LINK_CJEU_TEXT, LINK_CELLAR_REFERRALS,
    LINK_AG_OPINIONS, LINK_CELLAR_RELATIONS
                              per extractor, default on when the master is on.
    LINK_CELLAR_UUID_CACHE    JSON file {cellar URI: [dossier identifier]} for
                              cellar_relations. Unset or missing: that
                              extractor is skipped with a warning.
    LINK_CELLAR_UUID_CELEX_CACHE
                              optional JSON file {cellar URI: [CELEX]} for
                              cellar_relations (targets whose UUID names a
                              work rather than a dossier). Unset: not used;
                              set but missing: not used, with a warning.

Cited authorities (roadmap Phase 4) run the same way behind their own flag:

    AUTHORITY_EXTRACTION_ENABLED
                              default off. On: build_monthly_task_group adds
                              an ``extract_authorities`` task after
                              ``extract_law_references`` (or the last of
                              ``extract_legislation``, ``extract_links``,
                              ``run_window`` that is present). Off: nothing
                              is added.
    AUTHORITY_RS_TEXT, AUTHORITY_RS_PUBLICATION, AUTHORITY_ECHR_TEXT,
    AUTHORITY_CELLAR          per extractor, default on when the master is on.
    AUTHORITY_NL_OFFICIAL_PUBLICATIONS
                              content switch of authority_text, default on.
    AUTHORITY_NL_DECREES      content switch of authority_text, default off:
                              decrees cited by date and reference number
                              ("besluit van ..., nr. DGB 2014/296M"); the
                              pattern also takes individual decisions.
    AUTHORITY_CELLAR_DECISIONS
                              sector 3 decisions as authority documents,
                              default off (R3.2 records them as legislation).

       rechtspraak  rs_text_authority (authority_text), rs_publication
       echr         echr_text_authority (authority_text)
       cellar       cellar_authority

    Files: ``processed/<month>/authorities/<source_dataset>.jsonl`` (every one
    written, empty when nothing was found or the extractor is off; see
    authority_artifact_paths) and ``_counts.<PREFIX>.json`` next to them,
    loaded with data_loading.authority_loader. Backfill:
    ``python -m linking_tasks backfill-authorities --dsn-env VAR --source S
    --from-id N --to-id M --out DIR [--load]``.

The DAG never queries Cellar SPARQL. Both caches are refreshed outside it, by
hand or by a separate scheduled job (not part of this change), with

    python -m data_extraction.linking.cellar_relations --dsn-env VAR \\
        --refresh-uuid-cache --uuid-dossier $LINK_CELLAR_UUID_CACHE \\
        [--uuid-celex $LINK_CELLAR_UUID_CELEX_CACHE]

which asks Cellar only for the UUIDs of unresolved cellar_sparql rows that
the files lack. Rows whose UUID is not in the cache yet are skipped and
counted (``uuid_unmapped``) until a refresh adds it and a later run selects
the row again.

Not covered: Rechtspraak's modified-date sweep
-----------------------------------------------
rechtspraak_etl also loads ``processed/modified/<date>/RS_cases_clean.csv``
(old judgments published or corrected retroactively; RS_MODIFIED_LOOKBACK_DAYS)
on the final chunk of a forced run. Links are NOT extracted for those cases
here, on purpose: the promoter (caselaw-coolify etl/promoter.py artifacts_for)
replays only ``processed/<month>/...``, never ``processed/modified/...``, so
neither those corpus rows nor link files written next to them would reach
production, and links loaded into db-dev alone would make db-dev and
production differ in a way assert_promoted cannot see. Until the promoter
replays the modified sweep, those cases get their links from the backfill
(below) or from a later weekly run that names them (rs_text, like every
extractor, reads the texts from the database, so it sees the corrected body
whenever it next runs for that case). Doing it properly needs the promoter to
register ``processed/modified/<date>/`` (corpus CSV and
``links/<source_dataset>.jsonl``) first; then this module can write the same
layout there.

Legislation outside the BWB register (roadmap R3.1, R3.7)
---------------------------------------------------------
With LEGISLATION_EXTERNAL_ENABLED set (default off, independent of
LINK_EXTRACTION_ENABLED), build_monthly_task_group adds an
``extract_legislation`` task after ``run_window`` (after ``extract_links`` when
that is on too). For every month folder it writes and loads:

    cellar  processed/<month>/links/legislation_external.jsonl   role 'legislation'
            (data_extraction.legislation.catalog: the curated acts and the
            CELEX acts of sectors 1-4 and the base acts of consolidated
            texts the month's cases refer to; loaded by
            legislation_loader.load_acts_artifact)
    echr    processed/<month>/law_references/echr_article.jsonl  role 'law_references'
            (data_extraction.legislation.echr_articles: echr_document_article
            -> ECHR provisions; loaded by
            legislation_loader.load_law_reference_artifact, which
            law_reference_loader.load_artifact calls for echr_article files,
            so the promoter can replay every 'law_references' file, this one
            and those of R3.2-R3.4 below, through law_reference_loader)

and ``processed/<month>/links/_legislation_counts.<PREFIX>.json``. Rechtspraak
has no file here: its R3.5 change is in the corpus loader
(row_processors/postgres.py) behind its own flag RS_RESOLVE_BWB_ENABLED,
default off; off, the loader writes exactly the rows it wrote before R3.5.
On, an rs_lido_sqlite row gets legislation_id only when exactly one
legislation row has scheme 'bwb' and that identifier (a database holding
version rows per BWB id leaves those references unresolved). The promoter must
replay the legislation file before the law-reference file of the same month
(the law-reference loader inserts a missing curated act itself, so the order
matters only for titles of CELEX acts, which have none). Backfill:

    python -m linking_tasks legislation-backfill --dsn-env CLE_DSN --source echr \
        --from-id 1 --to-id 500000 --out /data/legislation/echr-1-500000 [--load]

Deployment
----------
The link artifacts, the link loader and row_processors (rs_lido_sqlite
citations, is_cross_jurisdiction) run in Airflow and, on replay, in the
etl-promoter. Deploy both from the same ref, or a replay into production can
load an artifact with code that reads it differently.

Law references (roadmap R3.2-R3.4)
----------------------------------
With LAW_REFERENCE_EXTRACTION_ENABLED set (default off, independent of
LINK_EXTRACTION_ENABLED), build_monthly_task_group adds an
``extract_law_references`` task after ``run_window`` (after
``extract_links`` and ``extract_legislation`` when those are on too). For
every month folder it runs the source's
law-reference extractor for the month's cases:

    rechtspraak  rs_eu_law        rs_text_eu_law
    echr         echr_eu_law      echr_text_eu_law
    cellar       cellar_law_refs  cellar_law_ref

writes ``processed/<month>/law_references/<source_dataset>.jsonl`` (empty when
nothing was found or the extractor is off; see law_artifact_paths, the list
the promoter registers with role 'law_references'), loads it with
data_loading.law_reference_loader into case_law_reference (insert-only) and
writes the counts to ``processed/<month>/law_references/_counts.<PREFIX>.json``.
The ECHR month folder's law_references/ also holds echr_article.jsonl, written
by ``extract_legislation`` (above; its counts stay in links/), so every file of
role 'law_references' lives in law_references/.
Per-extractor flags LAW_RS_TEXT, LAW_ECHR_TEXT, LAW_CELLAR_REFS default on
when the master is on. The same flag makes cjeu_loader resolve legislation_id
on the Cellar CDM law references it inserts (see cjeu_loader
SQL_LAWREF_RESOLVED), so it must be set alike in Airflow and in the
etl-promoter, which replays cjeu_loader.

Backfill: ``python -m linking_tasks backfill-law --dsn-env VAR --source
rechtspraak --from-id N --to-id M --out DIR [--load]`` (read-only without
--load), or each extractor's own CLI (``python -m
data_extraction.linking.rs_eu_law --dsn-env VAR --from-id N --to-id M --out
FILE [--load]``).

Backfill (cjeu-migration)
-------------------------
History is not extracted through the DAG or the promoter. cjeu-migration runs
the same extract + load against db-dev over ``cases.id`` ranges, either per
extractor with the module CLIs, e.g.

    cd airflow/dags
    python -m data_extraction.linking.rs_text --dsn-env CLE_DSN \\
        --from-id 1 --to-id 500000 --out /data/links/rs_text.jsonl
    python -m data_extraction.linking.cellar_relations --dsn-env CLE_DSN \\
        --from-id 1 --to-id 500000 --uuid-dossier uuid_dossier.json \\
        --out /data/links/cellar_relation_resolved.jsonl

followed by link_loader.load_artifact for each file, or per source with this
module, which writes the same per-dataset files and counts as a weekly run:

    python -m linking_tasks backfill --dsn-env CLE_DSN --source cellar \\
        --from-id 1 --to-id 500000 --out /data/links/cellar-1-500000 [--load]

Without --load the connection is read-only and only the files and
``_counts.<PREFIX>.json`` are written, so the files can be checked and hashed
before loading (into db-dev, and later the same hashed files into
production). The per-extractor flags and LINK_CELLAR_UUID_CACHE apply; the
master flag does not. Backfill does not run late binding (R2.9 has its own
range run).
"""

import argparse
import csv
import importlib
import inspect
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
MASTER_FLAG = "LINK_EXTRACTION_ENABLED"
LEGISLATION_FLAG = "LEGISLATION_EXTERNAL_ENABLED"
LEGISLATION_COUNTS_FILE = "_legislation_counts.{}.json"
CELLAR_UUID_CACHE_ENV = "LINK_CELLAR_UUID_CACHE"
CELLAR_UUID_CELEX_CACHE_ENV = "LINK_CELLAR_UUID_CELEX_CACHE"
LINKS_DIR = "links"
LAW_DIR = "law_references"
COUNTS_FILE = "_counts.{}.json"
# Same name as etl_factory.NO_SOURCE_DATA_MARKER (not imported: etl_factory
# imports Airflow, and the backfill CLI must run without it).
NO_SOURCE_DATA_MARKER = "no_source_data.{}.marker"

_TRUE = ("1", "true", "yes", "on")


def env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in _TRUE


def enabled() -> bool:
    """LINK_EXTRACTION_ENABLED is set to a true value (default off)."""
    return env_flag(MASTER_FLAG, False)


def legislation_enabled() -> bool:
    """LEGISLATION_EXTERNAL_ENABLED is set to a true value (default off)."""
    return env_flag(LEGISLATION_FLAG, False)


# rs_text ECLI scope. Weekly runs scan new cases, which since the July 2026
# migration have no rs_body_cite rows, so every ECLI is extracted; the
# historical backfill extracts cross-court ECLIs only (Dutch-to-Dutch ones are
# already in rs_body_cite / rs_lido_sqlite).
WEEKLY_ECLI_SCOPE = "all"
BACKFILL_ECLI_SCOPE = "cross"


@dataclass(frozen=True)
class Extractor:
    name: str
    flag: str
    datasets: Tuple[str, ...]

    @property
    def module(self):
        return f"data_extraction.linking.{self.name}"


# Dataset names are spelled out (and checked against the modules in the
# tests) so the DAG files and the promoter's path list need no extractor
# imports.
EXTRACTORS: Dict[str, Extractor] = {
    e.name: e
    for e in (
        Extractor(
            "rs_text",
            "LINK_RS_TEXT",
            ("rs_text_ecli", "rs_text_cjeu_casenum", "rs_text_echr_appno"),
        ),
        Extractor("echr_text", "LINK_ECHR_TEXT", ("echr_text_cjeu", "echr_text_rs")),
        Extractor("echr_edge_v2", "LINK_ECHR_EDGE_V2", ("echr_edge_v2",)),
        Extractor("cjeu_text", "LINK_CJEU_TEXT", ("cjeu_text_echr",)),
        Extractor("cellar_referrals", "LINK_CELLAR_REFERRALS", ("cellar_national_judgement",)),
        Extractor("ag_opinions", "LINK_AG_OPINIONS", ("cjeu_ag_link",)),
        Extractor("cellar_relations", "LINK_CELLAR_RELATIONS", ("cellar_relation_resolved",)),
    )
}


@dataclass(frozen=True)
class Source:
    name: str
    prefix: str  # the DAG's var_prefix
    dag_id: str
    processed_csv: str  # in processed/<month>/
    key_column: str  # natural key column of processed_csv
    case_column: str  # cases column holding that key
    extractors: Tuple[str, ...]

    @property
    def datasets(self) -> List[str]:
        return [d for name in self.extractors for d in EXTRACTORS[name].datasets]


SOURCES: Dict[str, Source] = {
    s.name: s
    for s in (
        Source(
            "rechtspraak",
            "RS",
            "rechtspraak_etl",
            "RS_cases_clean.csv",
            "ECLI",
            "ecli",
            ("rs_text",),
        ),
        Source(
            "echr",
            "ECHR",
            "echr_etl",
            "ECHR_metadata_clean.csv",
            "document_id",
            "item_id",
            ("echr_text", "echr_edge_v2"),
        ),
        Source(
            "cellar",
            "CELLAR",
            "cellar_etl",
            "cellar_csv_data_clean.csv",
            "celex",
            "celex_id",
            ("cjeu_text", "cellar_referrals", "ag_opinions", "cellar_relations"),
        ),
    )
}
SOURCE_BY_PREFIX: Dict[str, Source] = {s.prefix: s for s in SOURCES.values()}

# Law references (R3.2-R3.4): own master flag, own artifact folder and loader.
LAW_MASTER_FLAG = "LAW_REFERENCE_EXTRACTION_ENABLED"  # = law_reference_loader.FLAG
LAW_EXTRACTORS: Dict[str, Extractor] = {
    "rechtspraak": Extractor("rs_eu_law", "LAW_RS_TEXT", ("rs_text_eu_law",)),
    "echr": Extractor("echr_eu_law", "LAW_ECHR_TEXT", ("echr_text_eu_law",)),
    "cellar": Extractor("cellar_law_refs", "LAW_CELLAR_REFS", ("cellar_law_ref",)),
}


def law_enabled() -> bool:
    """LAW_REFERENCE_EXTRACTION_ENABLED is set to a true value (default off)."""
    return env_flag(LAW_MASTER_FLAG, False)


def law_artifact_paths(source: Source, month_folder: str) -> List[str]:
    """Paths (relative to DATA_PATH) of the law-reference files a weekly run
    writes for one month; every one exists after the task, possibly empty.
    The promoter registers these with role 'law_references' and replays them
    with data_loading.law_reference_loader."""
    extractor = LAW_EXTRACTORS[source.name]
    return [f"processed/{month_folder}/{LAW_DIR}/{d}.jsonl" for d in extractor.datasets]


def artifact_paths(source: Source, month_folder: str) -> List[str]:
    """Paths (relative to DATA_PATH) of the link files a weekly run writes for
    one month, in load order. Every one exists after the task, possibly empty;
    this is the list the promoter registers with role 'links'."""
    return [f"processed/{month_folder}/{LINKS_DIR}/{d}.jsonl" for d in source.datasets]


def counts_path(source: Source, month_folder: str) -> str:
    return f"processed/{month_folder}/{LINKS_DIR}/{COUNTS_FILE.format(source.prefix)}"


# ---------------------------------------------------------------------------
# case ids of a month
# ---------------------------------------------------------------------------


def read_processed_keys(path, key_column) -> List[str]:
    """Distinct non-blank natural keys of a processed CSV."""
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with open(path, newline="", encoding="utf8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is not None and key_column not in reader.fieldnames:
            raise ValueError(f"{path} has no {key_column!r} column")
        return sorted({(row.get(key_column) or "").strip() for row in reader} - {""})


def case_ids_for_keys(conn, source: Source, keys: Sequence[str]) -> List[int]:
    """cases.id for the natural keys of source in this database."""
    if not keys:
        return []
    keys = list(keys)
    with conn.cursor() as cursor:
        if source.case_column == "item_id":
            cursor.execute(
                f"""
                SELECT id FROM {SCHEMA}.cases WHERE item_id = ANY(%s)
                UNION
                SELECT case_id FROM {SCHEMA}.echr_document
                 WHERE item_id = ANY(%s) AND case_id IS NOT NULL
                """,
                (keys, keys),
            )
        else:
            cursor.execute(
                f"SELECT id FROM {SCHEMA}.cases WHERE {source.case_column} = ANY(%s)", (keys,)
            )
        ids = sorted({row[0] for row in cursor.fetchall()})
    conn.rollback()  # read only; do not hold the snapshot open during extraction
    return ids


# ---------------------------------------------------------------------------
# extract, load
# ---------------------------------------------------------------------------


def extractor_plan(source: Source) -> List[Tuple[Extractor, Optional[str]]]:
    """(extractor, reason it is skipped or None) for every extractor of source."""
    plan = []
    for name in source.extractors:
        extractor = EXTRACTORS[name]
        reason = None
        if not env_flag(extractor.flag, True):
            reason = f"{extractor.flag} is off"
        elif name == "cellar_relations":
            cache = os.environ.get(CELLAR_UUID_CACHE_ENV, "").strip()
            if not cache:
                reason = f"{CELLAR_UUID_CACHE_ENV} is not set"
            elif not os.path.isfile(cache):
                reason = f"{CELLAR_UUID_CACHE_ENV} file {cache} does not exist"
        if reason:
            log.warning("links: skipping %s (%s)", name, reason)
        plan.append((extractor, reason))
    return plan


def _uuid_celex_cache() -> Optional[str]:
    """LINK_CELLAR_UUID_CELEX_CACHE when set and present, else None."""
    path = os.environ.get(CELLAR_UUID_CELEX_CACHE_ENV, "").strip()
    if not path:
        return None
    if not os.path.isfile(path):
        log.warning(
            "links: %s file %s does not exist; cellar_relations runs without it",
            CELLAR_UUID_CELEX_CACHE_ENV,
            path,
        )
        return None
    return path


def _run_extractor(
    conn, extractor: Extractor, out_path, case_ids=None, id_range=None, ecli_scope=None
):
    module = importlib.import_module(extractor.module)
    kwargs = {"case_ids": case_ids, "id_range": id_range, "out_path": out_path}
    if extractor.name == "rs_text":
        kwargs["ecli_scope"] = ecli_scope or WEEKLY_ECLI_SCOPE
    if extractor.name == "cellar_relations":
        kwargs["uuid_dossier"] = module.load_uuid_map(os.environ[CELLAR_UUID_CACHE_ENV].strip())
        kwargs["uuid_celex"] = module.load_uuid_map(_uuid_celex_cache())
    module.extract(conn, **kwargs)


def _split(raw_path, writers) -> None:
    """Stream the extractor's file into the per-dataset files, record by
    record: each file keeps the extractor's (deterministic) order."""
    from data_extraction.linking.artifact import read_jsonl

    for record in read_jsonl(raw_path):
        writers.write([record])


def extract_links(
    conn, source: Source, out_dir, case_ids=None, id_range=None, ecli_scope=None
) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """Run source's extractors and write out_dir/<source_dataset>.jsonl for
    every dataset of source (empty when skipped or nothing was found).

    case_ids (a list, possibly empty) or id_range selects the source cases.
    Returns ({extractor: status}, {dataset: {"records": n}}). Nothing is
    held in memory beyond one extractor batch: the extractor streams its file
    and it is split record by record. Each dataset file appears complete
    (written to .tmp, then renamed) or not at all.
    """
    from data_extraction.linking.artifact import ArtifactError, DatasetWriters

    os.makedirs(out_dir, exist_ok=True)
    tmp_dir = os.path.join(out_dir, f".tmp-{source.prefix}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    os.makedirs(tmp_dir)
    statuses, datasets = {}, {}
    try:
        for extractor, reason in extractor_plan(source):
            paths = {d: os.path.join(out_dir, f"{d}.jsonl") for d in extractor.datasets}
            with DatasetWriters(paths) as writers:
                if reason:
                    statuses[extractor.name] = {"status": "skipped", "reason": reason}
                elif case_ids is not None and not case_ids:
                    statuses[extractor.name] = {"status": "no_cases"}
                else:
                    raw = os.path.join(tmp_dir, f"{extractor.name}.jsonl")
                    _run_extractor(
                        conn,
                        extractor,
                        raw,
                        case_ids=case_ids,
                        id_range=id_range,
                        ecli_scope=ecli_scope,
                    )
                    try:
                        _split(raw, writers)
                    except ArtifactError as exc:
                        raise ValueError(f"{extractor.name}: {exc}") from None
                    os.remove(raw)
                    statuses[extractor.name] = {"status": "ran"}
            for dataset, count in writers.counts.items():
                datasets[dataset] = {"records": count}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return statuses, datasets


def load_links(conn, source: Source, out_dir) -> Dict[str, dict]:
    """Load every dataset file of source from out_dir; {dataset: counts}."""
    from data_loading import link_loader

    loaded = {}
    for dataset in source.datasets:
        result = link_loader.load_artifact(conn, os.path.join(out_dir, f"{dataset}.jsonl"))
        loaded[dataset] = result.get(dataset, {})
    return loaded


def late_bind(conn, case_ids):
    """link_loader.resolve_late for the newly loaded cases, if it exists yet
    (feature/linking-late-binding). Returns its result, or None when absent."""
    from data_loading import link_loader

    resolve_late = getattr(link_loader, "resolve_late", None)
    if resolve_late is None:
        log.info("links: link_loader.resolve_late is not available; no late binding")
        return None
    try:
        accepts_ids = "case_ids" in inspect.signature(resolve_late).parameters
    except (TypeError, ValueError):
        accepts_ids = False
    result = resolve_late(conn, case_ids=list(case_ids)) if accepts_ids else resolve_late(conn)
    log.info("links: late binding %s", result)
    return result


def _identifier_maintenance_enabled() -> bool:
    from data_loading import identifier_loader

    return identifier_loader.enabled()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _write_counts(path, counts):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(_json_safe(counts), handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def _log_counts(label, counts):
    for dataset, values in counts["datasets"].items():
        log.info(
            "links %s %s: %s records, load %s",
            label,
            dataset,
            values["records"],
            values.get("load", "not loaded"),
        )


def run_month(conn, source: Source, data_path, month_folder) -> Optional[dict]:
    """Extract and load the links of one month's batch. Returns the counts, or
    None when the chunk is marked as having no source data."""
    processed_dir = os.path.join(data_path, "processed", month_folder)
    if os.path.exists(os.path.join(processed_dir, NO_SOURCE_DATA_MARKER.format(source.prefix))):
        log.info("links: %s %s has no source data; nothing to extract", source.name, month_folder)
        return None
    csv_path = os.path.join(processed_dir, source.processed_csv)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"processed artifact missing for link extraction: {csv_path}")
    identifier_maintenance = _identifier_maintenance_enabled()
    if not identifier_maintenance:
        log.warning(
            "links: CASE_IDENTIFIER_ENABLED is off; references to this batch's cases by "
            "case number will not resolve until case_identifier is filled"
        )
    keys = read_processed_keys(csv_path, source.key_column)
    case_ids = case_ids_for_keys(conn, source, keys)
    if len(case_ids) < len(keys) and source.case_column != "item_id":
        log.warning(
            "links: %s of %s %s keys of %s are not in the database",
            len(keys) - len(case_ids),
            len(keys),
            source.key_column,
            month_folder,
        )
    out_dir = os.path.join(processed_dir, LINKS_DIR)
    statuses, datasets = extract_links(conn, source, out_dir, case_ids=case_ids)
    for dataset, load in load_links(conn, source, out_dir).items():
        datasets[dataset]["load"] = load
    late = late_bind(conn, case_ids) if case_ids else None
    counts = {
        "source": source.name,
        "month": month_folder,
        "case_keys": len(keys),
        "case_ids": len(case_ids),
        "case_identifier_enabled": identifier_maintenance,
        "extractors": statuses,
        "datasets": datasets,
        "late_binding": late,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"{source.name} {month_folder}", counts)
    return counts


def run_window_links(var_prefix, **context):
    """Airflow callable: links for every month chunk of the run's window.

    A no-op unless LINK_EXTRACTION_ENABLED (the task is not even added when
    the flag is off at parse time; this guards a flag switched off since).
    """
    if not enabled():
        log.info("links: %s is off; nothing to do", MASTER_FLAG)
        return None
    from data_loading.clients.postgres import PostgresCLEClient
    from etl_factory import get_data_path, iter_month_chunks, resolve_run_window

    source = SOURCE_BY_PREFIX[var_prefix]
    start, end, _ = resolve_run_window(var_prefix, context)
    data_path = get_data_path()
    summary = {}
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        for chunk_start, _chunk_end in iter_month_chunks(start, end):
            folder = chunk_start.isoformat()
            counts = run_month(conn, source, data_path, folder)
            summary[folder] = (
                None if counts is None else {d: v["records"] for d, v in counts["datasets"].items()}
            )
    return summary


# ---------------------------------------------------------------------------
# legislation outside the BWB register (R3.1, R3.7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegislationOutput:
    name: str  # file stem
    role: str  # promoter role
    extractor: str  # module in data_extraction.legislation
    loader: str  # function in data_loading.legislation_loader
    folder: str = LINKS_DIR  # under processed/<month>/: next to the files of its role


LEGISLATION_OUTPUTS: Dict[str, Tuple[LegislationOutput, ...]] = {
    "rechtspraak": (),
    "cellar": (
        LegislationOutput("legislation_external", "legislation", "catalog", "load_acts_artifact"),
    ),
    "echr": (
        LegislationOutput(
            "echr_article",
            "law_references",
            "echr_articles",
            "load_law_reference_artifact",
            LAW_DIR,
        ),
    ),
}


def has_legislation(var_prefix: str) -> bool:
    """Does the DAG with this prefix write legislation files?"""
    source = SOURCE_BY_PREFIX.get(var_prefix)
    return bool(source and LEGISLATION_OUTPUTS.get(source.name))


def legislation_artifact_paths(source: Source, month_folder: str) -> List[Tuple[str, str]]:
    """(path relative to DATA_PATH, role) of the legislation files a weekly run
    writes for one month, in load order; every one exists after the task,
    possibly empty. What the promoter must replay."""
    return [
        (f"processed/{month_folder}/{o.folder}/{o.name}.jsonl", o.role)
        for o in LEGISLATION_OUTPUTS[source.name]
    ]


def _legislation_path(out_dir, output: LegislationOutput, month_layout: bool) -> str:
    """out_dir/<folder>/<name>.jsonl for a month folder (month_layout), else
    out_dir/<name>.jsonl (a backfill's --out directory)."""
    folder = os.path.join(out_dir, output.folder) if month_layout else out_dir
    return os.path.join(folder, f"{output.name}.jsonl")


def extract_legislation(
    conn, source: Source, out_dir, case_ids=None, id_range=None, month_layout=False
) -> dict:
    """Write <name>.jsonl for every legislation output of source, in out_dir
    or, with month_layout (out_dir a processed month folder), in each output's
    folder under it; {name: stats}. Each extractor writes .tmp and renames, so
    a file is complete or absent."""
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    for output in LEGISLATION_OUTPUTS[source.name]:
        module = importlib.import_module(f"data_extraction.legislation.{output.extractor}")
        path = _legislation_path(out_dir, output, month_layout)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        written, stats = module.extract(conn, case_ids=case_ids, id_range=id_range, out_path=path)
        results[output.name] = {"records": written, "stats": dict(stats)}
    return results


def load_legislation(conn, source: Source, out_dir, month_layout=False) -> Dict[str, dict]:
    from data_loading import legislation_loader

    loaded = {}
    for output in LEGISLATION_OUTPUTS[source.name]:
        load = getattr(legislation_loader, output.loader)
        loaded[output.name] = load(conn, _legislation_path(out_dir, output, month_layout))
    return loaded


def run_legislation_month(conn, source: Source, data_path, month_folder) -> Optional[dict]:
    """Extract and load the legislation files of one month. None when the
    chunk has no source data or the source writes no legislation files."""
    if not LEGISLATION_OUTPUTS.get(source.name):
        return None
    processed_dir = os.path.join(data_path, "processed", month_folder)
    if os.path.exists(os.path.join(processed_dir, NO_SOURCE_DATA_MARKER.format(source.prefix))):
        log.info("legislation: %s %s has no source data", source.name, month_folder)
        return None
    csv_path = os.path.join(processed_dir, source.processed_csv)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"processed artifact missing for legislation: {csv_path}")
    keys = read_processed_keys(csv_path, source.key_column)
    case_ids = case_ids_for_keys(conn, source, keys)
    outputs = extract_legislation(conn, source, processed_dir, case_ids=case_ids, month_layout=True)
    for name, load in load_legislation(conn, source, processed_dir, month_layout=True).items():
        outputs[name]["load"] = load
    counts = {
        "source": source.name,
        "month": month_folder,
        "case_keys": len(keys),
        "case_ids": len(case_ids),
        "outputs": outputs,
    }
    counts_dir = os.path.join(processed_dir, LINKS_DIR)
    os.makedirs(counts_dir, exist_ok=True)
    _write_counts(os.path.join(counts_dir, LEGISLATION_COUNTS_FILE.format(source.prefix)), counts)
    for name, values in outputs.items():
        log.info(
            "legislation %s %s %s: %s records, load %s",
            source.name,
            month_folder,
            name,
            values["records"],
            values.get("load"),
        )
    return counts


def run_window_legislation(var_prefix, **context):
    """Airflow callable: legislation files for every month chunk of the run's
    window. A no-op unless LEGISLATION_EXTERNAL_ENABLED."""
    if not legislation_enabled():
        log.info("legislation: %s is off; nothing to do", LEGISLATION_FLAG)
        return None
    from data_loading.clients.postgres import PostgresCLEClient
    from etl_factory import get_data_path, iter_month_chunks, resolve_run_window

    source = SOURCE_BY_PREFIX[var_prefix]
    start, end, _ = resolve_run_window(var_prefix, context)
    data_path = get_data_path()
    summary = {}
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        for chunk_start, _chunk_end in iter_month_chunks(start, end):
            folder = chunk_start.isoformat()
            counts = run_legislation_month(conn, source, data_path, folder)
            summary[folder] = (
                None if counts is None else {n: v["records"] for n, v in counts["outputs"].items()}
            )
    return summary


def legislation_backfill(conn, source: Source, from_id, to_id, out_dir, load=False) -> dict:
    """Extract (and optionally load) source's legislation files over cases.id
    from_id..to_id (inclusive, either may be None) into out_dir."""
    outputs = extract_legislation(conn, source, out_dir, id_range=(from_id, to_id))
    if load:
        for name, result in load_legislation(conn, source, out_dir).items():
            outputs[name]["load"] = result
    counts = {"source": source.name, "from_id": from_id, "to_id": to_id, "outputs": outputs}
    _write_counts(os.path.join(out_dir, LEGISLATION_COUNTS_FILE.format(source.prefix)), counts)
    return counts


# ---------------------------------------------------------------------------
# law references (R3.2-R3.4)
# ---------------------------------------------------------------------------


def extract_law_references(conn, source: Source, out_dir, case_ids=None, id_range=None):
    """Run source's law-reference extractor into out_dir/<dataset>.jsonl
    (written empty when the extractor is off or there are no cases).
    Returns (status, {dataset: {"records": n}})."""
    extractor = LAW_EXTRACTORS[source.name]
    os.makedirs(out_dir, exist_ok=True)
    (dataset,) = extractor.datasets
    path = os.path.join(out_dir, f"{dataset}.jsonl")
    if not env_flag(extractor.flag, True):
        log.warning("law references: skipping %s (%s is off)", extractor.name, extractor.flag)
        status, result = {"status": "skipped", "reason": f"{extractor.flag} is off"}, None
    elif case_ids is not None and not case_ids:
        status, result = {"status": "no_cases"}, None
    else:
        module = importlib.import_module(extractor.module)
        result = module.extract(conn, case_ids=case_ids, id_range=id_range, out_path=path)
        status = {"status": "ran", "extract": result}
    if result is None:
        from data_extraction.linking.artifact import ArtifactWriter

        with ArtifactWriter(path):
            pass
    return status, {dataset: {"records": (result or {}).get("records", 0)}}


def load_law_references(conn, source: Source, out_dir) -> Dict[str, dict]:
    from data_loading import law_reference_loader

    loaded = {}
    for dataset in LAW_EXTRACTORS[source.name].datasets:
        result = law_reference_loader.load_artifact(conn, os.path.join(out_dir, f"{dataset}.jsonl"))
        loaded[dataset] = result.get(dataset, {})
    return loaded


def run_month_law(conn, source: Source, data_path, month_folder) -> Optional[dict]:
    """Extract and load the law references of one month's batch; None when the
    chunk is marked as having no source data."""
    processed_dir = os.path.join(data_path, "processed", month_folder)
    if os.path.exists(os.path.join(processed_dir, NO_SOURCE_DATA_MARKER.format(source.prefix))):
        log.info("law references: %s %s has no source data", source.name, month_folder)
        return None
    csv_path = os.path.join(processed_dir, source.processed_csv)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"processed artifact missing for law references: {csv_path}")
    keys = read_processed_keys(csv_path, source.key_column)
    case_ids = case_ids_for_keys(conn, source, keys)
    out_dir = os.path.join(processed_dir, LAW_DIR)
    status, datasets = extract_law_references(conn, source, out_dir, case_ids=case_ids)
    for dataset, load in load_law_references(conn, source, out_dir).items():
        datasets[dataset]["load"] = load
    counts = {
        "source": source.name,
        "month": month_folder,
        "case_keys": len(keys),
        "case_ids": len(case_ids),
        "extractor": status,
        "datasets": datasets,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"law references {source.name} {month_folder}", counts)
    return counts


def run_window_law_references(var_prefix, **context):
    """Airflow callable: law references for every month chunk of the run's
    window. A no-op unless LAW_REFERENCE_EXTRACTION_ENABLED."""
    if not law_enabled():
        log.info("law references: %s is off; nothing to do", LAW_MASTER_FLAG)
        return None
    from data_loading.clients.postgres import PostgresCLEClient
    from etl_factory import get_data_path, iter_month_chunks, resolve_run_window

    source = SOURCE_BY_PREFIX[var_prefix]
    start, end, _ = resolve_run_window(var_prefix, context)
    data_path = get_data_path()
    summary = {}
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        for chunk_start, _chunk_end in iter_month_chunks(start, end):
            folder = chunk_start.isoformat()
            counts = run_month_law(conn, source, data_path, folder)
            summary[folder] = (
                None if counts is None else {d: v["records"] for d, v in counts["datasets"].items()}
            )
    return summary


def backfill_law(conn, source: Source, from_id, to_id, out_dir, load=False) -> dict:
    """Extract (and optionally load) the law references of source over
    cases.id from_id..to_id (inclusive, either may be None) into out_dir."""
    status, datasets = extract_law_references(conn, source, out_dir, id_range=(from_id, to_id))
    if load:
        for dataset, result in load_law_references(conn, source, out_dir).items():
            datasets[dataset]["load"] = result
    counts = {
        "source": source.name,
        "from_id": from_id,
        "to_id": to_id,
        "extractor": status,
        "datasets": datasets,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"law references {source.name} {from_id}..{to_id}", counts)
    return counts


# ---------------------------------------------------------------------------
# cited authorities (roadmap Phase 4)
# ---------------------------------------------------------------------------

AUTHORITY_FLAG = "AUTHORITY_EXTRACTION_ENABLED"
AUTHORITIES_DIR = "authorities"


def authority_enabled() -> bool:
    """AUTHORITY_EXTRACTION_ENABLED is set to a true value (default off)."""
    return env_flag(AUTHORITY_FLAG, False)


@dataclass(frozen=True)
class AuthorityExtractor:
    dataset: str  # the one source_dataset it writes
    module_name: str
    flag: str
    options: Tuple[Tuple[str, str], ...] = ()  # extra keyword arguments of extract()

    @property
    def module(self):
        return f"data_extraction.linking.{self.module_name}"


AUTHORITY_EXTRACTORS: Dict[str, AuthorityExtractor] = {
    e.dataset: e
    for e in (
        AuthorityExtractor(
            "rs_text_authority", "authority_text", "AUTHORITY_RS_TEXT", (("corpus", "rs"),)
        ),
        AuthorityExtractor("rs_publication", "rs_publication", "AUTHORITY_RS_PUBLICATION"),
        AuthorityExtractor(
            "echr_text_authority", "authority_text", "AUTHORITY_ECHR_TEXT", (("corpus", "echr"),)
        ),
        AuthorityExtractor("cellar_authority", "cellar_authority", "AUTHORITY_CELLAR"),
    )
}
# Per source, in load order.
AUTHORITY_SOURCES: Dict[str, Tuple[str, ...]] = {
    "rechtspraak": ("rs_text_authority", "rs_publication"),
    "echr": ("echr_text_authority",),
    "cellar": ("cellar_authority",),
}


def authority_artifact_paths(source: Source, month_folder: str) -> List[str]:
    """Paths (relative to DATA_PATH) of the authority files a weekly run writes
    for one month, in load order; every one exists after the task, possibly
    empty. The promoter registers these with role 'authorities' and replays
    them with data_loading.authority_loader."""
    return [
        f"processed/{month_folder}/{AUTHORITIES_DIR}/{d}.jsonl"
        for d in AUTHORITY_SOURCES[source.name]
    ]


def authority_counts_path(source: Source, month_folder: str) -> str:
    return f"processed/{month_folder}/{AUTHORITIES_DIR}/{COUNTS_FILE.format(source.prefix)}"


def extract_authorities(conn, source: Source, out_dir, case_ids=None, id_range=None):
    """Run source's authority extractors; writes out_dir/<dataset>.jsonl for
    every dataset of source (empty when switched off or no cases). Returns
    ({dataset: status}, {dataset: {"records": n}})."""
    from data_extraction.linking.authority_artifact import AuthorityWriter

    os.makedirs(out_dir, exist_ok=True)
    statuses, datasets = {}, {}
    for dataset in AUTHORITY_SOURCES[source.name]:
        extractor = AUTHORITY_EXTRACTORS[dataset]
        path = os.path.join(out_dir, f"{dataset}.jsonl")
        if not env_flag(extractor.flag, True):
            log.warning("authorities: skipping %s (%s is off)", dataset, extractor.flag)
            statuses[dataset] = {"status": "skipped", "reason": f"{extractor.flag} is off"}
        elif case_ids is not None and not case_ids:
            statuses[dataset] = {"status": "no_cases"}
        else:
            module = importlib.import_module(extractor.module)
            written, _stats = module.extract(
                conn,
                case_ids=case_ids,
                id_range=id_range,
                out_path=path,
                **dict(extractor.options),
            )
            statuses[dataset] = {"status": "ran"}
            datasets[dataset] = {"records": written}
            continue
        with AuthorityWriter(path):
            pass  # an empty file, so the promoter finds every path
        datasets[dataset] = {"records": 0}
    return statuses, datasets


def load_authorities(conn, source: Source, out_dir) -> Dict[str, dict]:
    from data_loading import authority_loader

    loaded = {}
    for dataset in AUTHORITY_SOURCES[source.name]:
        result = authority_loader.load_artifact(conn, os.path.join(out_dir, f"{dataset}.jsonl"))
        loaded[dataset] = result.get(dataset, {})
    return loaded


def run_month_authorities(conn, source: Source, data_path, month_folder) -> Optional[dict]:
    """Extract and load the cited authorities of one month's batch. Returns
    the counts, or None when the chunk is marked as having no source data."""
    processed_dir = os.path.join(data_path, "processed", month_folder)
    if os.path.exists(os.path.join(processed_dir, NO_SOURCE_DATA_MARKER.format(source.prefix))):
        log.info("authorities: %s %s has no source data", source.name, month_folder)
        return None
    csv_path = os.path.join(processed_dir, source.processed_csv)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"processed artifact missing for authority extraction: {csv_path}")
    keys = read_processed_keys(csv_path, source.key_column)
    case_ids = case_ids_for_keys(conn, source, keys)
    out_dir = os.path.join(processed_dir, AUTHORITIES_DIR)
    statuses, datasets = extract_authorities(conn, source, out_dir, case_ids=case_ids)
    for dataset, load in load_authorities(conn, source, out_dir).items():
        datasets[dataset]["load"] = load
    counts = {
        "source": source.name,
        "month": month_folder,
        "case_keys": len(keys),
        "case_ids": len(case_ids),
        "extractors": statuses,
        "datasets": datasets,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"authorities {source.name} {month_folder}", counts)
    return counts


def run_window_authorities(var_prefix, **context):
    """Airflow callable: cited authorities for every month chunk of the run's
    window. A no-op unless AUTHORITY_EXTRACTION_ENABLED."""
    if not authority_enabled():
        log.info("authorities: %s is off; nothing to do", AUTHORITY_FLAG)
        return None
    from data_loading.clients.postgres import PostgresCLEClient
    from etl_factory import get_data_path, iter_month_chunks, resolve_run_window

    source = SOURCE_BY_PREFIX[var_prefix]
    start, end, _ = resolve_run_window(var_prefix, context)
    data_path = get_data_path()
    summary = {}
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        for chunk_start, _chunk_end in iter_month_chunks(start, end):
            folder = chunk_start.isoformat()
            counts = run_month_authorities(conn, source, data_path, folder)
            summary[folder] = (
                None if counts is None else {d: v["records"] for d, v in counts["datasets"].items()}
            )
    return summary


def backfill_authorities(conn, source: Source, from_id, to_id, out_dir, load=False) -> dict:
    """Extract (and optionally load) the cited authorities of source over
    cases.id from_id..to_id (inclusive, either may be None) into out_dir."""
    statuses, datasets = extract_authorities(conn, source, out_dir, id_range=(from_id, to_id))
    if load:
        for dataset, result in load_authorities(conn, source, out_dir).items():
            datasets[dataset]["load"] = result
    counts = {
        "source": source.name,
        "from_id": from_id,
        "to_id": to_id,
        "extractors": statuses,
        "datasets": datasets,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"authorities {source.name} {from_id}..{to_id}", counts)
    return counts


# ---------------------------------------------------------------------------
# case outcomes and status (roadmap R5.1, R5.2)
# ---------------------------------------------------------------------------
#
# With OUTCOME_EXTRACTION_ENABLED (default off), build_monthly_task_group adds
# an ``extract_outcomes`` task as the group's last task (after
# ``extract_links`` and the legislation, law-reference and authority tasks
# when those run too; it must follow ``extract_links`` because the CJEU appeal
# status reads the appeal_of rows the links task loads). For every month
# folder it writes
# ``processed/<month>/outcomes/<source_dataset>.jsonl`` (empty when an
# extractor is switched off or found nothing), loads each file with
# data_loading.outcome_loader (insert-only) and writes the counts to
# ``processed/<month>/outcomes/_counts.<PREFIX>.json``. Flag off: the task is
# not added and the DAGs are exactly as before.
#
#     rechtspraak  rs_dictum, rs_appeal_status    only with RS_DICTUM_ENABLED
#                                                 (default off: the dictum rules
#                                                 have no real-text sample yet)
#     echr         echr_conclusion, echr_status
#     cellar       cjeu_proc_type, cjeu_appeal_status
#
# Backfill: ``python -m linking_tasks outcomes --dsn-env VAR --source S
# --from-id N --to-id M --out DIR [--load]`` (read-only without --load; the
# master flag does not apply, RS_DICTUM_ENABLED does).

OUTCOME_FLAG = "OUTCOME_EXTRACTION_ENABLED"
RS_DICTUM_FLAG = "RS_DICTUM_ENABLED"
OUTCOMES_DIR = "outcomes"


def outcomes_enabled() -> bool:
    """OUTCOME_EXTRACTION_ENABLED is set to a true value (default off)."""
    return env_flag(OUTCOME_FLAG, False)


@dataclass(frozen=True)
class ContextExtractor:
    dataset: str  # the one source_dataset it writes; also the file name
    module: str
    function: str
    flag: Optional[str] = None  # an extra flag it needs (default off)


CONTEXT_EXTRACTORS: Dict[str, Tuple[ContextExtractor, ...]] = {
    "rechtspraak": (
        ContextExtractor(
            "rs_dictum", "data_extraction.case_context.rs_dictum", "extract", RS_DICTUM_FLAG
        ),
        ContextExtractor(
            "rs_appeal_status",
            "data_extraction.case_context.case_status",
            "extract_rs",
            RS_DICTUM_FLAG,
        ),
    ),
    "echr": (
        ContextExtractor(
            "echr_conclusion", "data_extraction.case_context.echr_outcomes", "extract"
        ),
        ContextExtractor("echr_status", "data_extraction.case_context.case_status", "extract_echr"),
    ),
    "cellar": (
        ContextExtractor("cjeu_proc_type", "data_extraction.case_context.cjeu_outcomes", "extract"),
        ContextExtractor(
            "cjeu_appeal_status", "data_extraction.case_context.case_status", "extract_cjeu"
        ),
    ),
}


def outcome_artifact_paths(source: Source, month_folder: str) -> List[str]:
    """Paths (relative to DATA_PATH) of the outcome/status files a weekly run
    writes for one month, in load order; every one exists after the task,
    possibly empty. The promoter registers these with their own role
    (e.g. 'case_context'), replayed after 'links'."""
    return [
        f"processed/{month_folder}/{OUTCOMES_DIR}/{e.dataset}.jsonl"
        for e in CONTEXT_EXTRACTORS[source.name]
    ]


def extract_outcomes(conn, source: Source, out_dir, case_ids=None, id_range=None):
    """Write out_dir/<source_dataset>.jsonl for every outcome/status dataset
    of source; returns ({dataset: status}, {dataset: {"records": n}})."""
    from data_extraction.linking.artifact import ArtifactWriter

    os.makedirs(out_dir, exist_ok=True)
    statuses, datasets = {}, {}
    for extractor in CONTEXT_EXTRACTORS[source.name]:
        path = os.path.join(out_dir, f"{extractor.dataset}.jsonl")
        reason = None
        if extractor.flag and not env_flag(extractor.flag, False):
            reason = f"{extractor.flag} is off"
        if reason or (case_ids is not None and not case_ids):
            with ArtifactWriter(path):
                pass  # an empty file, so the promoter finds every path
            statuses[extractor.dataset] = (
                {"status": "skipped", "reason": reason} if reason else {"status": "no_cases"}
            )
            if reason:
                log.info("outcomes: skipping %s (%s)", extractor.dataset, reason)
            datasets[extractor.dataset] = {"records": 0}
            continue
        function = getattr(importlib.import_module(extractor.module), extractor.function)
        written, _stats = function(conn, case_ids=case_ids, id_range=id_range, out_path=path)
        statuses[extractor.dataset] = {"status": "ran"}
        datasets[extractor.dataset] = {"records": written}
    return statuses, datasets


def load_outcomes(conn, source: Source, out_dir) -> Dict[str, dict]:
    """Load every outcome/status file of source from out_dir; {dataset: counts}."""
    from data_loading import outcome_loader

    loaded = {}
    for extractor in CONTEXT_EXTRACTORS[source.name]:
        result = outcome_loader.load_artifact(
            conn, os.path.join(out_dir, f"{extractor.dataset}.jsonl")
        )
        loaded[extractor.dataset] = result.get(extractor.dataset, {})
    return loaded


def run_month_outcomes(conn, source: Source, data_path, month_folder) -> Optional[dict]:
    """Extract and load the outcomes and statuses of one month's batch."""
    processed_dir = os.path.join(data_path, "processed", month_folder)
    if os.path.exists(os.path.join(processed_dir, NO_SOURCE_DATA_MARKER.format(source.prefix))):
        log.info("outcomes: %s %s has no source data", source.name, month_folder)
        return None
    csv_path = os.path.join(processed_dir, source.processed_csv)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"processed artifact missing for outcome extraction: {csv_path}")
    keys = read_processed_keys(csv_path, source.key_column)
    case_ids = case_ids_for_keys(conn, source, keys)
    out_dir = os.path.join(processed_dir, OUTCOMES_DIR)
    statuses, datasets = extract_outcomes(conn, source, out_dir, case_ids=case_ids)
    for dataset, load in load_outcomes(conn, source, out_dir).items():
        datasets[dataset]["load"] = load
    counts = {
        "source": source.name,
        "month": month_folder,
        "case_keys": len(keys),
        "case_ids": len(case_ids),
        "extractors": statuses,
        "datasets": datasets,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"outcomes {source.name} {month_folder}", counts)
    return counts


def run_window_outcomes(var_prefix, **context):
    """Airflow callable: outcomes and statuses for every month chunk of the
    run's window. A no-op unless OUTCOME_EXTRACTION_ENABLED."""
    if not outcomes_enabled():
        log.info("outcomes: %s is off; nothing to do", OUTCOME_FLAG)
        return None
    from data_loading.clients.postgres import PostgresCLEClient
    from etl_factory import get_data_path, iter_month_chunks, resolve_run_window

    source = SOURCE_BY_PREFIX[var_prefix]
    start, end, _ = resolve_run_window(var_prefix, context)
    data_path = get_data_path()
    summary = {}
    with PostgresCLEClient() as client:
        conn = client._get_conn()
        for chunk_start, _chunk_end in iter_month_chunks(start, end):
            folder = chunk_start.isoformat()
            counts = run_month_outcomes(conn, source, data_path, folder)
            summary[folder] = (
                None if counts is None else {d: v["records"] for d, v in counts["datasets"].items()}
            )
    return summary


def backfill_outcomes(conn, source: Source, from_id, to_id, out_dir, load=False) -> dict:
    """Extract (and optionally load) outcomes and statuses over cases.id
    from_id..to_id (inclusive, either may be None) into out_dir."""
    statuses, datasets = extract_outcomes(conn, source, out_dir, id_range=(from_id, to_id))
    if load:
        for dataset, result in load_outcomes(conn, source, out_dir).items():
            datasets[dataset]["load"] = result
    counts = {
        "source": source.name,
        "from_id": from_id,
        "to_id": to_id,
        "extractors": statuses,
        "datasets": datasets,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"outcomes {source.name} {from_id}..{to_id}", counts)
    return counts


# ---------------------------------------------------------------------------
# backfill CLI
# ---------------------------------------------------------------------------


def backfill(conn, source: Source, from_id, to_id, out_dir, load=False, ecli_scope=None) -> dict:
    """Extract (and optionally load) the links of source over cases.id
    from_id..to_id (inclusive, either may be None) into out_dir.

    rs_text scans with BACKFILL_ECLI_SCOPE ('cross') unless ecli_scope says
    otherwise: historical cases already have their Dutch ECLI citations in
    rs_body_cite / rs_lido_sqlite."""
    statuses, datasets = extract_links(
        conn,
        source,
        out_dir,
        id_range=(from_id, to_id),
        ecli_scope=ecli_scope or BACKFILL_ECLI_SCOPE,
    )
    if load:
        for dataset, result in load_links(conn, source, out_dir).items():
            datasets[dataset]["load"] = result
    counts = {
        "source": source.name,
        "from_id": from_id,
        "to_id": to_id,
        "extractors": statuses,
        "datasets": datasets,
    }
    _write_counts(os.path.join(out_dir, COUNTS_FILE.format(source.prefix)), counts)
    _log_counts(f"{source.name} {from_id}..{to_id}", counts)
    return counts


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-dataset link extraction")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("backfill", help="extract (and load) links over a cases.id range")
    run.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    run.add_argument("--source", required=True, choices=sorted(SOURCES))
    run.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    run.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    run.add_argument("--out", required=True, help="directory for <source_dataset>.jsonl")
    run.add_argument("--load", action="store_true", help="also load the files into the DSN")
    run.add_argument(
        "--ecli-scope",
        choices=("cross", "all"),
        default=None,
        help="rs_text ECLIs: cross-court only (backfill default) or all",
    )
    leg = commands.add_parser(
        "legislation-backfill",
        help="extract (and load) EU/CoE/UN acts and ECHR article references over a cases.id range",
    )
    leg.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    leg.add_argument(
        "--source", required=True, choices=sorted(n for n, o in LEGISLATION_OUTPUTS.items() if o)
    )
    leg.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    leg.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    leg.add_argument("--out", required=True, help="directory for the legislation files")
    leg.add_argument("--load", action="store_true", help="also load the files into the DSN")
    law = commands.add_parser(
        "backfill-law", help="extract (and load) law references over a cases.id range"
    )
    law.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    law.add_argument("--source", required=True, choices=sorted(SOURCES))
    law.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    law.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    law.add_argument("--out", required=True, help="directory for <source_dataset>.jsonl")
    law.add_argument("--load", action="store_true", help="also load the file into the DSN")
    authorities = commands.add_parser(
        "backfill-authorities",
        help="extract (and load) cited authorities (Phase 4) over a cases.id range",
    )
    authorities.add_argument("--dsn-env", required=True, help="environment variable with the DSN")
    authorities.add_argument("--source", required=True, choices=sorted(SOURCES))
    authorities.add_argument("--from-id", type=int, default=None, help="first cases.id")
    authorities.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    authorities.add_argument("--out", required=True, help="directory for <source_dataset>.jsonl")
    authorities.add_argument("--load", action="store_true", help="also load into the DSN")
    outcomes = commands.add_parser(
        "outcomes", help="extract (and load) case outcomes and status over a cases.id range"
    )
    outcomes.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    outcomes.add_argument("--source", required=True, choices=sorted(SOURCES))
    outcomes.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    outcomes.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    outcomes.add_argument("--out", required=True, help="directory for <source_dataset>.jsonl")
    outcomes.add_argument("--load", action="store_true", help="also load the files into the DSN")
    args = parser.parse_args(argv)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f"environment variable {args.dsn_env} is not set")
    import psycopg2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = psycopg2.connect(dsn)
    try:
        if not args.load:
            conn.set_session(readonly=True)
        if args.command == "legislation-backfill":
            counts = legislation_backfill(
                conn, SOURCES[args.source], args.from_id, args.to_id, args.out, load=args.load
            )
        elif args.command == "backfill-law":
            counts = backfill_law(
                conn, SOURCES[args.source], args.from_id, args.to_id, args.out, load=args.load
            )
        elif args.command == "backfill-authorities":
            counts = backfill_authorities(
                conn, SOURCES[args.source], args.from_id, args.to_id, args.out, load=args.load
            )
        elif args.command == "outcomes":
            counts = backfill_outcomes(
                conn, SOURCES[args.source], args.from_id, args.to_id, args.out, load=args.load
            )
        else:
            counts = backfill(
                conn,
                SOURCES[args.source],
                args.from_id,
                args.to_id,
                args.out,
                load=args.load,
                ecli_scope=args.ecli_scope,
            )
    finally:
        conn.close()
    print(json.dumps(_json_safe(counts), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
