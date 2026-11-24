"""
Load a link artifact (data_extraction/linking/artifact.py) into case_citation
and case_citation_mention.

The same code loads the weekly artifacts into db-dev, the promoter's replay
into production, and the historical backfill, so it only ever inserts:

  * resolved rows (both cases present) go in under case_citation_uk_resolved;
  * a target named by ECLI/CELEX that this database does not have yet (for
    example a case in db-dev that is not promoted yet) is written unresolved,
    with target_ecli_raw / target_celex_raw, for late binding to resolve when
    the case arrives;
  * a reference with no target (a case number nothing matched) is written
    unresolved with target_ref_raw / target_ref_scheme;
  * every mention is inserted against the row's id in this database.

A row that already exists is left as it is and its mentions are added. A record
whose source case is missing is counted and skipped. Nothing is updated or
deleted. Returns counts per source_dataset.

Late binding (roadmap R2.9, ``resolve_late``): when cases are loaded after
the links that name them, the unresolved rows of the link datasets
(artifact.LINK_DATASETS) whose target_ecli_raw, target_celex_raw or
(target_ref_scheme, target_ref_raw) now match one of those cases get a
resolved twin, with the unresolved row's mentions copied to it. The
unresolved row stays, so this too is insert-only and can run any number of
times. Legacy datasets are never touched here (cjeu_loader SQL_LINK_* resolves
those in place).

CLI:
    python -m data_loading.link_loader load --dsn-env VAR PATH [PATH ...]
    python -m data_loading.link_loader resolve-late --dsn-env VAR --from-id N --to-id M
"""

import argparse
import json
import logging
import os
from collections import Counter, defaultdict
from typing import Iterable, Optional, Sequence

from data_extraction.linking import resolver
from data_extraction.linking.artifact import LINK_DATASETS, LinkRecord, match_method

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
BATCH_SIZE = 1000

# Which corpus an ECLI belongs to, for is_cross_jurisdiction on rows whose
# target is not in this database. Anything else (other national ECLIs) is
# treated as foreign to every corpus.
_ECLI_CORPUS = (("ECLI:EU:", "CJEU"), ("ECLI:CE:ECHR:", "ECHR"), ("ECLI:NL:", "RS"))


def corpus_of_ecli(ecli):
    for prefix, corpus in _ECLI_CORPUS:
        if ecli and ecli.upper().startswith(prefix):
            return corpus
    return None


def _cases_by_key(cursor, records):
    """Map ('ecli'|'celex'|'item_id', value) -> (case_id, sources) for every
    case named in records, in one query. An item_id is looked up in
    cases.item_id and, failing that, in echr_document.item_id: HUDOC language
    variants and related documents share one case row, which carries only the
    canonical item's id."""
    eclis, celexes, item_ids = set(), set(), set()
    for record in records:
        for key in (record.source, record.target):
            if key is None:
                continue
            if key.ecli:
                eclis.add(key.ecli)
            if key.celex:
                celexes.add(key.celex)
            if key.item_id:
                item_ids.add(key.item_id)
    found = {}
    if not (eclis or celexes or item_ids):
        return found
    cursor.execute(
        f"""
        SELECT id, ecli, celex_id, item_id, sources, false
          FROM {SCHEMA}.cases
         WHERE ecli = ANY(%(eclis)s) OR celex_id = ANY(%(celexes)s) OR item_id = ANY(%(items)s)
        UNION ALL
        SELECT c.id, NULL, NULL, d.item_id, c.sources, true
          FROM {SCHEMA}.echr_document d
          JOIN {SCHEMA}.cases c ON c.id = d.case_id
         WHERE d.item_id = ANY(%(items)s)
        """,
        {"eclis": sorted(eclis), "celexes": sorted(celexes), "items": sorted(item_ids)},
    )
    by_document = {}
    for case_id, ecli, celex, item_id, sources, via_document in cursor.fetchall():
        value = (case_id, list(sources or []))
        if via_document:
            by_document[item_id] = value
            continue
        if ecli in eclis:
            found[("ecli", ecli)] = value
        if celex in celexes:
            found[("celex", celex)] = value
        if item_id in item_ids:
            found[("item_id", item_id)] = value
    for item_id, value in by_document.items():
        found.setdefault(("item_id", item_id), value)
    return found


