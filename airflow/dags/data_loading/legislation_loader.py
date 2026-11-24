"""
Load the legislation artifacts (data_extraction/legislation/) into the
database it is given: acts outside the BWB register into legislation and
legislation_alias (R3.1), and law references to their provisions into
legal_provision and case_law_reference (R3.7).

Insert-only, so the weekly runs, the promoter's replay into production and the
backfill can all run it any number of times:

  * acts: ON CONFLICT on legislation_uk_external, its predicate restated
    (scheme IN ('celex', 'coe_treaty', 'un_treaty')), which works against the
    deployed partial index and the plain one of db/schema.sql alike. An act
    already there is left as it is (title included); its aliases are still
    added (legislation_alias_uk).
  * law references: the act must exist; one the curated fixture holds
    (external_acts.json) is inserted first, so an echr_article artifact loads
    into a database that never saw the legislation artifact. Provisions are
    created per (act, element type, article, paragraph) under
    legal_provision_uk_external (article rows first, then paragraph rows with
    parent_id set to their article). case_law_reference rows have
    provision_id and legislation_id set and raw_resource NULL, so
    case_law_reference_uk_provision (case_id, provision_id, role,
    source_dataset) is their key; conflicts are counted as existing.
  * a record whose source case is missing is counted and skipped.

Everything written carries source_dataset and extractor_version, so a dataset
is removed with DELETEs by source_dataset, in foreign-key order:

  1. case_law_reference rows of the dataset, and then every row of another
     dataset whose legislation_id or provision_id points at the dataset's acts
     or provisions (law references of R3.2-R3.4, rs_lido_sqlite rows resolved
     by R3.5, Cellar CDM references resolved by cjeu_loader): delete those
     too, or keep the acts they point at;
  2. legal_provision rows of the dataset, children before parents (paragraph
     rows, parent_id set, before their article rows; a provision of another
     dataset whose parent_id points at one of them, or a lido_link row whose
     target_provision_id does, blocks it the same way);
  3. legislation_alias rows of the dataset's acts;
  4. legislation rows of the dataset.

Needs migration 0011 (columns and unique indexes).

CLI:
    python -m data_loading.legislation_loader acts --dsn-env VAR PATH [PATH ...]
    python -m data_loading.legislation_loader references --dsn-env VAR PATH [PATH ...]
"""

import argparse
import json
import logging
import os
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from data_extraction.legislation import acts as acts_module
from data_extraction.legislation.acts import UK_PREDICATE, ActRecord, read_acts
from data_extraction.legislation.law_reference import LawReferenceRecord, read_law_references

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
BATCH_SIZE = 2000

JURISDICTIONS = {
    "EU": ("European Union", "supranational"),
    "CE": ("Council of Europe", "international"),
    "UN": ("United Nations", "international"),
}

ARTICLE = "article"
PARAGRAPH = "paragraph"


def _values(cursor, sql, rows, template, fetch=True):
    if not rows:
        return []
    from psycopg2.extras import execute_values

    return execute_values(cursor, sql, rows, template=template, page_size=len(rows), fetch=fetch)


def jurisdiction_ids(cursor) -> Dict[str, int]:
    """{iso_code: id} for EU, CE and UN; inserts a missing lookup row
    (migration 0011 adds them; this covers a database built without it)."""
    cursor.execute(
        f"""
        INSERT INTO {SCHEMA}.jurisdiction (iso_code, name, type)
        SELECT * FROM unnest(%s::text[], %s::text[], %s::text[])
        ON CONFLICT (iso_code) DO NOTHING
        """,
        (
            list(JURISDICTIONS),
            [v[0] for v in JURISDICTIONS.values()],
            [v[1] for v in JURISDICTIONS.values()],
        ),
    )
    cursor.execute(
        f"SELECT iso_code, id FROM {SCHEMA}.jurisdiction WHERE iso_code = ANY(%s)",
        (list(JURISDICTIONS),),
    )
    return dict(cursor.fetchall())


# ---------------------------------------------------------------------------
# acts
# ---------------------------------------------------------------------------

