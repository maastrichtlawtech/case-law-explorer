"""
Advocate General's opinion -> the judgment it was delivered in (R2.4).

An opinion's CELEX number is its case's number with type letters CC
(62012CC0199); the judgment in the same case is CJ (62012CJ0199), or CO when
the case ended with an order. Rules, in order:

    1. CELEX CC -> CJ, a case with exactly that CELEX      match_method 'celex'
    2. the first judgment (CJ/TJ) carrying one of the opinion's case numbers
       (case_identifier 'cjeu_case_number') dated on or after the opinion
                                                             match_method 'case_number'
    3. CELEX CC -> CO                                        match_method 'celex'

Rule 2 comes before the CO swap (the roadmap lists CO second): in joined
cases the judgment is filed under the lead number, and a non-lead member's
number can carry an order of its own (research rs/allres_nums.txt: the
opinions 62000CC0205, ...0211, ...0213, ...0217, ...0219 in Aalborg Portland
have a CO with their number, while the judgment is 62000CJ0204). A judgment
that carries the case number is better evidence than an order that shares
it; the CO swap is the last resort, with confidence 0.8.

A target dated before the opinion is refused (an opinion is delivered before
its judgment), and the next rule is tried. Rule 2 needs the opinion's date;
when the opinion's case numbers lead to different first judgments, or one
case number has several judgments on its first date, it is skipped
(never guessed). A suffixed CELEX ('62019CC0001(01)') is tried with the
same suffix first, then without it.

Research (2026-11-24): CC -> CJ matches 11,021 of 11,446 opinions, CC -> CO
103 more; 20/20 checked.

relation 'opinion_of' (opinion -> judgment), source_dataset 'cjeu_ag_link'.
There is no text line, so the records carry no mentions.

Out of scope: cjeu_ag_opinion.parent_case_id (set on 51 rows) is not updated;
filling it from this artifact would be an update of existing data, which
needs its own gate.

CLI:
    python -m data_extraction.linking.ag_opinions --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH
"""

import argparse
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from data_extraction.linking import resolver
from data_extraction.linking.artifact import CaseKey, LinkRecord, write_jsonl

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
SOURCE_DATASET = "cjeu_ag_link"
EXTRACTOR_VERSION = "ag_opinions/1.0.0"
RELATION = "opinion_of"
BATCH_SIZE = 500

CONFIDENCE = {"celex_cj": 0.98, "case_number": 0.85, "celex_co": 0.8}

_OPINION_CELEX = re.compile(r"^(6\d{4})CC(\d{4})(\(\d{2}\))?$")


@dataclass(frozen=True)
class Document:
    case_id: int
    ecli: Optional[str]
    celex: Optional[str]
    decided: Optional[date]

    def key(self):
        if self.ecli:
            return CaseKey(ecli=self.ecli)
        if self.celex:
            return CaseKey(celex=self.celex)
        return None


@dataclass(frozen=True)
class Opinion(Document):
    case_numbers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Resolution:
    target: Document
    method: str  # celex | case_number
    rule: str  # celex_cj | celex_co | case_number
    confidence: float


def swapped_celex(celex: Optional[str], letters: str) -> List[str]:
    """'62012CC0199' -> ['62012CJ0199'] for letters 'CJ'; a suffixed CELEX
    gives the suffixed form first, then the plain one."""
    match = _OPINION_CELEX.match((celex or "").strip().upper())
    if not match:
        return []
    head, number, suffix = match.groups()
    plain = f"{head}{letters}{number}"
    return [plain + suffix, plain] if suffix else [plain]


def _not_before(target: Document, opinion: Opinion):
    return target.decided is None or opinion.decided is None or target.decided >= opinion.decided


def _swap(opinion, by_celex, letters, rule):
    """(Resolution | None, refused?) for one CELEX swap."""
    refused = False
    for celex in swapped_celex(opinion.celex, letters):
        target = by_celex.get(celex)
        if target is None or target.case_id == opinion.case_id:
            continue
        if not _not_before(target, opinion):
            refused = True
            continue
        return Resolution(target, "celex", rule, CONFIDENCE[rule]), refused
    return None, refused


def _by_case_number(opinion, by_case_number):
    """(Resolution | None, reason) for the first judgment on or after the
    opinion carrying one of its case numbers."""
    if not opinion.case_numbers:
        return None, "no_case_number"
    if opinion.decided is None:
        return None, "no_opinion_date"
    firsts = set()
    for number in opinion.case_numbers:
        judgments = [
            c
            for c in by_case_number.get(number, ())
            if c.kind == resolver.CJEU_JUDGMENT
            and c.case_id != opinion.case_id
            and c.date is not None
            and c.date >= opinion.decided
        ]
        if not judgments:
            continue
        earliest = min(c.date for c in judgments)
        same_day = {c.case_id: c for c in judgments if c.date == earliest}
        if len(same_day) > 1:
            return None, "several_judgments_same_day"
        firsts.add(next(iter(same_day.values())))
    if not firsts:
        return None, "no_judgment"
    if len({c.case_id for c in firsts}) > 1:
        return None, "case_numbers_disagree"
    chosen = firsts.pop()
    target = Document(chosen.case_id, chosen.ecli, chosen.celex, chosen.date)
    return Resolution(target, "case_number", "case_number", CONFIDENCE["case_number"]), "ok"