def _resolve(found, key):
    """ECLI first, then CELEX, then item_id; None when absent."""
    if key is None:
        return None
    for name in ("ecli", "celex", "item_id"):
        value = getattr(key, name)
        if value and (name, value) in found:
            return found[(name, value)]
    return None


_INSERT_COLUMNS = (
    "source_case_id, target_case_id, target_ecli_raw, target_celex_raw, target_ref_raw, "
    "target_ref_scheme, relation_type, source_dataset, weight, is_cross_jurisdiction, "
    "extractor_version, match_method, confidence"
)
# The row fields in _INSERT_COLUMNS order, with their SQL types (VALUES lists
# need them: a column of NULLs has no type otherwise).
_ROW_FIELDS = (
    ("source_case_id", "bigint"),
    ("target_case_id", "bigint"),
    ("target_ecli_raw", "text"),
    ("target_celex_raw", "text"),
    ("target_ref_raw", "text"),
    ("target_ref_scheme", "text"),
    ("relation_type", "text"),
    ("source_dataset", "text"),
    ("weight", "integer"),
    ("is_cross_jurisdiction", "boolean"),
    ("extractor_version", "text"),
    ("match_method", "text"),
    ("confidence", "real"),
)


def _template(types):
    return "(" + ", ".join(f"%s::{t}" for t in types) + ")"


# Every statement below takes one VALUES list per batch (execute_values with
# the whole batch as one page) and keeps the batch's order through ``ord``:
# rows are inserted in artifact order, so within a batch the first of two
# conflicting records is the one inserted, as when they went in one by one.
_ROW_TEMPLATE = _template(["integer"] + [t for _f, t in _ROW_FIELDS])
_ROW_ALIASES = "ord, " + ", ".join(f for f, _t in _ROW_FIELDS)

# Resolved rows: one arbiter, named with its predicate so the statement works
# against the deployed (partial) and the local (plain) unique index alike.
_INSERT_RESOLVED = f"""
    INSERT INTO {SCHEMA}.case_citation ({_INSERT_COLUMNS})
    SELECT {_INSERT_COLUMNS} FROM (VALUES %s) AS v({_ROW_ALIASES})
     ORDER BY ord
    ON CONFLICT (source_case_id, target_case_id, relation_type, source_dataset)
        WHERE target_case_id IS NOT NULL
    DO NOTHING
    RETURNING id, source_case_id, target_case_id, relation_type, source_dataset
"""
# Unresolved rows can fall under two unique indexes at once (an ECLI and a
# case number), so any conflict means "already there".
_INSERT_UNRESOLVED = f"""
    INSERT INTO {SCHEMA}.case_citation ({_INSERT_COLUMNS})
    SELECT {_INSERT_COLUMNS} FROM (VALUES %s) AS v({_ROW_ALIASES})
     ORDER BY ord
    ON CONFLICT DO NOTHING
    RETURNING id, source_case_id, target_ecli_raw, target_celex_raw, target_ref_raw,
              target_ref_scheme, relation_type, source_dataset
"""

_FIND_RESOLVED = f"""
    SELECT c.id, c.source_case_id, c.target_case_id, c.relation_type, c.source_dataset
      FROM (VALUES %s) AS v(source_case_id, target_case_id, relation_type, source_dataset)
      JOIN {SCHEMA}.case_citation c
        ON c.source_case_id = v.source_case_id AND c.target_case_id = v.target_case_id
       AND c.relation_type = v.relation_type AND c.source_dataset = v.source_dataset
"""
_FIND_RESOLVED_TEMPLATE = "(%s::bigint, %s::bigint, %s::text, %s::text)"