_ACT_FIELDS = (
    ("identifier", "text"),
    ("scheme", "text"),
    ("title", "text"),
    ("jurisdiction_id", "bigint"),
    ("document_type", "text"),
    ("enacted_date", "date"),
    ("enacted_year", "smallint"),
    ("eli", "text"),
    ("source_dataset", "text"),
    ("extractor_version", "text"),
)
_ACT_COLUMNS = ", ".join(f for f, _t in _ACT_FIELDS)
_ACT_TEMPLATE = "(%s::integer, " + ", ".join(f"%s::{t}" for _f, t in _ACT_FIELDS) + ")"
_INSERT_ACTS = f"""
    INSERT INTO {SCHEMA}.legislation ({_ACT_COLUMNS})
    SELECT {_ACT_COLUMNS} FROM (VALUES %s) AS v(ord, {_ACT_COLUMNS})
     ORDER BY ord
    ON CONFLICT (scheme, identifier) WHERE {UK_PREDICATE}
    DO NOTHING
    RETURNING scheme, identifier
"""
_FIND_ACTS = f"""
    SELECT l.scheme, l.identifier, l.id
      FROM (VALUES %s) AS v(scheme, identifier)
      JOIN {SCHEMA}.legislation l
        ON l.scheme = v.scheme AND l.identifier = v.identifier
     WHERE l.{UK_PREDICATE}
"""
_INSERT_ALIASES = f"""
    INSERT INTO {SCHEMA}.legislation_alias (legislation_id, alias, source)
    SELECT legislation_id, alias, source
      FROM (VALUES %s) AS v(ord, legislation_id, alias, source)
     ORDER BY ord
    ON CONFLICT (legislation_id, alias) DO NOTHING
    RETURNING legislation_id
"""


def find_acts(cursor, keys: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], int]:
    keys = sorted(set(keys))
    rows = _values(cursor, _FIND_ACTS, keys, "(%s::text, %s::text)")
    return {(scheme, identifier): act_id for scheme, identifier, act_id in rows}


def insert_acts(cursor, records: Sequence[ActRecord], counts) -> Dict[Tuple[str, str], int]:
    """Insert acts and their aliases; returns {key: legislation.id} for every
    record (inserted now or already there). counts[dataset] gets inserted,
    existing and aliases_inserted."""
    if not records:
        return {}
    jurisdictions = jurisdiction_ids(cursor)
    rows = [  # in _ACT_FIELDS order
        (
            i,
            r.identifier,
            r.scheme,
            r.title,
            jurisdictions[r.jurisdiction],
            r.document_type,
            r.enacted_date,
            r.enacted_year,
            r.eli,
            r.source_dataset,
            r.extractor_version,
        )
        for i, r in enumerate(records)
    ]
    inserted = {tuple(row) for row in _values(cursor, _INSERT_ACTS, rows, _ACT_TEMPLATE)}
    seen = set()
    for r in records:
        if r.key in seen:
            counts[r.source_dataset]["duplicate_in_batch"] += 1
            continue
        seen.add(r.key)
        counts[r.source_dataset]["inserted" if r.key in inserted else "existing"] += 1
    ids = find_acts(cursor, (r.key for r in records))
    alias_rows, dataset_of = [], {}
    for r in records:
        act_id = ids.get(r.key)
        if act_id is None:
            counts[r.source_dataset]["not_found_after_insert"] += 1
            continue
        dataset_of[act_id] = r.source_dataset
        for alias in r.aliases:
            alias_rows.append((len(alias_rows), act_id, alias, acts_module.ALIAS_SOURCE))
    for (act_id,) in _values(
        cursor, _INSERT_ALIASES, alias_rows, "(%s::integer, %s::bigint, %s::text, %s::text)"
    ):
        counts[dataset_of[act_id]]["aliases_inserted"] += 1
    return ids


def _batches(records, batch_size):
    batch = []
    for record in records:
        batch.append(record)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _finish(counts, label):
    for dataset, c in sorted(counts.items()):
        log.info("%s %s: %s", label, dataset, dict(sorted(c.items())))
    return {dataset: {k: v for k, v in c.items() if v} for dataset, c in counts.items()}


def load_acts(conn, records: Iterable[ActRecord], batch_size: int = BATCH_SIZE):
    """Insert act records batch by batch, one transaction per batch. Returns
    {source_dataset: {inserted, existing, aliases_inserted, ...}}."""
    counts = defaultdict(Counter)
    try:
        for batch in _batches(records, batch_size):
            with conn.cursor() as cursor:
                insert_acts(cursor, batch, counts)
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return _finish(counts, "legislation load")


def load_acts_artifact(conn, path, batch_size: int = BATCH_SIZE):
    return load_acts(conn, read_acts(path), batch_size=batch_size)


def load_curated(conn):
    """Insert the committed fixture (external_acts.json); insert-only."""
    return load_acts(conn, acts_module.curated_acts())


