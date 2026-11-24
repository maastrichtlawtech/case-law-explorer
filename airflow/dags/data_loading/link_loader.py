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
"""

import logging
from collections import Counter, defaultdict
from typing import Iterable

from data_extraction.linking.artifact import LinkRecord

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
    case named in records, in one query."""
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
        SELECT id, ecli, celex_id, item_id, sources
          FROM {SCHEMA}.cases
         WHERE ecli = ANY(%s) OR celex_id = ANY(%s) OR item_id = ANY(%s)
        """,
        (sorted(eclis), sorted(celexes), sorted(item_ids)),
    )
    for case_id, ecli, celex, item_id, sources in cursor.fetchall():
        value = (case_id, list(sources or []))
        if ecli in eclis:
            found[("ecli", ecli)] = value
        if celex in celexes:
            found[("celex", celex)] = value
        if item_id in item_ids:
            found[("item_id", item_id)] = value
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
_INSERT_VALUES = (
    "%(source_case_id)s, %(target_case_id)s, %(target_ecli_raw)s, %(target_celex_raw)s, "
    "%(target_ref_raw)s, %(target_ref_scheme)s, %(relation_type)s, %(source_dataset)s, "
    "%(weight)s, %(is_cross_jurisdiction)s, %(extractor_version)s, %(match_method)s, "
    "%(confidence)s"
)

# Resolved rows: one arbiter, named with its predicate so the statement works
# against the deployed (partial) and the local (plain) unique index alike.
_INSERT_RESOLVED = f"""
    INSERT INTO {SCHEMA}.case_citation ({_INSERT_COLUMNS})
    VALUES ({_INSERT_VALUES})
    ON CONFLICT (source_case_id, target_case_id, relation_type, source_dataset)
        WHERE target_case_id IS NOT NULL
    DO NOTHING
    RETURNING id
"""
# Unresolved rows can fall under two unique indexes at once (an ECLI and a
# case number), so any conflict means "already there".
_INSERT_UNRESOLVED = f"""
    INSERT INTO {SCHEMA}.case_citation ({_INSERT_COLUMNS})
    VALUES ({_INSERT_VALUES})
    ON CONFLICT DO NOTHING
    RETURNING id
"""

_FIND_RESOLVED = f"""
    SELECT id FROM {SCHEMA}.case_citation
     WHERE source_case_id = %(source_case_id)s AND target_case_id = %(target_case_id)s
       AND relation_type = %(relation_type)s AND source_dataset = %(source_dataset)s
"""
_FIND_UNRESOLVED = f"""
    SELECT id FROM {SCHEMA}.case_citation
     WHERE target_case_id IS NULL
       AND source_case_id = %(source_case_id)s
       AND relation_type = %(relation_type)s AND source_dataset = %(source_dataset)s
       AND (   (%(target_ecli_raw)s::text IS NOT NULL AND target_ecli_raw = %(target_ecli_raw)s)
            OR (%(target_celex_raw)s::text IS NOT NULL AND target_celex_raw = %(target_celex_raw)s)
            OR (%(target_ref_raw)s::text IS NOT NULL AND target_ref_raw = %(target_ref_raw)s
                AND target_ref_scheme = %(target_ref_scheme)s))
     ORDER BY id
     LIMIT 1
"""

_INSERT_MENTION = f"""
    INSERT INTO {SCHEMA}.case_citation_mention
        (citation_id, case_text_id, text_field, language, char_start, char_end,
         raw_text, context, segment_id, section, extractor_version)
    VALUES
        (%(citation_id)s,
         (SELECT id FROM {SCHEMA}.case_text
           WHERE case_id = %(source_case_id)s AND language = %(language)s
             AND source = %(text_source)s),
         %(text_field)s, %(language)s, %(char_start)s, %(char_end)s,
         %(raw_text)s, %(context)s,
         (SELECT id FROM {SCHEMA}.case_segment
           WHERE case_id = %(source_case_id)s AND segment_hash = %(segment_hash)s),
         %(section)s, %(extractor_version)s)
    ON CONFLICT DO NOTHING
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


def _insert(cursor, row, resolved):
    cursor.execute(_INSERT_RESOLVED if resolved else _INSERT_UNRESOLVED, row)
    returned = cursor.fetchone()
    if returned:
        return returned[0], True
    cursor.execute(_FIND_RESOLVED if resolved else _FIND_UNRESOLVED, row)
    existing = cursor.fetchone()
    if existing is None:
        # Conflicted on an index this lookup does not cover; leave it alone.
        return None, False
    return existing[0], False


def load_records(conn, records: Iterable[LinkRecord], batch_size: int = BATCH_SIZE):
    """Insert records batch by batch, one transaction per batch.

    Returns {source_dataset: Counter} with inserted, existing,
    inserted_unresolved, source_missing, target_unwritable and
    mentions_inserted.
    """
    counts = defaultdict(Counter)
    batch = []

    def flush():
        if not batch:
            return
        with conn.cursor() as cursor:
            found = _cases_by_key(cursor, batch)
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
                row = _row(record, source, target)
                citation_id, inserted = _insert(cursor, row, resolved=target is not None)
                if citation_id is None:
                    c["conflict_elsewhere"] += 1
                    continue
                if inserted:
                    c["inserted" if target is not None else "inserted_unresolved"] += 1
                else:
                    c["existing"] += 1
                for mention in record.mentions:
                    cursor.execute(
                        _INSERT_MENTION,
                        {
                            "citation_id": citation_id,
                            "source_case_id": row["source_case_id"],
                            "text_field": mention.text_field,
                            "language": mention.language,
                            "text_source": mention.text_source,
                            "char_start": mention.char_start,
                            "char_end": mention.char_end,
                            "raw_text": mention.raw_text,
                            "context": mention.context,
                            "segment_hash": mention.segment_hash,
                            "section": mention.section,
                            "extractor_version": record.extractor_version,
                        },
                    )
                    c["mentions_inserted"] += cursor.rowcount
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
