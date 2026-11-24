"""
Where a Rechtspraak decision was published and who annotated it (roadmap
R4.6, Rechtspraak part). Source dataset 'rs_publication'.

Reads, for each RS decision:

  * rs_document_publication (1.86M rows from the July 2026 migration): the
    stored ``raw`` value with the parsed ``journal_abbr``, ``year``,
    ``locator`` and ``annotator`` columns the legacy loader filled;
  * rs_document.vindplaatsen (the open-data "vindplaatsen"), for entries that
    have no rs_document_publication row of the same raw value.

The weekly Rechtspraak loader fills neither (it drops dcterms:hasVersion), so
weekly runs find nothing until it does; the historical rows come from the
backfill. That is a loader gap, listed for the owner, not changed here.

Each entry becomes one record:

  * a journal locator ("NJ 2019/123", "AB 2020, 45", from the columns when
    journal_abbr, year and locator are all filled, else parsed from raw)
    without an annotator -> kind 'literature', scheme 'nl_journal_locator',
    identifier the canonical locator 'NJ 2019/123' (journal abbreviation
    upper case without dots or spaces, year, '/', number);
  * with an annotator (the column, or "m.nt.", "met annotatie van", "met noot
    van", "annotatie" in raw) -> kind 'annotation', identifier
    'NJ 2019/123 m.nt. <annotator>' (titles such as "mr." and "prof." left
    out, spaces collapsed): one document per note, shared by every decision
    published with it (an HR judgment and the Parket's conclusion in one NJ
    number).
  * "Rechtspraak.nl" and other entries without a journal locator are counted
    and skipped: Rechtspraak.nl is the decision itself, and an entry without
    a number has no identifier to share.

Attributes: title the canonical form, issuer the journal abbreviation;
no date (a year is not a date) and no url (journals have no public URL
scheme). raw_reference is the stored raw value, text_field 'metadata'.

No real rs_document_publication rows are in the research files, so the raw
forms parsed here are those of the Rechtspraak open-data documentation and
are tested with labelled illustrative strings; a precision sample on db-dev
is needed before the data reaches production.

CLI (backfill over a cases.id range; the connection is read-only):
    python -m data_extraction.linking.rs_publication --dsn-env VAR \\
        --from-id N --to-id M --out PATH
"""

import logging
import re
from collections import Counter
from typing import Dict, Iterable, List, Optional

from data_extraction.linking.artifact import CaseKey
from data_extraction.linking.authority_artifact import (
    AuthorityDoc,
    AuthorityMention,
    AuthorityRecord,
    AuthorityWriter,
)
from data_extraction.linking.text_common import BATCH_SIZE, cli_args, connect, iter_case_batches

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
SOURCE_DATASET = "rs_publication"
EXTRACTOR_VERSION = "rs_publication/1.0.0"

_ANNOTATION_RE = re.compile(
    r"[\s,(]+(?:m\.\s?nt\.|met\s+(?:annotatie|noot)\s+(?:van\s+)?|annotatie:?\s+(?:van\s+)?"
    r"|annotator:?\s*|noot:?\s+)(?P<annotator>[^()]+?)\)?\s*$",
    re.I,
)
_LOCATOR_RE = re.compile(
    r"^\s*(?P<journal>[A-Za-z][A-Za-z&'\-]*\.?(?:\s?[A-Za-z&'\-]+\.?){0,3}?)\s*"
    r"(?P<year>(?:19|20)\d{2})\s*[/,]\s*(?:nr\.?\s*)?"
    r"(?P<number>\d{1,6}(?:\.\d{1,3})?[A-Za-z]{0,2})(?![\w/])"
)
_TITLES_RE = re.compile(r"\b(?:mr|prof|dr|drs|ir|ing|em|jhr)\.\s*", re.I)
_SKIP_RE = re.compile(r"^\s*(?:www\.)?rechtspraak\.nl\s*$", re.I)


def canonical_journal(value: str) -> str:
    """'Gst.' -> 'GST', 'RvdW' -> 'RVDW', 'NJ' -> 'NJ'."""
    return re.sub(r"[\s.]+", "", value).upper()