# ---------------------------------------------------------------------------
# law references
# ---------------------------------------------------------------------------

_INSERT_PROVISIONS = f"""
    INSERT INTO {SCHEMA}.legal_provision
        (legislation_id, parent_id, element_type, article_label, paragraph, title,
         source_dataset, extractor_version)
    SELECT legislation_id, parent_id, element_type, article_label, paragraph, title,
           source_dataset, extractor_version
      FROM (VALUES %s) AS v(ord, legislation_id, parent_id, element_type, article_label,
                            paragraph, title, source_dataset, extractor_version)
     ORDER BY ord
    ON CONFLICT (legislation_id, element_type, article_label, COALESCE(paragraph, ''))
        WHERE source_dataset IS NOT NULL
    DO NOTHING
    RETURNING id
"""
_PROVISION_TEMPLATE = (
    "(%s::integer, %s::bigint, %s::bigint, %s::text, %s::text, %s::text, %s::text, "
    "%s::text, %s::text)"
)
_FIND_PROVISIONS = f"""
    SELECT p.legislation_id, p.element_type, p.article_label, p.paragraph, p.id
      FROM (VALUES %s) AS v(legislation_id, element_type, article_label, paragraph)
      JOIN {SCHEMA}.legal_provision p
        ON p.legislation_id = v.legislation_id AND p.element_type = v.element_type
       AND p.article_label = v.article_label
       AND COALESCE(p.paragraph, '') = COALESCE(v.paragraph, '')
     WHERE p.source_dataset IS NOT NULL
"""

_REF_FIELDS = (
    ("case_id", "bigint"),
    ("legislation_id", "bigint"),
    ("provision_id", "bigint"),
    ("raw_scheme", "text"),
    ("raw_subdivision", "text"),
    ("raw_reference", "text"),
    ("role", "text"),
    ("source_dataset", "text"),
    ("extractor_version", "text"),
)
_REF_COLUMNS = ", ".join(f for f, _t in _REF_FIELDS)
_REF_TEMPLATE = "(%s::integer, " + ", ".join(f"%s::{t}" for _f, t in _REF_FIELDS) + ")"
# Provision rows: case_law_reference_uk_provision, predicate restated.
_INSERT_PROVISION_REFS = f"""
    INSERT INTO {SCHEMA}.case_law_reference ({_REF_COLUMNS})
    SELECT {_REF_COLUMNS} FROM (VALUES %s) AS v(ord, {_REF_COLUMNS})
     ORDER BY ord
    ON CONFLICT (case_id, provision_id, role, source_dataset)
        WHERE provision_id IS NOT NULL AND raw_resource IS NULL
    DO NOTHING
    RETURNING case_id, provision_id, role, source_dataset
"""
# Whole-act rows: case_law_reference_uk_legislation, predicate restated.
_INSERT_ACT_REFS = f"""
    INSERT INTO {SCHEMA}.case_law_reference ({_REF_COLUMNS})
    SELECT {_REF_COLUMNS} FROM (VALUES %s) AS v(ord, {_REF_COLUMNS})
     ORDER BY ord
    ON CONFLICT (case_id, legislation_id, role, source_dataset)
        WHERE provision_id IS NULL AND legislation_id IS NOT NULL AND raw_resource IS NULL
    DO NOTHING
    RETURNING case_id, legislation_id, role, source_dataset
"""


def provision_title(article: str, paragraph: Optional[str]) -> str:
    return f"Article {article}" + (f" § {paragraph}" if paragraph else "")


def ensure_acts(cursor, keys, counts) -> Dict[Tuple[str, str], int]:
    """{key: legislation.id} for the acts named; inserts the curated ones that
    are missing. Keys neither present nor curated are left out."""
    keys = set(keys)
    found = find_acts(cursor, keys)
    curated = acts_module.curated_by_key()
    missing = [curated[k] for k in sorted(keys - set(found)) if k in curated]
    if missing:
        found.update(insert_acts(cursor, missing, counts))
    return found