def resolve_opinion(
    opinion: Opinion,
    by_celex: Dict[str, Document],
    by_case_number: Dict[str, Sequence[resolver.Candidate]],
) -> Tuple[Optional[Resolution], str]:
    """Pick the judgment of one opinion. by_celex maps CELEX -> Document for
    the swapped CELEX numbers; by_case_number maps a normalised case number ->
    resolver.Candidates. Returns (Resolution, 'ok') or (None, reason)."""
    resolution, refused_cj = _swap(opinion, by_celex, "CJ", "celex_cj")
    if resolution is not None:
        return resolution, "ok"
    resolution, number_reason = _by_case_number(opinion, by_case_number)
    if resolution is not None:
        return resolution, "ok"
    if number_reason in ("several_judgments_same_day", "case_numbers_disagree"):
        return None, number_reason
    resolution, refused_co = _swap(opinion, by_celex, "CO", "celex_co")
    if resolution is not None:
        return resolution, "ok"
    if refused_cj or refused_co:
        return None, "dated_before_opinion"
    return None, number_reason


def record_for(opinion: Opinion, resolution: Resolution) -> Optional[LinkRecord]:
    source, target = opinion.key(), resolution.target.key()
    if source is None or target is None or source == target:
        return None
    return LinkRecord(
        source=source,
        target=target,
        relation_type=RELATION,
        source_dataset=SOURCE_DATASET,
        extractor_version=EXTRACTOR_VERSION,
        match_method=resolution.method,
        confidence=resolution.confidence,
    )


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------

# Opinions: cases with an opinion CELEX, and every cjeu_ag_opinion row
# (some opinions lost their CELEX in loading and have only a case number).
_OPINIONS = f"""
    SELECT c.id, c.ecli, c.celex_id, coalesce(a.delivered_date, c.date_decision),
           ARRAY(SELECT ci.value_normalized FROM {SCHEMA}.case_identifier ci
                  WHERE ci.case_id = c.id AND ci.scheme = 'cjeu_case_number'
                  ORDER BY ci.value_normalized)
      FROM {SCHEMA}.cases c
      LEFT JOIN {SCHEMA}.cjeu_ag_opinion a ON a.case_id = c.id
     WHERE (a.case_id IS NOT NULL OR c.celex_id ~ '^6[0-9]{{4}}CC[0-9]{{4}}')
       AND c.id > %(after)s
       AND (%(from_id)s::bigint IS NULL OR c.id >= %(from_id)s)
       AND (%(to_id)s::bigint IS NULL OR c.id <= %(to_id)s)
       AND (%(case_ids)s::bigint[] IS NULL OR c.id = ANY(%(case_ids)s))
     ORDER BY c.id
     LIMIT %(limit)s
"""

_BY_CELEX = f"""
    SELECT id, ecli, celex_id, date_decision FROM {SCHEMA}.cases WHERE celex_id = ANY(%s)
"""


def iter_opinions(conn, case_ids=None, id_range=None, batch_size=BATCH_SIZE):
    from_id, to_id = id_range if id_range else (None, None)
    after = 0
    while True:
        with conn.cursor() as cursor:
            cursor.execute(
                _OPINIONS,
                {
                    "after": after,
                    "from_id": from_id,
                    "to_id": to_id,
                    "case_ids": list(case_ids) if case_ids is not None else None,
                    "limit": batch_size,
                },
            )
            rows = cursor.fetchall()
        if not rows:
            return
        after = rows[-1][0]
        yield [
            Opinion(case_id, ecli, celex, decided, tuple(numbers or ()))
            for case_id, ecli, celex, decided, numbers in rows
        ]


def links_for_batch(cursor, opinions: Iterable[Opinion], stats: Counter) -> List[LinkRecord]:
    opinions = list(opinions)
    wanted = sorted(
        {c for o in opinions for letters in ("CJ", "CO") for c in swapped_celex(o.celex, letters)}
    )
    by_celex = {}
    if wanted:
        cursor.execute(_BY_CELEX, (wanted,))
        by_celex = {row[2]: Document(*row) for row in cursor.fetchall()}
    # Case numbers only for the opinions the CC -> CJ swap cannot serve.
    numbers = sorted(
        {
            n
            for o in opinions
            if _swap(o, by_celex, "CJ", "celex_cj")[0] is None
            for n in o.case_numbers
        }
    )
    by_number = resolver.fetch_candidates(cursor, "cjeu_case_number", numbers)
    records = []
    for opinion in opinions:
        stats["opinions"] += 1
        resolution, reason = resolve_opinion(opinion, by_celex, by_number)
        if resolution is None:
            stats[reason] += 1
            continue
        record = record_for(opinion, resolution)
        if record is None:
            stats["no_natural_key"] += 1
            continue
        stats[f"matched_{resolution.rule}"] += 1
        records.append(record)
    return records


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size: int = BATCH_SIZE):
    """Write the artifact for the opinions selected by case_ids or id_range
    (cases.id, inclusive); returns (records written, stats)."""
    stats: Counter = Counter()
    records: List[LinkRecord] = []
    for batch in iter_opinions(conn, case_ids, id_range, batch_size):
        with conn.cursor() as cursor:
            records.extend(links_for_batch(cursor, batch, stats))
    written = write_jsonl(records, out_path) if out_path else len(records)
    stats["records"] = written
    log.info("ag_opinions: %s", dict(sorted(stats.items())))
    return written, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("--from-id", type=int)
    parser.add_argument("--to-id", type=int)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    import psycopg2

    logging.basicConfig(level=logging.INFO)
    conn = psycopg2.connect(os.environ[args.dsn_env])
    try:
        conn.set_session(readonly=True)
        id_range = (args.from_id, args.to_id) if args.from_id or args.to_id else None
        written, stats = extract(conn, id_range=id_range, out_path=args.out)
    finally:
        conn.close()
    print(f"{written} records -> {args.out}; {dict(sorted(stats.items()))}")


if __name__ == "__main__":
    main()
