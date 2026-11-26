"""
ECtHR Convention articles -> provisions of the ECHR and its Protocols (R3.7).

echr_document_article (929k rows, loaded by the migration from legacy
echr_document_article; the weekly ECHR loader does not fill it) holds, per
HUDOC document, the articles applied, violated and not violated, as HUDOC
article codes:

    '6'        Article 6 of the Convention
    '6-1'      Article 6 § 1
    '6-3-c'    Article 6 § 3 (c)
    'P1-1'     Protocol No. 1, Article 1
    'P1-1-1'   Protocol No. 1, Article 1 § 1
    '14+8'     Article 14 taken with Article 8 (one reference to each)

Each code (each part of a '+' code) becomes one record: the act (the
Convention, CETS 005, or the Protocol, by the curated fixture's protocol
numbers), article and paragraph ('3(c)' for '6-3-c'), role = the row's kind
(applied | violation | nonviolation), raw_subdivision = the part, raw_reference
= the code as stored. Codes are matched case-insensitively with surrounding
space removed. A part that is not of these forms, or names a protocol the
fixture does not hold, is counted (``unparsed``, ``unknown_protocol``) and
left out.

HUDOC language versions and related documents of one case share a cases row;
their codes are merged per case, so a case refers to a provision once per role.
The source is the case's ECLI, else its item_id.

source_dataset 'echr_article'. Read-only.

CLI:
    python -m data_extraction.legislation.echr_articles --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from data_extraction.legislation.acts import echr_protocols
from data_extraction.legislation.law_reference import LawReferenceRecord
from data_extraction.linking.artifact import ArtifactWriter
from data_extraction.linking.text_common import (
    cli_args,
    connect,
    iter_case_batches,
    source_key,
)

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
SOURCE_DATASET = "echr_article"
EXTRACTOR_VERSION = "echr_article/1.0.0"
RAW_SCHEME = "echr_article"
ROLES = ("applied", "violation", "nonviolation")
BATCH_SIZE = 2000

_PART = re.compile(
    r"^(?:P(?P<protocol>\d+)-)?(?P<article>\d+)(?:-(?P<paragraph>\d+)(?:-(?P<sub>[A-Z]|\d+))?)?$"
)


@dataclass(frozen=True)
class ArticleRef:
    protocol: int  # 0 = the Convention
    article: str
    paragraph: Optional[str]
    part: str  # the normalised part of the code, e.g. 'P1-1'


def parse_article_code(code) -> Tuple[List[ArticleRef], List[str]]:
    """(references, parts that did not parse) for one stored article code."""
    refs, bad = [], []
    text = re.sub(r"\s+", "", str(code or "")).upper()
    for part in (p for p in text.split("+") if p) if text else ():
        match = _PART.match(part)
        if not match:
            bad.append(part)
            continue
        paragraph = match["paragraph"]
        if paragraph is not None:
            paragraph = str(int(paragraph))
            if match["sub"] is not None:
                sub = match["sub"]
                paragraph += f"({sub.lower() if sub.isalpha() else int(sub)})"
        refs.append(
            ArticleRef(
                protocol=int(match["protocol"]) if match["protocol"] else 0,
                article=str(int(match["article"])),
                paragraph=paragraph,
                part=part,
            )
        )
    if not text:
        bad.append(str(code))
    return refs, bad


# Cases with at least one HUDOC document. Cases without article rows give no
# records; the per-batch query below finds out.
_IDS = f"""
    SELECT DISTINCT case_id FROM {SCHEMA}.echr_document
     WHERE case_id IS NOT NULL {{where}}
"""

_ROWS = f"""
    SELECT d.case_id, c.ecli, c.item_id, a.kind, a.article_code
      FROM {SCHEMA}.echr_document d
      JOIN {SCHEMA}.echr_document_article a ON a.item_id = d.item_id
      JOIN {SCHEMA}.cases c ON c.id = d.case_id
     WHERE d.case_id = ANY(%(ids)s)
    UNION ALL
    SELECT d.case_id, c.ecli, c.item_id, src.kind, btrim(code) AS article_code
      FROM {SCHEMA}.echr_document d
      JOIN {SCHEMA}.cases c ON c.id = d.case_id
      CROSS JOIN LATERAL (
          VALUES ('applied', d.article),
                 ('violation', d.violation),
                 ('nonviolation', d.nonviolation)
      ) AS src(kind, raw_list)
      CROSS JOIN LATERAL unnest(regexp_split_to_array(COALESCE(src.raw_list, ''), ';')) AS code
     WHERE d.case_id = ANY(%(ids)s)
       AND btrim(code) <> ''
       AND NOT EXISTS (
           SELECT 1 FROM {SCHEMA}.echr_document_article a
            WHERE a.item_id = d.item_id
       )
"""


def records_for_rows(rows, protocols, stats: Counter) -> List[LawReferenceRecord]:
    """One record per (case, act, article, paragraph, role); rows are
    (case_id, ecli, item_id, kind, article_code)."""
    chosen: Dict[tuple, LawReferenceRecord] = {}
    for case_id, ecli, item_id, kind, code in rows:
        stats["rows"] += 1
        if kind not in ROLES:
            stats["unknown_kind"] += 1
            continue
        if not (ecli or item_id):
            stats["no_natural_key"] += 1
            continue
        refs, bad = parse_article_code(code)
        stats["unparsed"] += len(bad)
        for part in bad:
            log.debug("echr_article: unparsed article code part %r of %r", part, code)
        for ref in refs:
            act = protocols.get(ref.protocol)
            if act is None:
                stats["unknown_protocol"] += 1
                continue
            record = LawReferenceRecord(
                source=source_key(ecli=ecli, item_id=None if ecli else item_id),
                scheme=act.scheme,
                identifier=act.identifier,
                role=kind,
                source_dataset=SOURCE_DATASET,
                extractor_version=EXTRACTOR_VERSION,
                article=ref.article,
                paragraph=ref.paragraph,
                raw_scheme=RAW_SCHEME,
                raw_subdivision=ref.part,
                raw_reference=str(code).strip(),
            )
            key = (case_id, record.act_key, record.provision_key, kind)
            previous = chosen.get(key)
            # Several codes for one provision (e.g. '14+8' and '8'): keep the
            # smallest code, so the output does not depend on row order.
            if previous is None or (record.raw_reference, record.raw_subdivision) < (
                previous.raw_reference,
                previous.raw_subdivision,
            ):
                if previous is not None:
                    stats["merged"] += 1
                chosen[key] = record
            else:
                stats["merged"] += 1
    return list(chosen.values())


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size: int = BATCH_SIZE):
    """Write the echr_article artifact for the selected cases (cases.id);
    returns (records written, stats)."""
    stats: Counter = Counter()
    protocols = echr_protocols()
    with ArtifactWriter(out_path) as writer:
        if case_ids is None or case_ids:
            batches = iter_case_batches(
                conn, _IDS, case_ids=case_ids, id_range=id_range, batch_size=batch_size
            )
            for ids in batches:
                with conn.cursor() as cursor:
                    cursor.execute(_ROWS, {"ids": ids})
                    rows = cursor.fetchall()
                conn.rollback()  # read only; end the snapshot between batches
                writer.write(records_for_rows(rows, protocols, stats))
    stats["records"] = writer.count
    log.info("echr_article: %s", dict(sorted(stats.items())))
    return writer.count, stats


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