def ensure_provisions(cursor, wanted, dataset, version, counts):
    """wanted: {(act_id, article, paragraph or None)}; returns {that key:
    provision id}. Article rows first (paragraph rows point at them)."""
    out = {}
    articles = sorted({(act_id, article) for act_id, article, _p in wanted})
    paragraphs = sorted(
        {(a, art, p) for a, art, p in wanted if p is not None}, key=lambda k: (k[0], k[1], k[2])
    )
    for level, items in ((ARTICLE, articles), (PARAGRAPH, paragraphs)):
        if not items:
            continue
        rows = []
        for i, item in enumerate(items):
            act_id, article = item[0], item[1]
            paragraph = item[2] if level == PARAGRAPH else None
            parent = out.get((act_id, article, None)) if level == PARAGRAPH else None
            rows.append(
                (
                    i,
                    act_id,
                    parent,
                    level,
                    article,
                    paragraph,
                    provision_title(article, paragraph),
                    dataset,
                    version,
                )
            )
        inserted = _values(cursor, _INSERT_PROVISIONS, rows, _PROVISION_TEMPLATE)
        counts[dataset][f"provisions_inserted_{level}"] += len(inserted)
        found = _values(
            cursor,
            _FIND_PROVISIONS,
            [(r[1], level, r[4], r[5]) for r in rows],
            "(%s::bigint, %s::text, %s::text, %s::text)",
        )
        for act_id, _type, article, paragraph, provision_id in found:
            out[(act_id, article, paragraph)] = provision_id
    return out


def _load_reference_batch(cursor, batch: List[LawReferenceRecord], counts):
    from data_loading.link_loader import _cases_by_key, _resolve

    cases = _cases_by_key(cursor, batch)
    act_ids = ensure_acts(cursor, {r.act_key for r in batch}, counts)
    planned = []
    for record in batch:
        c = counts[record.source_dataset]
        source = _resolve(cases, record.source)
        if source is None:
            c["source_missing"] += 1
            continue
        act_id = act_ids.get(record.act_key)
        if act_id is None:
            c["act_missing"] += 1
            continue
        planned.append((record, source[0], act_id))
    by_dataset = defaultdict(list)
    for item in planned:
        by_dataset[(item[0].source_dataset, item[0].extractor_version)].append(item)
    for (dataset, version), items in sorted(by_dataset.items()):
        wanted = {
            (act_id, r.article, r.paragraph) for r, _case, act_id in items if r.article is not None
        }
        provisions = ensure_provisions(cursor, wanted, dataset, version, counts)
        provision_rows, act_rows = [], []
        for record, case_id, act_id in items:
            provision_id = None
            if record.article is not None:
                provision_id = provisions.get((act_id, record.article, record.paragraph))
                if provision_id is None:
                    counts[dataset]["provision_missing"] += 1
                    continue
            target = provision_rows if provision_id is not None else act_rows
            target.append(
                (
                    len(target),
                    case_id,
                    act_id,
                    provision_id,
                    record.raw_scheme,
                    record.raw_subdivision,
                    record.raw_reference,
                    record.role,
                    dataset,
                    version,
                )
            )
        for sql, rows in ((_INSERT_PROVISION_REFS, provision_rows), (_INSERT_ACT_REFS, act_rows)):
            inserted = _values(cursor, sql, rows, _REF_TEMPLATE)
            counts[dataset]["inserted"] += len(inserted)
            counts[dataset]["existing"] += len(rows) - len(inserted)


def load_law_references(conn, records: Iterable[LawReferenceRecord], batch_size=BATCH_SIZE):
    """Insert law-reference records batch by batch, one transaction per batch.
    Returns {source_dataset: {inserted, existing, source_missing, act_missing,
    provisions_inserted_article, provisions_inserted_paragraph, ...}}; acts
    inserted from the fixture are counted under legislation_curated."""
    counts = defaultdict(Counter)
    try:
        for batch in _batches(records, batch_size):
            with conn.cursor() as cursor:
                _load_reference_batch(cursor, batch, counts)
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return _finish(counts, "law reference load")


def load_law_reference_artifact(conn, path, batch_size: int = BATCH_SIZE):
    return load_law_references(conn, read_law_references(path), batch_size=batch_size)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Load legislation and law-reference artifacts.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("acts", "load legislation artifacts (acts and aliases)"),
        ("references", "load law-reference artifacts (provisions and case_law_reference)"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument(
            "--dsn-env", required=True, help="environment variable holding the DSN"
        )
        command.add_argument("--batch-size", type=int, default=BATCH_SIZE)
        command.add_argument("paths", nargs="+", help="artifact files")
    args = parser.parse_args(argv)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f"environment variable {args.dsn_env} is not set")
    import psycopg2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load = load_acts_artifact if args.command == "acts" else load_law_reference_artifact
    conn = psycopg2.connect(dsn)
    try:
        result = {str(p): load(conn, p, batch_size=args.batch_size) for p in args.paths}
    finally:
        conn.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