# The oldest unresolved row a record conflicted with. ``bound`` is the first
# id inserted by a later record of the same batch: a row-by-row load would not
# have seen those rows yet.
_FIND_UNRESOLVED = f"""
    SELECT v.ord,
           (SELECT c.id FROM {SCHEMA}.case_citation c
             WHERE c.target_case_id IS NULL
               AND c.source_case_id = v.source_case_id
               AND c.relation_type = v.relation_type AND c.source_dataset = v.source_dataset
               AND (   (v.target_ecli_raw IS NOT NULL AND c.target_ecli_raw = v.target_ecli_raw)
                    OR (v.target_celex_raw IS NOT NULL
                        AND c.target_celex_raw = v.target_celex_raw)
                    OR (v.target_ref_raw IS NOT NULL AND c.target_ref_raw = v.target_ref_raw
                        AND c.target_ref_scheme = v.target_ref_scheme))
               AND (v.bound IS NULL OR c.id < v.bound)
             ORDER BY c.id
             LIMIT 1)
      FROM (VALUES %s) AS v(ord, source_case_id, target_ecli_raw, target_celex_raw,
                            target_ref_raw, target_ref_scheme, relation_type,
                            source_dataset, bound)
"""
_FIND_UNRESOLVED_TEMPLATE = _template(
    ["integer", "bigint", "text", "text", "text", "text", "text", "text", "bigint"]
)

_MENTION_FIELDS = (
    ("citation_id", "bigint"),
    ("case_text_id", "bigint"),
    ("text_field", "text"),
    ("language", "text"),
    ("char_start", "integer"),
    ("char_end", "integer"),
    ("raw_text", "text"),
    ("context", "text"),
    ("segment_id", "bigint"),
    ("section", "text"),
    ("extractor_version", "text"),
)
_MENTION_COLUMNS = ", ".join(f for f, _t in _MENTION_FIELDS)
_INSERT_MENTIONS = f"""
    INSERT INTO {SCHEMA}.case_citation_mention ({_MENTION_COLUMNS})
    SELECT {_MENTION_COLUMNS} FROM (VALUES %s) AS v(ord, {_MENTION_COLUMNS})
     ORDER BY ord
    ON CONFLICT DO NOTHING
    RETURNING citation_id
"""
_MENTION_TEMPLATE = _template(["integer"] + [t for _f, t in _MENTION_FIELDS])

# case_text is unique on (case_id, language, source), case_segment on
# (case_id, segment_hash).
_CASE_TEXTS = f"""
    SELECT case_id, language, source, id FROM {SCHEMA}.case_text
     WHERE case_id = ANY(%s) AND source = ANY(%s)
"""
_CASE_SEGMENTS = f"""
    SELECT case_id, segment_hash, id FROM {SCHEMA}.case_segment
     WHERE case_id = ANY(%s) AND segment_hash = ANY(%s)
"""


def _row(record: LinkRecord, source, target):
    source_id, source_sources = source
    row = {
        "source_case_id": source_id,
        "target_case_id": None,
        "target_ecli_raw": None,
        "target_celex_raw": None,
        "target_ref_raw": record.target_ref_raw,
        "target_ref_scheme": record.target_ref_scheme,
        "relation_type": record.relation_type,
        "source_dataset": record.source_dataset,
        "weight": max(1, len(record.mentions)),
        "extractor_version": record.extractor_version,
        "match_method": record.match_method,
        "confidence": record.confidence,
    }
    if target is not None:
        target_id, target_sources = target
        row["target_case_id"] = target_id
        row["is_cross_jurisdiction"] = not (set(source_sources) & set(target_sources))
        return row
    if record.target is not None:
        row["target_ecli_raw"] = record.target.ecli
        row["target_celex_raw"] = None if record.target.ecli else record.target.celex
    target_corpus = corpus_of_ecli(row["target_ecli_raw"]) or (
        "CJEU" if row["target_celex_raw"] else None
    )
    row["is_cross_jurisdiction"] = target_corpus is not None and target_corpus not in source_sources
    return row


_RESOLVED_KEY = ("source_case_id", "target_case_id", "relation_type", "source_dataset")
_UNRESOLVED_KEY = (
    "source_case_id",
    "target_ecli_raw",
    "target_celex_raw",
    "target_ref_raw",
    "target_ref_scheme",
    "relation_type",
    "source_dataset",
)


def _values(cursor, sql, rows, template):
    """One statement for all rows; the rows it returns."""
    if not rows:
        return []
    from psycopg2.extras import execute_values

    return execute_values(cursor, sql, rows, template=template, page_size=len(rows), fetch=True)


