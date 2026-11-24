"""
Cited authorities from Cellar data already in the database (roadmap R4.3,
R4.4, and the Cellar part of R4.6). Source dataset 'cellar_authority'.

1. Unresolved Cellar citations. case_citation rows of 'cellar_sparql' with no
   target case whose target CELEX is not case law of the collections:

     sector 5 (preparatory acts)  -> eu_preparatory_act; COM / JOIN numbers
                                     from descriptors PC, DC ("COM(2012) 11")
                                     and JC ("JOIN(2013) 1")
     sector 3, descriptor D       -> eu_decision (decisions of any institution:
                                     the CELEX does not say which, so they are
                                     not called Commission decisions);
                                     AUTHORITY_CELLAR_DECISIONS, default on
     sector 8 (national case law) -> national_court_decision, issuer the
                                     country code, date from the CELEX
                                     ("82018DE1114(51)": Germany, 2018-11-14);
                                     Dutch ones (8YYYYNL...) are left to the
                                     link extractors and counted
     sector E (EFTA)              -> efta_court for descriptor J, efta_document
                                     for every other descriptor

   Both directions are taken ('cites' and the inverse 'cited_by' rows); one
   record per (case, CELEX), match_method 'cellar_cites', 'cellar_cited_by'
   or 'cellar_cited_by,cellar_cites'. raw_reference is target_celex_raw as
   stored, text_field 'metadata'. Identifier scheme 'celex' (the CELEX without
   a '_XXX' suffix), url the EUR-Lex page built from it.

   Not verified against data (no sample in the research files): the sector 5
   and E descriptor meanings above. They only set kind, title and issuer;
   the identifier is the CELEX either way.

2. The national_judgement notice (cjeu_document.national_judgement_xml):

   * lines of a national decision that carry a full ECLI of a court outside
     the three collections ("*P1* Grondwettelijk Hof, arrest van 25/11/2021
     (ECLI:BE:GHCC:2021:ARR.168)") -> national_court_decision by ECLI,
     match_method 'national_judgement_ecli', pinpoint the line code ('P1');
   * literature lines ("- Nederlandse jurisprudentie ; Uitspraken in
     burgerlijke en strafzaken 1961 nº 159 (*)", "- Gielen, Ch.: Intellectuele
     eigendom & Reclamerecht 2010 p.299-300") -> literature or annotation,
     scheme 'cellar_literature', match_method 'national_judgement_literature',
     pinpoint the code of the national decision line they follow.

     A line with an author ("Surname, Initials: ...") and nothing but a
     journal, year and locator after it is an annotation (a named author's
     note); with a title before the journal ("Raaijmakers, M.J.G.C.: Nietige
     en non-existente vennootschap, Ars aequi 1989 p.1005-1010") it is an
     article (literature, the title kept); without an author it is a report of
     the decision in a journal (literature). The identifier is synthetic and
     deterministic: author (if any), journal, year and locator, normalised
     ('nederlandse jurisprudentie ; uitspraken in burgerlijke en strafzaken|
     1961|no. 159'). Lines without a year and a locator ("JURIFAST",
     "Publication Flash News ...", links) are counted and skipped.

     These lines describe where the *national* decision was published or
     annotated. They are attached to the CJEU document that carries the
     notice (the only case this data names), with the national decision's
     line code as pinpoint; attaching them to the Dutch decision instead,
     where R2.3 matched it, is a decision for the owner.

   citations_extra_info is not parsed: the research files hold no example of
   its content.

CLI (backfill over a cases.id range; the connection is read-only):
    python -m data_extraction.linking.cellar_authority --dsn-env VAR \\
        --from-id N --to-id M --out PATH
"""