def canonical_annotator(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = _TITLES_RE.sub("", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;.:")
    return value or None


def parse_publication(
    raw: str,
    journal_abbr: Optional[str] = None,
    year: Optional[int] = None,
    locator: Optional[str] = None,
    annotator: Optional[str] = None,
) -> Optional[Dict[str, Optional[str]]]:
    """One publication entry -> {journal, year, number, annotator, method}, or
    None when it names no journal locator."""
    if not raw or _SKIP_RE.match(raw):
        return None
    note = canonical_annotator(annotator)
    body = raw
    m = _ANNOTATION_RE.search(raw)
    if m:
        body = raw[: m.start()]
        note = note or canonical_annotator(m.group("annotator"))
    if journal_abbr and year and locator:
        number = re.sub(r"\s+", "", str(locator)).lstrip("/,")
        if re.fullmatch(r"\d{1,6}(?:\.\d{1,3})?[A-Za-z]{0,2}", number):
            return {
                "journal": canonical_journal(journal_abbr),
                "year": str(int(year)),
                "number": number.upper(),
                "annotator": note,
                "method": "publication_columns",
            }
    lm = _LOCATOR_RE.match(body)
    if not lm:
        return None
    journal = canonical_journal(lm.group("journal"))
    if not journal or journal in ("ECLI", "LJN", "NR", "ZAAKNR"):
        return None
    return {
        "journal": journal,
        "year": lm.group("year"),
        "number": lm.group("number").upper(),
        "annotator": note,
        "method": "publication_raw",
    }


def publication_doc(parts: Dict[str, Optional[str]]) -> AuthorityDoc:
    locator = f"{parts['journal']} {parts['year']}/{parts['number']}"
    if parts["annotator"]:
        identifier = f"{locator} m.nt. {parts['annotator']}"
        return AuthorityDoc(
            kind="annotation",
            identifier_scheme="nl_journal_locator",
            identifier=identifier,
            title=identifier,
            issuer=parts["journal"],
        )
    return AuthorityDoc(
        kind="literature",
        identifier_scheme="nl_journal_locator",
        identifier=locator,
        title=locator,
        issuer=parts["journal"],
    )


def records_for_case(
    source: CaseKey,
    publications: Iterable[tuple],
    vindplaatsen: Optional[Iterable[str]],
    stats: Counter,
) -> List[AuthorityRecord]:
    """publications: (raw, journal_abbr, year, locator, annotator) rows."""
    records, seen = [], set()
    entries = [(row, "rs_document_publication") for row in publications]
    for raw in vindplaatsen or ():
        entries.append(((raw, None, None, None, None), "vindplaatsen"))
    for (raw, journal_abbr, year, locator, annotator), origin in entries:
        raw = (raw or "").strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        parts = parse_publication(raw, journal_abbr, year, locator, annotator)
        if parts is None:
            stats[f"{origin}_skipped"] += 1
            continue
        stats[f"{origin}_{'annotation' if parts['annotator'] else 'literature'}"] += 1
        method = parts["method"] if origin == "rs_document_publication" else "vindplaatsen"
        record = AuthorityRecord(
            source=source,
            authority=publication_doc(parts),
            raw_reference=raw,
            source_dataset=SOURCE_DATASET,
            extractor_version=EXTRACTOR_VERSION,
            mention=AuthorityMention(text_field="metadata"),
            match_method=method,
            confidence=0.95 if method == "publication_columns" else 0.9,
        )
        record.validate()
        records.append(record)
    return records


_CASE_IDS = f"SELECT case_id FROM {SCHEMA}.rs_document WHERE true {{where}}"
_CASES = f"""
    SELECT c.id, c.ecli, c.celex_id, c.item_id, d.vindplaatsen
      FROM {SCHEMA}.rs_document d
      JOIN {SCHEMA}.cases c ON c.id = d.case_id
     WHERE d.case_id = ANY(%s)
     ORDER BY c.id
"""
_PUBLICATIONS = f"""
    SELECT case_id, raw, journal_abbr, year, locator, annotator
      FROM {SCHEMA}.rs_document_publication
     WHERE case_id = ANY(%s)
     ORDER BY case_id, raw
"""


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size: int = BATCH_SIZE):
    """Write the rs_publication artifact for the given RS cases (all when both
    selectors are None). Returns (records, stats)."""
    stats = Counter()
    with AuthorityWriter(out_path) as writer:
        for ids in iter_case_batches(
            conn, _CASE_IDS, case_ids=case_ids, id_range=id_range, batch_size=batch_size
        ):
            with conn.cursor() as cursor:
                cursor.execute(_CASES, (ids,))
                cases = cursor.fetchall()
                cursor.execute(_PUBLICATIONS, (ids,))
                publications: Dict[int, list] = {}
                for case_id, *row in cursor.fetchall():
                    publications.setdefault(case_id, []).append(tuple(row))
            conn.rollback()  # read-only; end the snapshot between batches
            records = []
            for case_id, ecli, celex, item_id, vindplaatsen in cases:
                key = CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None)
                if not (key.ecli or key.celex or key.item_id):
                    stats["sources_without_key"] += 1
                    continue
                stats["sources"] += 1
                records.extend(
                    records_for_case(key, publications.get(case_id, ()), vindplaatsen, stats)
                )
            writer.write(records)
    stats["records"] = writer.count
    log.info("rs_publication: %s", dict(sorted(stats.items())))
    return writer.count, stats


def main(argv=None):
    args = cli_args(__doc__.split("\n\n")[0].strip(), argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
    print(f"{written} records -> {args.out}")
    for key, value in sorted(stats.items()):
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