def _insert_rows(cursor, rows, resolved):
    """Insert rows (dicts, in batch order) in one statement; returns one
    (citation_id or None, inserted?) per row, as inserting them one at a
    time and looking up the existing row after a conflict would."""
    key_fields = _RESOLVED_KEY if resolved else _UNRESOLVED_KEY
    returned = _values(
        cursor,
        _INSERT_RESOLVED if resolved else _INSERT_UNRESOLVED,
        [(i,) + tuple(row[f] for f, _t in _ROW_FIELDS) for i, row in enumerate(rows)],
        _ROW_TEMPLATE,
    )
    # A returned row is the first record of the batch with its values: later
    # identical records conflicted with it.
    new_ids = defaultdict(list)
    for citation_id, *key in returned:
        new_ids[tuple(key)].append(citation_id)
    results = [None] * len(rows)
    for i, row in enumerate(rows):
        ids = new_ids.get(tuple(row[f] for f in key_fields))
        if ids:
            results[i] = (ids.pop(0), True)
    missing = [i for i, result in enumerate(results) if result is None]
    if not missing:
        return results
    if resolved:
        found = {
            tuple(key): citation_id
            for citation_id, *key in _values(
                cursor,
                _FIND_RESOLVED,
                sorted({tuple(rows[i][f] for f in _RESOLVED_KEY) for i in missing}),
                _FIND_RESOLVED_TEMPLATE,
            )
        }
        for i in missing:
            results[i] = (found.get(tuple(rows[i][f] for f in _RESOLVED_KEY)), False)
        return results
    bounds, first_later = {}, None
    for i in range(len(rows) - 1, -1, -1):
        if results[i] is None:
            bounds[i] = first_later
        else:
            first_later = results[i][0] if first_later is None else min(first_later, results[i][0])
    found = dict(
        _values(
            cursor,
            _FIND_UNRESOLVED,
            [(i,) + tuple(rows[i][f] for f in _UNRESOLVED_KEY) + (bounds[i],) for i in missing],
            _FIND_UNRESOLVED_TEMPLATE,
        )
    )
    for i in missing:
        results[i] = (found.get(i), False)
    return results


def _mention_targets(cursor, pending):
    """case_text and case_segment ids for the mentions of pending
    [(citation_id, row, record)], in two queries."""
    case_ids = sorted({row["source_case_id"] for _c, row, record in pending if record.mentions})
    sources = sorted({m.text_source for _c, _r, rec in pending for m in rec.mentions} - {None})
    hashes = sorted({m.segment_hash for _c, _r, rec in pending for m in rec.mentions} - {None})
    texts, segments = {}, {}
    if case_ids and sources:
        cursor.execute(_CASE_TEXTS, (case_ids, sources))
        texts = {(c, lang, src): i for c, lang, src, i in cursor.fetchall()}
    if case_ids and hashes:
        cursor.execute(_CASE_SEGMENTS, (case_ids, hashes))
        segments = {(c, h): i for c, h, i in cursor.fetchall()}
    return texts, segments


def _insert_mentions(cursor, pending, counts):
    texts, segments = _mention_targets(cursor, pending)
    dataset_of, values = {}, []
    for citation_id, row, record in pending:
        dataset_of[citation_id] = record.source_dataset
        source_id = row["source_case_id"]
        for mention in record.mentions:
            values.append(
                (
                    len(values),
                    citation_id,
                    texts.get((source_id, mention.language, mention.text_source)),
                    mention.text_field,
                    mention.language,
                    mention.char_start,
                    mention.char_end,
                    mention.raw_text,
                    mention.context,
                    segments.get((source_id, mention.segment_hash)),
                    mention.section,
                    record.extractor_version,
                )
            )
    for (citation_id,) in _values(cursor, _INSERT_MENTIONS, values, _MENTION_TEMPLATE):
        counts[dataset_of[citation_id]]["mentions_inserted"] += 1