import html
import logging
import re
from collections import Counter
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from data_extraction.linking import authority_patterns
from data_extraction.linking.artifact import CaseKey
from data_extraction.linking.authority_artifact import (
    AuthorityDoc,
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
SOURCE_DATASET = "cellar_authority"
EXTRACTOR_VERSION = "cellar_authority/1.0.0"
DECISIONS_FLAG = "AUTHORITY_CELLAR_DECISIONS"
EURLEX_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{}"
NJ_FIELD = "national_judgement_xml"

CELEX_RE = re.compile(
    r"^(?P<sector>[0-9CE])(?P<year>\d{4})(?P<type>[A-Z]{1,2})(?P<num>[0-9A-Z]+?)"
    r"(?P<suffix>\(\d{1,3}\))?(?:_[A-Z0-9]+)?$"
)
_PREPARATORY_ISSUERS = {
    "PC": "European Commission",
    "DC": "European Commission",
    "SC": "European Commission",
    "JC": "European Commission and High Representative",
    "AE": "European Economic and Social Committee",
    "IR": "European Committee of the Regions",
}
_PREPARATORY_TITLES = {
    "PC": "COM({year}) {num}",
    "DC": "COM({year}) {num}",
    "JC": "JOIN({year}) {num}",
}  # noqa: E501
CONFIDENCE_CELEX = 0.95


def celex_identifier(raw: str) -> str:
    """The CELEX without outer whitespace or a '_XXX' suffix, upper case."""
    return re.sub(r"_[A-Za-z0-9]+$", "", (raw or "").strip()).upper()


def classify_celex(raw: str, decisions: bool = True) -> Tuple[Optional[AuthorityDoc], str]:
    """The authority a Cellar target CELEX names, or (None, reason)."""
    celex = celex_identifier(raw)
    m = CELEX_RE.match(celex)
    if not m:
        return None, "celex_unparsed"
    sector, year, kind_code, num = (
        m.group("sector"),
        m.group("year"),
        m.group("type"),
        m.group("num"),
    )  # noqa: E501
    url = EURLEX_URL.format(celex)
    if sector == "5":
        title = None
        template = _PREPARATORY_TITLES.get(kind_code)
        if template and num.isdigit():
            title = template.format(year=year, num=int(num))
        return (
            AuthorityDoc(
                kind="eu_preparatory_act",
                identifier_scheme="celex",
                identifier=celex,
                title=title,
                issuer=_PREPARATORY_ISSUERS.get(kind_code),
                url=url,
            ),
            "sector5",
        )
    if sector == "3" and kind_code == "D":
        if not decisions:
            return None, "sector3_decision_off"
        return (
            AuthorityDoc(kind="eu_decision", identifier_scheme="celex", identifier=celex, url=url),
            "sector3_decision",
        )
    if sector == "8":
        if len(kind_code) != 2:
            return None, "sector8_unparsed"
        if kind_code == "NL":
            return None, "sector8_nl"
        decided = None
        if len(num) >= 4 and num[:4].isdigit():
            try:
                decided = date(int(year), int(num[:2]), int(num[2:4])).isoformat()
            except ValueError:
                decided = None
        return (
            AuthorityDoc(
                kind="national_court_decision",
                identifier_scheme="celex",
                identifier=celex,
                issuer=kind_code,
                date=decided,
                url=url,
            ),
            "sector8",
        )
    if sector == "E":
        kind = "efta_court" if kind_code == "J" else "efta_document"
        return (
            AuthorityDoc(kind=kind, identifier_scheme="celex", identifier=celex, url=url),
            "sectorE",
        )
    return None, f"sector{sector}_not_authority"


# ---------------------------------------------------------------------------
# national_judgement notice
# ---------------------------------------------------------------------------

_P_RE = re.compile(r"<p>(.*?)</p>", re.S)
_TAG_RE = re.compile(r"^\*([AIP])(\d*)\*")
_MARKER_RE = re.compile(
    r"\s*\((?:\*|résumé|resume|summary|Texte?\s[^()]{1,30}|[A-Z][a-z]+ text|[A-Z][a-z]+ tekst)\)",
    re.I,
)
_AUTHOR_RE = re.compile(
    r"^(?P<author>[^:;,\d()]{2,40},\s*[^:;,\d()]{1,40}(?:;\s*[^:;,\d()]{2,40},\s*[^:;,\d()]{1,40})*"
    r"|(?:[A-Z]\.){1,6}(?=:)|X)\s*:\s+(?P<rest>.+)$"
)
# What may follow the year: volume, part and section labels, a number and
# pages ("Vol.2 p.10-12", "Bijl. p.12", "II p.334-339", "nº 159", "Col.1503").
_LOC_TOKEN = (
    r"(?:Bijl\.|Jur\.|Katern|Part\s*\d+|liv\.\s*\d+|Vol\.\s*[\w.]+|[IV]{1,3}(?![\w.])"
    r"|[Rr]ubr\.\s*eur\.|(?:nº|n°|no\.?|nr\.?)\s*[\w.\-]+"
    r"|(?:p\.|pp\.|Col\.)\s*[A-Z]?\d+(?:\s*-\s*[A-Z]?\d+)?|\+|,)"
)
_YEAR_LOC_RE = re.compile(
    r"^(?P<journal>.+?),?\s+(?P<year>(?:1[89]|20)\d{2}(?:-\d{2,4})?),?"
    r"(?P<loc>(?:\s*" + _LOC_TOKEN + r")+)\s*$"
)
_LOC_MARK_RE = re.compile(r"(?:p\.|pp\.|Col\.|nº|n°|no\.?|nr\.?)\s*[A-Z]?\d")


def _norm(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^[\s,;\-–]+|[\s,;\-–]+$", "", value)
    value = re.sub(r"(?:\bnr\.?|nº|n°)\s*(?=\d)", "no. ", value)
    value = re.sub(r"\b(p|pp|Col)\.\s*", lambda m: m.group(1) + ".", value)
    return value


def parse_literature(line: str) -> Optional[Dict[str, Optional[str]]]:
    """A literature line of the notice ('- ...') -> its parts, or None when it
    has no year and locator. Keys: kind, author, title, journal, year, locator."""
    text = line.strip()
    if not text.startswith("-"):
        return None
    text = text[1:].strip()
    while True:
        stripped = _MARKER_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    author, title = None, None
    m = _AUTHOR_RE.match(text)
    if m:
        author, text = m.group("author").strip(), m.group("rest").strip()
    ym = _YEAR_LOC_RE.match(text)
    if not ym or not _LOC_MARK_RE.search(ym.group("loc")):
        return None
    journal = re.sub(r"[\s,\-–]+$", "", ym.group("journal"))
    kind = "literature"
    if author:
        if ", " in journal:
            title, journal = journal.rsplit(", ", 1)
            title = title.strip() or None
        else:
            kind = "annotation"
    return {
        "kind": kind,
        "author": author,
        "title": title,
        "journal": journal.strip(),
        "year": ym.group("year"),
        "locator": ym.group("loc").strip(" ,"),
    }


def literature_doc(parts: Dict[str, Optional[str]]) -> AuthorityDoc:
    pieces = [parts["author"]] if parts["author"] else []
    pieces += [parts["journal"], parts["year"], parts["locator"]]
    identifier = "|".join(_norm(p).lower() for p in pieces)
    shown = f"{_norm(parts['journal'])} {parts['year']} {_norm(parts['locator'])}"
    if parts["kind"] == "annotation":
        title = f"{_norm(parts['author'])}: {shown}"
    elif parts["title"]:
        title = f"{_norm(parts['author'])}: {_norm(parts['title'])}, {shown}"
    else:
        title = shown
    return AuthorityDoc(
        kind=parts["kind"],
        identifier_scheme="cellar_literature",
        identifier=identifier,
        title=title,
        issuer=_norm(parts["journal"]),
    )


def notice_records(source: CaseKey, xml: Optional[str], stats: Counter) -> List[AuthorityRecord]:
    """Foreign-court ECLIs and literature lines of one notice."""
    records = []
    if not xml:
        return records
    tag = None
    for match in _P_RE.finditer(xml):
        inner = match.group(1)
        lead = len(inner) - len(inner.lstrip())
        start = match.start(1) + lead
        end = match.start(1) + len(inner.rstrip())
        text = html.unescape(inner).strip()
        if text.startswith("**"):  # "** AFFAIRE C-199/12 **"
            tag = None
            continue
        tag_match = _TAG_RE.match(text)
        if tag_match:
            tag = tag_match.group(1) + tag_match.group(2)
            for hit in authority_patterns.foreign_ecli_hits(xml[start:end]):
                stats["nj_foreign_ecli"] += 1
                records.append(
                    _record(
                        source,
                        hit.doc,
                        xml[start + hit.start : start + hit.end],
                        AuthorityMention(
                            text_field=NJ_FIELD,
                            char_start=start + hit.start,
                            char_end=start + hit.end,
                            context=context(
                                xml, start + hit.start, start + hit.end, collapse_space=True
                            ),  # noqa: E501
                        ),
                        tag,
                        "national_judgement_ecli",
                        0.95,
                    )
                )
            continue
        if not text.startswith("-"):
            stats["nj_other_lines"] += 1
            continue
        parts = parse_literature(text)
        if parts is None:
            stats["nj_literature_unparsed"] += 1
            continue
        stats[f"nj_{parts['kind']}"] += 1
        records.append(
            _record(
                source,
                literature_doc(parts),
                text,
                AuthorityMention(
                    text_field=NJ_FIELD,
                    char_start=start,
                    char_end=end,
                    context=re.sub(r"\s+", " ", text)[:300],
                ),
                tag,
                "national_judgement_literature",
                0.9,
            )
        )
    return records


def _record(source, doc, raw, mention, pinpoint, method, confidence):
    record = AuthorityRecord(
        source=source,
        authority=doc,
        raw_reference=raw,
        source_dataset=SOURCE_DATASET,
        extractor_version=EXTRACTOR_VERSION,
        mention=mention,
        pinpoint=pinpoint,
        match_method=method,
        confidence=confidence,
    )
    record.validate()
    return record


def citation_records(
    source: CaseKey, targets: Iterable[Tuple[str, str]], stats: Counter, decisions: bool = True
) -> List[AuthorityRecord]:
    """[(target_celex_raw, relation_type)] of one case -> one record per CELEX."""
    by_raw: Dict[str, set] = {}
    for raw, relation in targets:
        if raw and relation in ("cites", "cited_by"):
            by_raw.setdefault(raw.strip(), set()).add(relation)
    records = []
    for raw in sorted(by_raw):
        doc, reason = classify_celex(raw, decisions)
        stats[f"celex_{reason}"] += 1
        if doc is None:
            continue
        method = ",".join(f"cellar_{r}" for r in sorted(by_raw[raw]))
        records.append(
            _record(
                source,
                doc,
                raw,
                AuthorityMention(text_field="metadata"),
                None,
                method,
                CONFIDENCE_CELEX,
            )
        )
    return records


_CASE_IDS = f"SELECT case_id FROM {SCHEMA}.cjeu_document WHERE true {{where}}"
_DOCUMENTS = f"""
    SELECT c.id, c.ecli, c.celex_id, c.item_id, d.national_judgement_xml
      FROM {SCHEMA}.cjeu_document d
      JOIN {SCHEMA}.cases c ON c.id = d.case_id
     WHERE d.case_id = ANY(%s)
     ORDER BY c.id
"""
_CITATIONS = f"""
    SELECT source_case_id, target_celex_raw, relation_type
      FROM {SCHEMA}.case_citation
     WHERE source_case_id = ANY(%s)
       AND source_dataset = 'cellar_sparql'
       AND target_case_id IS NULL
       AND target_celex_raw IS NOT NULL
       AND relation_type IN ('cites', 'cited_by')
"""


def extract(
    conn,
    case_ids=None,
    id_range=None,
    out_path=None,
    batch_size: int = BATCH_SIZE,
    decisions: Optional[bool] = None,
):
    """Write the cellar_authority artifact for the given CJEU cases (all when
    both selectors are None). Returns (records, stats)."""
    if decisions is None:
        decisions = env_flag(DECISIONS_FLAG, True)
    stats = Counter()
    with AuthorityWriter(out_path) as writer:
        for ids in iter_case_batches(
            conn, _CASE_IDS, case_ids=case_ids, id_range=id_range, batch_size=batch_size
        ):
            with conn.cursor() as cursor:
                cursor.execute(_DOCUMENTS, (ids,))
                documents = cursor.fetchall()
                cursor.execute(_CITATIONS, (ids,))
                targets: Dict[int, list] = {}
                for case_id, raw, relation in cursor.fetchall():
                    targets.setdefault(case_id, []).append((raw, relation))
            conn.rollback()  # read-only; end the snapshot between batches
            records = []
            for case_id, ecli, celex, item_id, xml in documents:
                key = CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None)
                if not (key.ecli or key.celex or key.item_id):
                    stats["sources_without_key"] += 1
                    continue
                stats["sources"] += 1
                records.extend(citation_records(key, targets.get(case_id, ()), stats, decisions))
                records.extend(notice_records(key, xml, stats))
            writer.write(records)
    stats["records"] = writer.count
    log.info("cellar_authority: %s", dict(sorted(stats.items())))
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
