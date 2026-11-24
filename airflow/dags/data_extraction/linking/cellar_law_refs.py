"""
Cellar law references stored as unresolved citations -> law-reference
artifact (roadmap R3.2).

The CJEU load (cjeu_loader SQL_CITE_OUT, and the migration before it) writes
every CELEX in Cellar's ``citing`` / ``work_cites_work`` fields to
case_citation with relation 'cites' and source_dataset 'cellar_sparql'.
Targets that are not case law never resolve (research 2026-11-24: 244,151
unresolved 'cites' rows; by CELEX sector 3 legislation 127,681, 1 treaties
106,308, 5 preparatory acts 5,423, 2 international agreements 2,828, 4 other
1,466, case law 124). This extractor reads those rows and writes one
law-reference record per (citing case, CELEX) with source_dataset
'cellar_law_ref', role 'cited', raw_scheme 'celex' and raw_resource the CELEX
as stored. The case_citation rows are left as they are.

  * sectors 1, 2, 3, 4 and 0 (consolidated texts) are law references
    (eu_law.LAW_SECTORS);
  * sector 5 (preparatory acts: COM documents, opinions) is skipped here: it
    belongs to Phase 4 (authority_document, R4.3); 6 (case law) stays a
    citation; 7, 8, 9, C, E are skipped (national measures, national case
    law, parliamentary questions, OJ C notices, EFTA) and counted;
  * a treaty-article CELEX ('12008E267') keeps the article as
    raw_subdivision / article (for legal_provision), and the act is also
    tried as '12008E/TXT' and '12008E'; a consolidated text
    ('02016R0679-20160504') is also tried as its base act ('32016R0679');
  * only relation 'cites': Cellar's inverse 'cited_by' rows name acts that
    cite the judgment, not acts the judgment relies on.

The 74k law references Cellar gives through its CDM legal predicates
(legal_resource, based_on_treaty, ...) are a different set: the CJEU load
writes them straight into case_law_reference with source_dataset
'cellar_sparql' (cjeu_loader SQL_LAWREF), with raw_resource and no
legislation_id. Resolving those existing rows is an update (roadmap Phase 6);
new ones are resolved at insert when LAW_REFERENCE_EXTRACTION_ENABLED is on
(cjeu_loader).

CLI: ``python -m data_extraction.linking.cellar_law_refs --dsn-env VAR
--from-id N --to-id M --out PATH [--load]`` (read-only unless --load).
"""

import logging
import sys
from collections import Counter
from typing import Dict, List, Sequence

from data_extraction.linking import eu_law
from data_extraction.linking.artifact import ArtifactWriter, CaseKey
from data_extraction.linking.law_artifact import LawReferenceRecord, LawTarget
from data_extraction.linking.text_common import iter_case_batches

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
DATASET = "cellar_law_ref"
DATASETS = (DATASET,)
EXTRACTOR_VERSION = "cellar_law_refs/1.0.0"
CELLAR_DATASET = "cellar_sparql"
RELATION = "cites"
ROLE = "cited"
BATCH_SIZE = 1000

_FILTER = f"""
       cc.source_dataset = '{CELLAR_DATASET}' AND cc.relation_type = '{RELATION}'
   AND cc.target_case_id IS NULL AND cc.target_celex_raw IS NOT NULL
   AND cc.source_case_id IS NOT NULL
"""
_IDS_SQL = f"""
    SELECT case_id FROM (
        SELECT DISTINCT cc.source_case_id AS case_id
          FROM {SCHEMA}.case_citation cc
         WHERE {_FILTER}
    ) s WHERE TRUE {{where}}
"""
_ROWS_SQL = f"""
    SELECT cc.source_case_id, c.ecli, c.celex_id, c.item_id, cc.target_celex_raw
      FROM {SCHEMA}.case_citation cc
      JOIN {SCHEMA}.cases c ON c.id = cc.source_case_id
     WHERE {_FILTER} AND cc.source_case_id = ANY(%s)
     ORDER BY cc.source_case_id, cc.target_celex_raw
"""


def record_for(source: CaseKey, raw_celex: str, stats: Counter):
    """The record for one stored CELEX, or None (counted in stats by reason)."""
    raw = (raw_celex or "").strip()
    sector = eu_law.celex_sector(raw)
    target = eu_law.cellar_target(raw)
    if target is None:
        stats[f"skipped_sector_{sector or 'none'}"] += 1
        return None
    stats[f"sector_{target.sector}"] += 1
    return LawReferenceRecord(
        source=source,
        target=LawTarget("celex", target.identifier, target.alternatives),
        raw_scheme="celex",
        raw_resource=raw,
        raw_subdivision=target.article,
        article=target.article,
        raw_reference=raw,
        role=ROLE,
        source_dataset=DATASET,
        extractor_version=EXTRACTOR_VERSION,
        match_method="celex_metadata",
        confidence=1.0,
    )


def records_from_rows(rows, stats: Counter) -> List[LawReferenceRecord]:
    """rows: (case_id, ecli, celex, item_id, target_celex_raw); one record per
    (source, natural key)."""
    out: Dict[tuple, LawReferenceRecord] = {}
    for _case_id, ecli, celex, item_id, raw in rows:
        if not (ecli or celex or item_id):
            stats["source_without_key"] += 1
            continue
        source = CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None)
        record = record_for(source, raw, stats)
        if record is not None:
            out.setdefault(record.natural_key, record)
    return list(out.values())


def extract_batch(cursor, case_ids: Sequence[int], stats: Counter):
    cursor.execute(_ROWS_SQL, (list(case_ids),))
    return records_from_rows(cursor.fetchall(), stats)


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size=BATCH_SIZE):
    """Write the cellar_law_ref artifact for the given source cases (all when
    both are None). Returns {"records": n, ...counts by sector / skip reason}."""
    stats = Counter()
    with ArtifactWriter(out_path) as writer, conn.cursor() as cursor:
        for ids in iter_case_batches(
            conn, _IDS_SQL, case_ids=case_ids, id_range=id_range, batch_size=batch_size
        ):
            records = extract_batch(cursor, ids, stats)
            conn.rollback()  # read-only; end the snapshot between batches
            stats["records"] += len(records)
            writer.write(records)
            log.info("cellar_law_refs: up to case %s, %s records", ids[-1], stats["records"])
    return dict(stats)


def main(argv=None):
    from data_loading.law_reference_loader import run_cli

    return run_cli(extract, "Cellar law references from unresolved citations (R3.2)", argv)


if __name__ == "__main__":
    sys.exit(main())