def _load_batch(cursor, batch, counts):
    """One batch in a fixed number of statements: case lookup, insert and
    find for resolved and for unresolved rows, case_text/case_segment ids,
    mentions."""
    found = _cases_by_key(cursor, batch)
    planned = []  # (record, row, resolved?)
    for record in batch:
        c = counts[record.source_dataset]
        source = _resolve(found, record.source)
        if source is None:
            c["source_missing"] += 1
            continue
        target = _resolve(found, record.target)
        if target is None and record.target is not None:
            if not (record.target.ecli or record.target.celex or record.target_ref_raw):
                # Named by item_id only and absent here: no column can hold it.
                c["target_unwritable"] += 1
                continue
        planned.append((record, _row(record, source, target), target is not None))
    outcome = {}
    for resolved in (True, False):
        # Resolved and unresolved rows never conflict with each other (the
        # unique indexes are partial on target_case_id), so the two groups
        # can go in separately.
        group = [(i, row) for i, (_rec, row, res) in enumerate(planned) if res == resolved]
        results = _insert_rows(cursor, [row for _i, row in group], resolved)
        outcome.update({i: result for (i, _row), result in zip(group, results)})
    pending = []
    for i, (record, row, resolved) in enumerate(planned):
        c = counts[record.source_dataset]
        citation_id, inserted = outcome[i]
        if citation_id is None:
            c["conflict_elsewhere"] += 1
            continue
        if inserted:
            c["inserted" if resolved else "inserted_unresolved"] += 1
        else:
            c["existing"] += 1
        if record.mentions:
            pending.append((citation_id, row, record))
    if pending:
        _insert_mentions(cursor, pending, counts)


def load_records(conn, records: Iterable[LinkRecord], batch_size: int = BATCH_SIZE):
    """Insert records batch by batch, one transaction per batch.

    Each batch takes a fixed number of statements (see _load_batch), whatever
    its size; records are read lazily, so an artifact of any size streams.

    Returns {source_dataset: Counter} with inserted, existing,
    inserted_unresolved, source_missing, target_unwritable, conflict_elsewhere
    and mentions_inserted (zero counts left out).
    """
    counts = defaultdict(Counter)
    batch = []

    def flush():
        if not batch:
            return
        with conn.cursor() as cursor:
            _load_batch(cursor, batch, counts)
        conn.commit()
        batch.clear()

    try:
        for record in records:
            batch.append(record)
            if len(batch) >= batch_size:
                flush()
        flush()
    except Exception:
        conn.rollback()
        raise
    for dataset, c in sorted(counts.items()):
        log.info("link load %s: %s", dataset, dict(sorted(c.items())))
    return {dataset: {k: v for k, v in c.items() if v} for dataset, c in counts.items()}


def load_artifact(conn, path, batch_size: int = BATCH_SIZE):
    """Load one JSONL artifact file; see load_records."""
    from data_extraction.linking.artifact import read_jsonl

    return load_records(conn, read_jsonl(path), batch_size=batch_size)


# ---------------------------------------------------------------------------
# Late binding (R2.9)
# ---------------------------------------------------------------------------

LATE_BATCH_SIZE = 5000

# Reference schemes late binding can choose for (the others, nl_zaaknummer and
# name_date, have no rule here and stay unresolved), with their match method.
_REF_METHODS = {"cjeu_case_number": "case_number", "echr_appno": "appno", "ljn": "ljn"}


def link_dataset_sql(column: str = "source_dataset") -> str:
    """SQL predicate: ``column`` is one of the link datasets (LINK_DATASETS).

    The prefixes are constants of this code base, so they are inlined."""
    for prefix in LINK_DATASETS:
        assert "'" not in prefix
    return "(" + " OR ".join(f"starts_with({column}, '{p}')" for p in LINK_DATASETS) + ")"


_LATE_PAIRS_TABLE = """
    CREATE TEMP TABLE IF NOT EXISTS late_binding_pair (
        unresolved_id   bigint NOT NULL,
        source_case_id  bigint NOT NULL,
        target_case_id  bigint NOT NULL,
        relation_type   text,
        source_dataset  text NOT NULL,
        match_method    text,
        confidence      real
    ) ON COMMIT DROP
"""

