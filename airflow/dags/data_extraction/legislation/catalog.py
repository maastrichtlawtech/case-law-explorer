"""
Acts for the EU law the database refers to (roadmap R3.1).

Reads, for the selected source cases, every CELEX number of sectors 1-3 that
Cellar data names:

    case_citation.target_celex_raw   unresolved Cellar citations whose target
                                     is legislation or a treaty, not a case
                                     (research 2026-11-24: 243,706 rows;
                                     sector 3 127,681, 1 106,308, 2 2,828)
    case_law_reference.raw_resource  rows with raw_scheme 'celex' (the CDM
                                     legal-resource predicates, cellar_sparql)

maps each to the act it names (celex.parse_celex: ``12008E267`` -> ``12008E``)
and writes one act record per distinct act: scheme 'celex', the CELEX number,
document type from the type letter, enacted_year from the CELEX year, title
NULL (the database holds no titles for them). The curated acts
(external_acts.json) come first in the file, so the treaties, the Charter and
the conventions get their titles and aliases whatever Cellar refers to.

Values that are not CELEX numbers of sectors 1-3 are counted, by sector
(``skipped_sector_<s>``) or as ``unparsed``, and left out.

Read-only; the loader (data_loading/legislation_loader.py) inserts the acts.

CLI:
    python -m data_extraction.legislation.catalog --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH
"""

import logging
from collections import Counter
from typing import Dict, Iterable, Optional, Sequence, Tuple

from data_extraction.legislation import acts
from data_extraction.legislation.celex import parse_celex, sector
from data_extraction.linking.text_common import cli_args, connect, iter_case_batches

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
EXTRACTOR_VERSION = "legislation_catalog/1.0.0"
BATCH_SIZE = 5000
# CELEX sectors that are not legislation or treaties (0 consolidated texts, 4
# complementary legislation, 5 preparatory acts, 6 case law, 7 national
# transposition, 8 national case law, 9 parliamentary questions, C OJ C
# notices, E EFTA).
OTHER_SECTORS = frozenset("0456789CE")

# Cases that have anything to read: an unresolved Cellar citation or a CELEX
# law reference. Two index scans (case_citation's source / case_law_reference's
# case_id indexes) instead of a pass over every case.
_IDS = f"""
    SELECT case_id FROM (
        SELECT source_case_id AS case_id FROM {SCHEMA}.case_citation
         WHERE target_case_id IS NULL AND target_celex_raw IS NOT NULL
        UNION
        SELECT case_id FROM {SCHEMA}.case_law_reference WHERE raw_scheme = 'celex'
    ) ids WHERE true {{where}}
"""

_VALUES = f"""
    SELECT target_celex_raw FROM {SCHEMA}.case_citation
     WHERE source_case_id = ANY(%(ids)s)
       AND target_case_id IS NULL AND target_celex_raw IS NOT NULL
    UNION
    SELECT raw_resource FROM {SCHEMA}.case_law_reference
     WHERE case_id = ANY(%(ids)s) AND raw_scheme = 'celex' AND raw_resource IS NOT NULL
"""


def act_for(value, stats: Counter) -> Optional[acts.ActRecord]:
    """The act record for one referenced CELEX value, or None (counted)."""
    parsed = parse_celex(value)
    if parsed is None:
        first = sector(value)
        if first is not None and first in OTHER_SECTORS:
            stats[f"skipped_sector_{first}"] += 1
        else:
            stats["unparsed"] += 1
        return None
    stats[f"sector_{parsed.sector}"] += 1
    if parsed.subdivision:
        stats["with_subdivision"] += 1
    return acts.ActRecord(
        scheme="celex",
        identifier=parsed.act,
        jurisdiction="EU",
        source_dataset=acts.DATASET_CELLAR,
        extractor_version=EXTRACTOR_VERSION,
        document_type=parsed.document_type,
        enacted_year=parsed.year,
    )


def referenced_values(conn, case_ids=None, id_range=None, batch_size: int = BATCH_SIZE):
    """Yield the distinct referenced values per batch of source cases."""
    batches = iter_case_batches(
        conn, _IDS, case_ids=case_ids, id_range=id_range, batch_size=batch_size
    )
    for ids in batches:
        with conn.cursor() as cursor:
            cursor.execute(_VALUES, {"ids": ids})
            values = [row[0] for row in cursor.fetchall()]
        conn.rollback()  # read only; end the snapshot between batches
        yield values


def cellar_acts(values: Iterable[str], stats: Counter) -> Dict[Tuple[str, str], acts.ActRecord]:
    found: Dict[Tuple[str, str], acts.ActRecord] = {}
    for value in values:
        record = act_for(value, stats)
        if record is not None:
            found.setdefault(record.key, record)
    return found


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size: int = BATCH_SIZE):
    """Write the legislation artifact (curated acts, then the CELEX acts the
    selected cases refer to that the fixture does not hold); returns
    (records written, stats). case_ids=[] writes the curated acts only."""
    stats: Counter = Counter()
    curated = acts.curated_acts()
    found: Dict[Tuple[str, str], acts.ActRecord] = {}
    if case_ids is None or case_ids:
        for values in referenced_values(conn, case_ids, id_range, batch_size):
            stats["values"] += len(values)
            for key, record in cellar_acts(values, stats).items():
                found.setdefault(key, record)
    curated_keys = {r.key for r in curated}
    stats["acts_in_fixture_referenced"] = len(curated_keys & set(found))
    cellar = [r for k, r in found.items() if k not in curated_keys]
    written = acts.write_acts([curated, cellar], out_path)
    stats["curated"] = len(curated)
    stats["cellar_acts"] = len(cellar)
    stats["records"] = written
    log.info("legislation catalog: %s", dict(sorted(stats.items())))
    return written, stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = cli_args(__doc__.split("\n\n")[0].strip(), argv)
    logging.basicConfig(level=logging.INFO)
    conn = connect(args.dsn_env)
    try:
        conn.set_session(readonly=True)
        id_range = None
        if args.from_id is not None or args.to_id is not None:
            id_range = (args.from_id, args.to_id)
        written, stats = extract(
            conn,
            case_ids=args.case_id,
            id_range=id_range,
            out_path=args.out,
            batch_size=args.batch_size,
        )
    finally:
        conn.close()
    print(f"{written} records -> {args.out}; {dict(sorted(stats.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
