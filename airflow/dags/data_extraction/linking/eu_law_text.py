"""
EU-law references in stored texts -> law-reference artifact (roadmap R3.3, R3.4).

Shared by rs_eu_law (Rechtspraak texts, source_dataset 'rs_text_eu_law') and
echr_eu_law (HUDOC texts, 'echr_text_eu_law'). The scanning rules are in
eu_law.scan. Every reference becomes one record per (citing case, act,
article and paragraph): role 'cited', raw_scheme 'celex', raw_resource the
act's CELEX, raw_subdivision "4(3)" / "47" / None, with every mention (exact
offsets, the text as written, ~300 characters of context). The loader
resolves the act to ``legislation`` and the article to ``legal_provision``.

Reads only from the database it is given; never calls a remote service.
"""

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence

from data_extraction.linking import eu_law
from data_extraction.linking.artifact import ArtifactWriter, CaseKey
from data_extraction.linking.law_artifact import LawReferenceRecord, LawTarget
from data_extraction.linking.text_common import TextUnit, iter_case_batches, mention

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
EXTRACTOR_VERSION = "eu_law_text/1.0.0"
ROLE = "cited"
RAW_SCHEME = "celex"
BATCH_SIZE = 500


@dataclass(frozen=True)
class TextSource:
    key: CaseKey
    decided: Optional[date] = None


def records_for(
    source: TextSource, units: Iterable[TextUnit], dataset: str, profile: str
) -> List[LawReferenceRecord]:
    """One record per (act, subdivision) found in the source's texts."""
    merged: Dict[tuple, dict] = {}
    for unit in units:
        for hit in eu_law.scan(unit.text, source.decided, profile):
            key = (hit.celex, hit.raw_subdivision or "")
            entry = merged.get(key)
            if entry is None:
                entry = merged[key] = {"hit": hit, "mentions": []}
            elif hit.confidence > entry["hit"].confidence:
                entry["hit"] = hit
            entry["mentions"].append(mention(unit, hit.start, hit.end))
    records = []
    for (_celex, _sub), entry in sorted(merged.items()):
        hit = entry["hit"]
        seen, mentions = set(), []
        for m in sorted(
            entry["mentions"],
            key=lambda m: (m.text_source or "", m.language or "", m.text_field, m.char_start),
        ):
            mkey = (m.text_field, m.language, m.text_source, m.char_start, m.raw_text)
            if mkey not in seen:
                seen.add(mkey)
                mentions.append(m)
        record = LawReferenceRecord(
            source=source.key,
            target=LawTarget("celex", hit.celex, hit.alternatives),
            raw_scheme=RAW_SCHEME,
            raw_resource=hit.celex,
            raw_subdivision=hit.raw_subdivision,
            article=hit.article.article if hit.article else None,
            raw_reference=" ".join(mentions[0].raw_text.split()),
            role=ROLE,
            source_dataset=dataset,
            extractor_version=EXTRACTOR_VERSION,
            match_method=hit.method,
            confidence=hit.confidence,
            mentions=tuple(mentions),
        )
        record.validate()
        records.append(record)
    return records


def _ids_sql(text_source: str) -> str:
    return f"""
        SELECT DISTINCT case_id FROM {SCHEMA}.case_text
         WHERE source = '{text_source}'
           AND (fulltext IS NOT NULL OR summary IS NOT NULL) {{where}}
    """


_TEXTS_SQL = f"""
    SELECT c.id, c.ecli, c.celex_id, c.item_id, c.date_decision,
           ct.language, ct.fulltext, ct.summary
      FROM {SCHEMA}.case_text ct
      JOIN {SCHEMA}.cases c ON c.id = ct.case_id
     WHERE ct.source = %s AND ct.case_id = ANY(%s)
     ORDER BY c.id, ct.language, ct.id
"""


def extract_batch(cursor, case_ids: Sequence[int], text_source: str, dataset: str, profile: str):
    cursor.execute(_TEXTS_SQL, (text_source, list(case_ids)))
    sources: Dict[int, TextSource] = {}
    units: Dict[int, List[TextUnit]] = {}
    for case_id, ecli, celex, item_id, decided, language, fulltext, summary in cursor.fetchall():
        sources[case_id] = TextSource(
            CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None), decided
        )
        for field_name, text in (("fulltext", fulltext), ("summary", summary)):
            if text:
                units.setdefault(case_id, []).append(
                    TextUnit(text, field_name, language, text_source)
                )
    records = []
    for case_id in sorted(units):
        source = sources[case_id]
        if not (source.key.ecli or source.key.celex or source.key.item_id):
            continue
        records.extend(records_for(source, units[case_id], dataset, profile))
    return records


def extract(
    conn,
    text_source: str,
    dataset: str,
    profile: str,
    case_ids=None,
    id_range=None,
    out_path=None,
    batch_size=BATCH_SIZE,
):
    """Scan the texts of ``text_source`` for the given cases (all when both
    are None) and write the artifact to out_path (None: count only).
    Returns {"records": n, "mentions": n, "sources_with_refs": n}."""
    stats = Counter()
    with ArtifactWriter(out_path) as writer, conn.cursor() as cursor:
        for ids in iter_case_batches(
            conn,
            _ids_sql(text_source),
            case_ids=case_ids,
            id_range=id_range,
            batch_size=batch_size,
        ):
            records = extract_batch(cursor, ids, text_source, dataset, profile)
            conn.rollback()  # read-only; end the snapshot between batches
            stats["records"] += len(records)
            stats["mentions"] += sum(len(r.mentions) for r in records)
            stats["sources_with_refs"] += len({r.source for r in records})
            writer.write(records)
            log.info("%s: up to case %s, %s records", dataset, ids[-1], stats["records"])
    return dict(stats)