# Unresolved link rows named by the ECLI or CELEX of one of the cases, through
# cases.ecli / cases.celex_id or the case's case_identifier aliases. An alias
# counts only when no case carries the value as its own ECLI/CELEX. A row
# matched several ways takes the direct ECLI, then the ECLI alias, then the
# CELEX.
_LATE_PAIRS_BY_KEY = f"""
    WITH k AS (
        SELECT id AS case_id, 'ecli' AS kind, ecli AS value, 0 AS priority
          FROM {SCHEMA}.cases WHERE id = ANY(%(ids)s) AND ecli IS NOT NULL
        UNION ALL
        SELECT ci.case_id, 'ecli', ci.value_normalized, 1
          FROM {SCHEMA}.case_identifier ci
         WHERE ci.case_id = ANY(%(ids)s) AND ci.scheme = 'ecli'
           AND NOT EXISTS (SELECT 1 FROM {SCHEMA}.cases o WHERE o.ecli = ci.value_normalized)
        UNION ALL
        SELECT id, 'celex', celex_id, 2
          FROM {SCHEMA}.cases WHERE id = ANY(%(ids)s) AND celex_id IS NOT NULL
        UNION ALL
        SELECT ci.case_id, 'celex', ci.value_normalized, 3
          FROM {SCHEMA}.case_identifier ci
         WHERE ci.case_id = ANY(%(ids)s) AND ci.scheme = 'celex'
           AND NOT EXISTS (SELECT 1 FROM {SCHEMA}.cases o WHERE o.celex_id = ci.value_normalized)
    ),
    matched AS (
        SELECT cc.id, k.case_id, k.priority
          FROM k JOIN {SCHEMA}.case_citation cc ON cc.target_ecli_raw = k.value
         WHERE k.kind = 'ecli' AND cc.target_case_id IS NULL
        UNION ALL
        SELECT cc.id, k.case_id, k.priority
          FROM k JOIN {SCHEMA}.case_citation cc ON cc.target_celex_raw = k.value
         WHERE k.kind = 'celex' AND cc.target_case_id IS NULL
    )
    INSERT INTO late_binding_pair
    SELECT DISTINCT ON (cc.id)
           cc.id, cc.source_case_id, m.case_id, cc.relation_type, cc.source_dataset,
           cc.match_method, cc.confidence
      FROM matched m
      JOIN {SCHEMA}.case_citation cc ON cc.id = m.id
     WHERE cc.source_case_id IS NOT NULL
       AND cc.source_case_id <> m.case_id
       AND {link_dataset_sql("cc.source_dataset")}
     ORDER BY cc.id, m.priority, m.case_id
"""

# Unresolved reference rows (no ECLI/CELEX of their own) whose reference is one
# of the cases' identifiers, with the source's decision date.
_LATE_REF_ROWS = f"""
    SELECT DISTINCT cc.id, cc.source_case_id, s.date_decision, cc.relation_type,
           cc.source_dataset, cc.target_ref_scheme, cc.target_ref_raw
      FROM {SCHEMA}.case_identifier ci
      JOIN {SCHEMA}.case_citation cc
        ON cc.target_ref_scheme = ci.scheme AND cc.target_ref_raw = ci.value_normalized
      JOIN {SCHEMA}.cases s ON s.id = cc.source_case_id
     WHERE ci.case_id = ANY(%(ids)s)
       AND ci.scheme = ANY(%(schemes)s)
       AND cc.target_case_id IS NULL
       AND cc.target_ecli_raw IS NULL AND cc.target_celex_raw IS NULL
       AND {link_dataset_sql("cc.source_dataset")}
     ORDER BY cc.id
"""

_LATE_ADD_PAIR = """
    INSERT INTO late_binding_pair VALUES
        (%(unresolved_id)s, %(source_case_id)s, %(target_case_id)s, %(relation_type)s,
         %(source_dataset)s, %(match_method)s, %(confidence)s)
"""

