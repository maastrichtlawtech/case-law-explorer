"""
Cited authorities in judgment texts (roadmap R4.1, R4.2, R4.4, R4.5).

Scans the stored texts of Rechtspraak decisions (case_text source
'RECHTSPRAAK', fulltext and summary) and of ECtHR documents (case_text source
'HUDOC', fulltext and summary; the secondary HUDOC variants are not scanned)
with the patterns of authority_patterns.py and writes one authority record per
occurrence:

    rs_text_authority     references in Rechtspraak texts
    echr_text_authority   references in HUDOC texts

What is found (see authority_patterns for the identifiers): Dutch
parliamentary papers (Kamerstukken, Handelingen), Staatsblad / Staatscourant /
Tractatenblad numbers (AUTHORITY_NL_OFFICIAL_PUBLICATIONS, default on), the
Vreemdelingencirculaire 2000, WBV and decrees cited by date and reference
number, full ECLIs of courts outside the three collections, UN treaty body
documents and communications, and Council of Europe documents (Venice
Commission, CPT, GRECO, ECRI, Committee of Ministers, Commissioner for Human
Rights). Every pattern runs on both corpora.

Each record names the citing case by ECLI (else CELEX, else item_id), the
document by (kind, identifier_scheme, identifier) with the attributes the
identifier gives, and the occurrence by its exact offsets, the text as written
and ~300 characters of context. Reads only from the database it is given;
never calls a remote service.

CLI (backfill over a cases.id range; the connection is read-only):
    python -m data_extraction.linking.authority_text --dsn-env VAR \\
        --corpus rs|echr --from-id N --to-id M --out PATH
"""

import logging
from collections import Counter
from typing import Iterable, List, Optional, Sequence

from data_extraction.linking import authority_patterns
from data_extraction.linking.artifact import CaseKey
from data_extraction.linking.authority_artifact import (
    AuthorityMention,
    AuthorityRecord,
    AuthorityWriter,
)
from data_extraction.linking.text_common import (
    BATCH_SIZE,
    cli_args,
    connect,
    context,
    env_flag,
    iter_case_batches,
)

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
EXTRACTOR_VERSION = "authority_text/1.0.0"
OFFICIAL_PUBLICATIONS_FLAG = "AUTHORITY_NL_OFFICIAL_PUBLICATIONS"

CORPORA = {
    # corpus: (case_text.source, source_dataset)
    "rs": ("RECHTSPRAAK", "rs_text_authority"),
    "echr": ("HUDOC", "echr_text_authority"),
}
DATASETS = tuple(dataset for _source, dataset in CORPORA.values())


def scan_groups(official_publications: Optional[bool] = None) -> tuple:
    """The pattern groups to run; Staatsblad/Staatscourant/Tractatenblad
    numbers only with AUTHORITY_NL_OFFICIAL_PUBLICATIONS (default on)."""
    if official_publications is None:
        official_publications = env_flag(OFFICIAL_PUBLICATIONS_FLAG, True)
    return tuple(
        g for g in authority_patterns.GROUPS if official_publications or g != "nl_official"
    )


def records_for_text(
    source: CaseKey,
    text: str,
    text_field: str,
    language: Optional[str],
    text_source: str,
    dataset: str,
    groups: Sequence[str] = authority_patterns.GROUPS,
    stats: Optional[Counter] = None,
) -> List[AuthorityRecord]:
    """Pure entry point: one stored text -> one record per reference."""
    records = []
    for hit in authority_patterns.scan(text, groups):
        if stats is not None:
            stats[f"hits_{hit.doc.kind}"] += 1
        record = AuthorityRecord(
            source=source,
            authority=hit.doc,
            raw_reference=text[hit.start : hit.end],
            source_dataset=dataset,
            extractor_version=EXTRACTOR_VERSION,
            mention=AuthorityMention(
                text_field=text_field,
                language=language,
                text_source=text_source,
                char_start=hit.start,
                char_end=hit.end,
                context=context(text, hit.start, hit.end, collapse_space=True),
            ),
            pinpoint=hit.pinpoint,
            match_method=hit.method,
            confidence=hit.confidence,
        )
        record.validate()
        records.append(record)
    return records


_CASE_IDS = """
    SELECT DISTINCT case_id FROM {schema}.case_text
     WHERE source = '{source}' AND (fulltext IS NOT NULL OR summary IS NOT NULL) {{where}}
"""
_CASE_TEXTS = f"""
    SELECT c.id, c.ecli, c.celex_id, c.item_id, ct.language, ct.fulltext, ct.summary
      FROM {SCHEMA}.case_text ct
      JOIN {SCHEMA}.cases c ON c.id = ct.case_id
     WHERE ct.source = %(source)s AND ct.case_id = ANY(%(ids)s)
     ORDER BY c.id, ct.language, ct.id
"""


def extract(
    conn,
    corpus: str,
    case_ids: Optional[Iterable[int]] = None,
    id_range=None,
    out_path=None,
    batch_size: int = BATCH_SIZE,
    groups: Optional[Sequence[str]] = None,
):
    """Scan the texts of one corpus for the given cases (all when both
    selectors are None) and write the artifact. Returns (records, stats)."""
    text_source, dataset = CORPORA[corpus]
    groups = scan_groups() if groups is None else tuple(groups)
    stats = Counter()
    ids_sql = _CASE_IDS.format(schema=SCHEMA, source=text_source)
    with AuthorityWriter(out_path) as writer:
        for ids in iter_case_batches(
            conn, ids_sql, case_ids=case_ids, id_range=id_range, batch_size=batch_size
        ):
            with conn.cursor() as cursor:
                cursor.execute(_CASE_TEXTS, {"source": text_source, "ids": ids})
                rows = cursor.fetchall()
            conn.rollback()  # read-only; end the snapshot between batches
            records, seen = [], set()
            for _case_id, ecli, celex, item_id, language, fulltext, summary in rows:
                key = CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None)
                if not (key.ecli or key.celex or key.item_id):
                    stats["texts_without_key"] += 1
                    continue
                seen.add(key)
                for field, text in (("fulltext", fulltext), ("summary", summary)):
                    if text:
                        stats["texts"] += 1
                        records.extend(
                            records_for_text(
                                key, text, field, language, text_source, dataset, groups, stats
                            )
                        )
            stats["sources"] += len(seen)
            writer.write(records)
    stats["records"] = writer.count
    log.info("authority_text %s: %s", corpus, dict(sorted(stats.items())))
    return writer.count, stats


def main(argv=None):
    def extra(parser):
        parser.add_argument("--corpus", required=True, choices=sorted(CORPORA))

    args = cli_args(__doc__.split("\n\n")[0].strip(), argv, extra=extra)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = connect(args.dsn_env)
    try:
        conn.set_session(readonly=True)
        id_range = None
        if args.from_id is not None or args.to_id is not None:
            id_range = (args.from_id, args.to_id)
        written, stats = extract(
            conn,
            args.corpus,
            case_ids=args.case_id,
            id_range=id_range,
            out_path=args.out,
            batch_size=args.batch_size,
        )
    finally:
        conn.close()
    print(f"{written} records -> {args.out}")
    for key, value in sorted(stats.items()):
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