# One resolved row per (source, target, relation, dataset): the most confident
# pair, under the resolved arbiter (restated with its predicate, as in
# _INSERT_RESOLVED).
_LATE_INSERT = f"""
    INSERT INTO {SCHEMA}.case_citation ({_INSERT_COLUMNS})
    SELECT DISTINCT ON (p.source_case_id, p.target_case_id, p.relation_type, p.source_dataset)
           p.source_case_id, p.target_case_id, NULL, NULL, cc.target_ref_raw,
           cc.target_ref_scheme, p.relation_type, p.source_dataset, cc.weight,
           NOT COALESCE(s.sources && t.sources, false),
           cc.extractor_version, p.match_method, p.confidence
      FROM late_binding_pair p
      JOIN {SCHEMA}.case_citation cc ON cc.id = p.unresolved_id
      JOIN {SCHEMA}.cases s ON s.id = p.source_case_id
      JOIN {SCHEMA}.cases t ON t.id = p.target_case_id
     ORDER BY p.source_case_id, p.target_case_id, p.relation_type, p.source_dataset,
              p.confidence DESC NULLS LAST, p.unresolved_id
    ON CONFLICT (source_case_id, target_case_id, relation_type, source_dataset)
        WHERE target_case_id IS NOT NULL
    DO NOTHING
    RETURNING source_dataset
"""

# Every pair's mentions onto its resolved row (new or already there).
_LATE_COPY_MENTIONS = f"""
    INSERT INTO {SCHEMA}.case_citation_mention
        (citation_id, case_text_id, text_field, language, char_start, char_end, raw_text,
         context, segment_id, section, treatment_label, treatment_model,
         treatment_confidence, extractor_version)
    SELECT r.id, m.case_text_id, m.text_field, m.language, m.char_start, m.char_end,
           m.raw_text, m.context, m.segment_id, m.section, m.treatment_label,
           m.treatment_model, m.treatment_confidence, m.extractor_version
      FROM late_binding_pair p
      JOIN {SCHEMA}.case_citation r
        ON r.source_case_id = p.source_case_id AND r.target_case_id = p.target_case_id
       AND r.relation_type IS NOT DISTINCT FROM p.relation_type
       AND r.source_dataset = p.source_dataset
      JOIN {SCHEMA}.case_citation_mention m ON m.citation_id = p.unresolved_id
     ORDER BY r.id, m.id
    ON CONFLICT DO NOTHING
    RETURNING (SELECT source_dataset FROM {SCHEMA}.case_citation WHERE id = citation_id)
"""

_LATE_PAIR_COUNTS = """
    SELECT source_dataset, count(*) FROM late_binding_pair GROUP BY source_dataset
"""


def _choose(scheme, candidates, source_date, relation_type):
    """resolver's choice for an unresolved reference, or None."""
    if scheme == "cjeu_case_number":
        # The suffix is not kept in target_ref_raw: a plain number means the
        # case's own documents, never an interim/costs/... order, except for
        # a review (reexamined_by), whose target is the RX decision.
        cited = "RX" if relation_type == "reexamined_by" else None
        pool = resolver.filter_cjeu_suffix(candidates, cited)
        return resolver.choose_cjeu(pool, source_date)
    if scheme == "echr_appno":
        return resolver.choose_echr(candidates, source_date)
    if scheme == "ljn":
        return resolver.choose_ljn(candidates, source_date)
    return None


def _late_ref_pairs(cursor, ids, counts):
    """Choose a target for the matching reference rows; returns the pairs."""
    cursor.execute(_LATE_REF_ROWS, {"ids": ids, "schemes": sorted(_REF_METHODS)})
    rows = cursor.fetchall()
    by_scheme = defaultdict(set)
    for _id, _source, _date, _relation, _dataset, scheme, value in rows:
        by_scheme[scheme].add(value)
    candidates = {
        scheme: resolver.fetch_candidates(cursor, scheme, sorted(values))
        for scheme, values in by_scheme.items()
    }
    pairs = []
    for unresolved_id, source_id, source_date, relation, dataset, scheme, value in rows:
        pool = [c for c in candidates[scheme].get(value, []) if c.case_id != source_id]
        choice = _choose(scheme, pool, source_date, relation)
        if choice is None:
            counts[dataset]["ref_left_unresolved"] += 1
            continue
        pairs.append(
            {
                "unresolved_id": unresolved_id,
                "source_case_id": source_id,
                "target_case_id": choice.candidate.case_id,
                "relation_type": relation,
                "source_dataset": dataset,
                "match_method": match_method(_REF_METHODS[scheme], choice.rule),
                "confidence": choice.confidence,
            }
        )
    return pairs


def _resolve_late_batch(conn, ids, counts):
    with conn.cursor() as cursor:
        cursor.execute(_LATE_PAIRS_TABLE)
        cursor.execute("TRUNCATE late_binding_pair")
        cursor.execute(_LATE_PAIRS_BY_KEY, {"ids": ids})
        for pair in _late_ref_pairs(cursor, ids, counts):
            cursor.execute(_LATE_ADD_PAIR, pair)
        cursor.execute(_LATE_PAIR_COUNTS)
        for dataset, n in cursor.fetchall():
            counts[dataset]["matched"] += n
        cursor.execute(_LATE_INSERT)
        for (dataset,) in cursor.fetchall():
            counts[dataset]["resolved_inserted"] += 1
        cursor.execute(_LATE_COPY_MENTIONS)
        for (dataset,) in cursor.fetchall():
            counts[dataset]["mentions_copied"] += 1
    conn.commit()


def resolve_late(conn, case_ids: Sequence[int], batch_size: int = LATE_BATCH_SIZE):
    """Late binding for newly loaded cases (R2.9).

    For the unresolved rows of the link datasets whose target_ecli_raw,
    target_celex_raw or (target_ref_scheme, target_ref_raw) matches
    cases.ecli / cases.celex_id / case_identifier of ``case_ids``: insert the
    resolved row (same source, relation, dataset, extractor_version, weight,
    target_ref_raw; is_cross_jurisdiction from the cases' sources) and copy
    the unresolved row's mentions to it. Rows named by ECLI/CELEX keep their
    match_method and confidence. A reference (case number, application
    number, LJN) is chosen among every case carrying it with resolver's rules
    and the source's decision date, and records that choice
    ('case_number/cjeu_judgment', ...); without a choice it stays unresolved.
    The unresolved rows stay; running it again inserts nothing.

    One transaction per ``batch_size`` case ids. Returns {source_dataset:
    {matched, resolved_inserted, mentions_copied, ref_left_unresolved}}.
    """
    ids = sorted({int(i) for i in case_ids})
    counts = defaultdict(Counter)
    try:
        for start in range(0, len(ids), batch_size):
            _resolve_late_batch(conn, ids[start : start + batch_size], counts)
    except Exception:
        conn.rollback()
        raise
    for dataset, c in sorted(counts.items()):
        log.info("late binding %s: %s", dataset, dict(sorted(c.items())))
    return {dataset: {k: v for k, v in c.items() if v} for dataset, c in counts.items()}


def case_ids_in_range(conn, from_id: Optional[int], to_id: Optional[int]):
    """cases.id between from_id and to_id (inclusive; None = open)."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"""SELECT id FROM {SCHEMA}.cases
                 WHERE (%(lo)s::bigint IS NULL OR id >= %(lo)s::bigint)
                   AND (%(hi)s::bigint IS NULL OR id <= %(hi)s::bigint)
                 ORDER BY id""",
            {"lo": from_id, "hi": to_id},
        )
        ids = [row[0] for row in cursor.fetchall()]
    conn.rollback()
    return ids


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _connect(dsn_env):
    import psycopg2

    dsn = os.environ.get(dsn_env)
    if not dsn:
        raise SystemExit(f"environment variable {dsn_env} is not set")
    return psycopg2.connect(dsn)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load link artifacts; late binding (R2.9).")
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load", help="load JSONL link artifacts")
    load.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    load.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    load.add_argument("paths", nargs="+", help="artifact files")
    late = commands.add_parser("resolve-late", help="late binding for a range of cases.id")
    late.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    late.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    late.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    late.add_argument("--batch-size", type=int, default=LATE_BATCH_SIZE)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = _connect(args.dsn_env)
    try:
        if args.command == "load":
            result = {
                str(path): load_artifact(conn, path, batch_size=args.batch_size)
                for path in args.paths
            }
        else:
            ids = case_ids_in_range(conn, args.from_id, args.to_id)
            result = resolve_late(conn, ids, batch_size=args.batch_size)
    finally:
        conn.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
