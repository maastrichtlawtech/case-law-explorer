"""
CJEU text -> ECtHR links (roadmap R2.6).

Scans the texts of CJEU cases (judgments, orders and Advocate General's
opinions; every language stored) and writes the dataset ``cjeu_text_echr``
(relation 'cites'):

* ECtHR ECLIs, with or without the "ECLI:" prefix
  ("CE:ECHR:2004:0622DEC001734103"); an ECLI that lost its year
  ("CE:ECHR:0622JUD000781977") is resolved through the application number it
  carries, and only when a document of that number has that day and month;
* application numbers ("no. 17341/03", "nos. 30562/04 and 30566/04",
  "requête n° 17341/03", "Nr. 17341/03") when an ECtHR cue is near
  ("ECtHR", "Eur. Court H.R.", "Cour EDH", "EGMR", "(dec.)", "v." / "c."
  naming a State, ...) and no legislation word ("Regulation No 1408/71")
  precedes the number. They resolve through case_identifier
  (scheme 'echr_appno', owner numbers only) with resolver.choose_echr: a
  decision only when "(dec.)"/"(déc.)" is written or there is no judgment,
  then the cited date or year;
* name + date citations ("F. v. the United Kingdom, 22 June 2004") only with
  the flag NAME_DATE_LINKS on (default off; decision D5 allows them only after
  a 100-row sample reaches 95% precision). They match echr_document.docname and
  judgement_date exactly (match_method 'name_date', target_ref_scheme
  'name_date') and are skipped when an application number or ECLI already
  names a document in the same citation.

Texts: case_text rows of CJEU cases (CELLAR_ITEM, INFOCURIA_BLOB_HTML), never
document_kind 'misfiled', and per (case, language) only the decision itself
when the case has one (summaries, information sheets and OJ notices only when
nothing better exists), following the order of case_text_canonical.

Pure entry point: ``extract_text(unit, source, lookup)``.
Database entry point: ``extract(conn, case_ids=None, id_range=None, out_path=...)``.
CLI: ``python -m data_extraction.linking.cjeu_text --dsn-env VAR --from-id N
--to-id M --out PATH``.
"""

import logging
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from data_extraction.linking import identifiers, resolver
from data_extraction.linking.artifact import CaseKey, LinkRecord
from data_extraction.linking.text_common import (
    DATE_RE,
    CandidateLookup,
    PendingLink,
    Source,
    TextUnit,
    build_records,
    cli_args,
    connect,
    env_flag,
    iter_case_batches,
    mention,
    parse_date_match,
    write_artifact,
)

log = logging.getLogger(__name__)

EXTRACTOR_VERSION = "cjeu_text/1.0.0"
DATASET = "cjeu_text_echr"
RELATION = "cites"
NAME_DATE_FLAG = "NAME_DATE_LINKS"
SCHEMA = resolver.SCHEMA
CJEU_TEXT_SOURCES = ("CELLAR_ITEM", "INFOCURIA_BLOB_HTML")

CONF_ECLI = 0.99
CONF_ECLI_NO_YEAR = 0.85
CONF_NAME_DATE = 0.7

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

ECHR_ECLI_RE = re.compile(
    r"(?<![\w:])(?:ECLI:)?CE:ECHR:(?:(?P<year>\d{4}):)?"
    r"(?P<mmdd>\d{4})(?P<type>JUD|DEC|REP|ADV|RES)(?P<appno>\d{9})(?![\w:])",
    re.I,
)
# The marker in front of an application number, and the lists after it.
APPNO_RE = re.compile(
    r"(?P<mark>\b(?:applications?\s+nos?\.?|application\s+number|requêtes?\s+(?:n[°ºo]s?\.?)?|"
    r"Beschwerde-?Nr\.?|Beschwerden?\s+Nr\.?|ricorsi?\s+(?:n\.|nn\.)?|demanda\s+n\.?[°º]?|"
    r"nos?\.|n[°º]s?|nrs?\.|Nr\.|nn?\.)\s*)"
    r"(?P<list>\d{1,6}/\d{2}(?![\d/])(?:\s*(?:,|;|and|et|und|en|e|y|i)\s*\d{1,6}/\d{2}(?![\d/]))*)",
    re.I,
)
_APPNO_ITEM_RE = re.compile(r"\d{1,6}/\d{2}(?![\d/])")
_ECHR_CUE_RE = re.compile(
    r"ECtHR|Eur\.?\s*Court\s*H\.?\s*R|European\s+Court\s+of\s+Human\s+Rights|Cour\s+EDH|"
    r"Cour\s+eur\.\s*D\.?\s*H|Cour\s+européenne\s+des\s+droits\s+de\s+l[’']homme|\bCEDH\b|"
    r"\bEGMR\b|\bEHRM\b|Europäische[nr]?\s+Gerichtshofs?\s+für\s+Menschenrechte|"
    r"Europees\s+Hof\s+voor\s+de\s+Rechten\s+van\s+de\s+Mens|Corte\s+EDU|"
    r"Corte\s+europea\s+dei\s+diritti\s+dell[’']uomo|\bTEDH\b|"
    r"Tribunal\s+Europeo\s+de\s+Derechos\s+Humanos|\bETPC\b|\bESLJP\b|\bEIRD\b|"
    r"\((?:dec|déc|Entsch|dés)\.\)|\[GC\]|Reports\s+of\s+Judgments\s+and\s+Decisions|"
    r"Recueil\s+des\s+arrêts\s+et\s+décisions|Series\s+A\s+no|série\s+A\s+n|CE:ECHR",
    re.I,
)
# A legislation word just before the marker: "Regulation (EEC) No 1408/71".
_LEGISLATION_RE = re.compile(
    r"(?:regulation|règlement|verordnung|verordening|regolamento|reglamento|rozporządzeni\w*|"
    r"directive|richtlinie|richtlijn|direttiva|directiva|decision|décision|beschluss|besluit|"
    r"decisione|decisión|framework|protocol|protocole|convention|übereinkommen|treaty|traité|"
    r"resolution|résolution|recommendation|recommandation|communication|opinion|avis|"
    r"case|affaire|zaak|rechtssache|causa|asunto|report|rapport)\W{0,12}"
    r"(?:\([A-Z]{2,4}\)\s*)?(?:\w+\s+){0,2}$",
    re.I,
)
_DECISION_CUE_RE = re.compile(r"\((?:dec|déc|Entsch|dés|dec\.)\.?\)", re.I)
_YEAR_CUE_RE = re.compile(r"\b(?:ECHR|CEDH|Reports|Recueil)\s+(?P<year>(?:19|20)\d\d)\b")
_STATE_NAMES = (
    "(?:the\\s+)?(?:United Kingdom|Royaume-Uni|Vereinigtes Königreich|Verenigd Koninkrijk|"
    "[A-ZÀ-Ý][\\w’'\\-]+(?:\\s+(?:and|et)\\s+[A-ZÀ-Ý][\\w’'\\-]+)?)"
)
# "F. v. the United Kingdom, 22 June 2004" / "F. c. Royaume-Uni (déc.), 22 juin 2004"
NAME_DATE_RE = re.compile(
    r"(?P<name>(?:[A-ZÀ-Ý][\w’'.\-]*\s+){0,5}?[A-ZÀ-Ý][\w’'.\-]*)\s+"
    r"(?P<sep>v\.|c\.|vs\.|gegen|contro|contra|t\.)\s+"
    r"(?P<state>" + _STATE_NAMES + r")"
    r"(?P<tail>(?:\s*\[GC\])?(?:\s*\((?:dec|déc|Entsch|dés)\.\))?\s*,\s*)"
)


@dataclass
class AppnoRef:
    start: int
    end: int
    value: str
    decision_cue: bool
    cited_date: Optional[date]
    cited_year: Optional[int]
    citation: int  # index of the citation it belongs to (one marker list = one citation)


@dataclass
class Scan:
    eclis: List[Tuple[int, int, str]] = field(default_factory=list)
    eclis_no_year: List[Tuple[int, int, str, str, str]] = field(default_factory=list)
    appnos: List[AppnoRef] = field(default_factory=list)
    name_dates: List[Tuple[int, int, str, date, bool]] = field(default_factory=list)

    def appno_values(self):
        values = {a.value for a in self.appnos}
        values.update(appno for _s, _e, _mmdd, _type, appno in self.eclis_no_year)
        return values


def _appno_from_ecli(digits):
    return identifiers.normalize_echr_appno(f"{int(digits[:7])}/{digits[7:]}")


def _citation_tail(text, end, limit=140):
    """Text after a reference up to the end of its citation (';', ')' or sentence)."""
    tail = text[end : end + limit]
    stop = re.search(r";|\)\s*[;.]|\.\s+[A-Z]", tail)
    return tail[: stop.start()] if stop else tail


def _citation_head(text, start, limit=200):
    head = text[max(0, start - limit) : start]
    stop = list(re.finditer(r";|\(see|\(voir|\(vgl|\(zie|\.\s+(?=[A-Z])", head))
    return head[stop[-1].end() :] if stop else head


def scan(text: str, name_dates: bool = False) -> Scan:
    out = Scan()
    for match in ECHR_ECLI_RE.finditer(text):
        if match.group("year"):
            ecli = identifiers.normalize_ecli(
                "ECLI:CE:ECHR:{}:{}{}{}".format(
                    match.group("year"),
                    match.group("mmdd"),
                    match.group("type").upper(),
                    match.group("appno"),
                )
            )
            if ecli:
                out.eclis.append((match.start(), match.end(), ecli))
        else:
            appno = _appno_from_ecli(match.group("appno"))
            if appno:
                out.eclis_no_year.append(
                    (
                        match.start(),
                        match.end(),
                        match.group("mmdd"),
                        match.group("type").upper(),
                        appno,
                    )
                )

    for index, match in enumerate(APPNO_RE.finditer(text)):
        before = text[max(0, match.start() - 60) : match.start()]
        if _LEGISLATION_RE.search(before):
            continue
        window = text[max(0, match.start() - 250) : match.end() + 150]
        if not _ECHR_CUE_RE.search(window):
            continue
        head = _citation_head(text, match.start())
        tail = _citation_tail(text, match.end())
        decision_cue = bool(
            _DECISION_CUE_RE.search(head[-80:]) or _DECISION_CUE_RE.search(tail[:20])
        )
        cited_date = cited_year = None
        for dmatch in DATE_RE.finditer(tail):
            cited_date = parse_date_match(dmatch)
            if cited_date:
                break
        ymatch = _YEAR_CUE_RE.search(tail)
        if ymatch:
            cited_year = int(ymatch.group("year"))
        elif cited_date:
            cited_year = cited_date.year
        for item in _APPNO_ITEM_RE.finditer(match.group("list")):
            value = identifiers.normalize_echr_appno(item.group(0))
            if not value:
                continue
            start = match.start("list") + item.start()
            out.appnos.append(
                AppnoRef(
                    start,
                    start + len(item.group(0)),
                    value,
                    decision_cue,
                    cited_date,
                    cited_year,
                    index,
                )
            )

    if name_dates:
        for match in NAME_DATE_RE.finditer(text):
            after = text[match.end() : match.end() + 40]
            dmatch = DATE_RE.match(after)
            if not dmatch:
                continue
            cited = parse_date_match(dmatch)
            if cited is None:
                continue
            name = f"{match.group('name')} {match.group('sep')} {match.group('state')}"
            decision = bool(_DECISION_CUE_RE.search(match.group("tail")))
            out.name_dates.append(
                (match.start(), match.end() + dmatch.end(), name, cited, decision)
            )
    return out


# ---------------------------------------------------------------------------
# Name + date matching (flagged, D5)
# ---------------------------------------------------------------------------

_SEP_NORMAL = {
    "v.": "V",
    "vs.": "V",
    "c.": "V",
    "gegen": "V",
    "contro": "V",
    "contra": "V",
    "t.": "V",
}
_STATE_SYNONYMS = {
    "ROYAUME-UNI": "UNITED KINGDOM",
    "VEREINIGTES KÖNIGREICH": "UNITED KINGDOM",
    "VERENIGD KONINKRIJK": "UNITED KINGDOM",
}


def normalize_case_name(value: str) -> Optional[str]:
    """'CASE OF F. v. THE UNITED KINGDOM' / 'F. c. Royaume-Uni' -> 'F V UNITED KINGDOM'."""
    if not value:
        return None
    text = unicodedata.normalize("NFKC", value).strip()
    text = re.sub(
        r"^(?:CASE\s+OF|AFFAIRE|AFFAIRE\s+DE|CAUSA|RECHTSSACHE|ZAAK)\s+", "", text, flags=re.I
    )
    text = re.sub(r"\s*\((?:dec|déc|Entsch)\.\)|\s*\[GC\]", "", text, flags=re.I)
    match = re.match(
        r"^(?P<name>.+?)\s+(?P<sep>v\.|vs\.|c\.|gegen|contro|contra|t\.)\s+(?P<state>.+)$",
        text,
        re.I,
    )
    if not match:
        return None
    name = re.sub(r"[.\s]+", " ", match.group("name")).strip().upper()
    state = re.sub(r"\s+", " ", match.group("state")).strip().upper()
    state = re.sub(r"^THE\s+", "", state)
    state = re.sub(r"\s*\(.*$", "", state).strip(" ,.")
    state = _STATE_SYNONYMS.get(state, state)
    return f"{name} V {state}"


def name_keys(name: str) -> List[str]:
    """Normalized keys for a cited name, longest first, dropping leading words
    that may belong to the sentence ("See F. v. the United Kingdom")."""
    match = re.match(
        r"^(?P<name>.+?)\s+(?P<rest>(?:v\.|vs\.|c\.|gegen|contro|contra|t\.)\s+.+)$", name
    )
    if not match:
        return []
    words = match.group("name").split()
    keys = []
    for i in range(len(words)):
        key = normalize_case_name(" ".join(words[i:]) + " " + match.group("rest"))
        if key and key not in keys:
            keys.append(key)
    return keys


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve(scan_result: Scan, unit: TextUnit, source: Source, lookup, name_index=None):
    """Pending links for one text. ``name_index`` maps (normalized name, date)
    to [Candidate] and is only used for name + date citations."""
    out: List[PendingLink] = []

    def add(target, start, end, method, confidence, ref=None, scheme=None, extra=()):
        mentions = [mention(unit, start, end)] + [mention(unit, s, e) for s, e in extra]
        out.append(
            PendingLink(
                target=target,
                relation_type=RELATION,
                source_dataset=DATASET,
                match_method=method,
                confidence=confidence,
                target_ref_raw=ref,
                target_ref_scheme=scheme,
                mentions=mentions,
            )
        )

    covered = []  # spans already naming a document (for the name + date fallback)
    for start, end, ecli in scan_result.eclis:
        add(CaseKey(ecli=ecli), start, end, "ecli", CONF_ECLI)
        covered.append((start, end))

    candidates = lookup.get("echr_appno", sorted(scan_result.appno_values()))

    for start, end, mmdd, doc_type, appno in scan_result.eclis_no_year:
        pool = [
            c
            for c in candidates.get(appno, [])
            if c.date is not None and c.date.strftime("%m%d") == mmdd
        ]
        choice = resolver.choose_echr(pool, source.date, decision_cue=doc_type == "DEC")
        if choice is None:
            add(None, start, end, "ecli", None, ref=appno, scheme="echr_appno")
        else:
            add(
                CaseKey.from_dict(choice.candidate.key()),
                start,
                end,
                "ecli",
                CONF_ECLI_NO_YEAR,
                ref=appno,
                scheme="echr_appno",
            )
        covered.append((start, end))

    for ref in scan_result.appnos:
        choice = resolver.choose_echr(
            candidates.get(ref.value, []),
            source.date,
            decision_cue=ref.decision_cue,
            cited_date=ref.cited_date,
            cited_year=ref.cited_year,
        )
        target = CaseKey.from_dict(choice.candidate.key()) if choice else None
        add(
            target,
            ref.start,
            ref.end,
            "appno",
            choice.confidence if choice else None,
            ref=ref.value,
            scheme="echr_appno",
        )
        covered.append((ref.start, ref.end))

    for start, end, name, cited, decision in scan_result.name_dates:
        if any(s < end + 120 and e > start - 40 for s, e in covered):
            continue  # the citation already names its document by number or ECLI
        keys = name_keys(name)
        if not keys:
            continue
        index = name_index or {}
        key = next((k for k in keys if (k, cited) in index), keys[-1])
        ref = f"{key}|{cited.isoformat()}"
        pool = list(index.get((key, cited), []))
        choice = resolver.choose_echr(pool, source.date, decision_cue=decision, cited_date=cited)
        if choice is None or len({c.case_id for c in pool if c.date == cited}) > 1:
            add(None, start, end, "name_date", None, ref=ref, scheme="name_date")
        else:
            target = CaseKey.from_dict(choice.candidate.key())
            add(target, start, end, "name_date", CONF_NAME_DATE, ref=ref, scheme="name_date")
    return out


def extract_text(
    unit: TextUnit, source: Source, lookup, name_dates: Optional[bool] = None, name_index=None
) -> List[LinkRecord]:
    """All ECtHR links one CJEU text supports (pure apart from ``lookup``)."""
    if name_dates is None:
        name_dates = env_flag(NAME_DATE_FLAG, False)
    if not unit.text:
        return []
    found = scan(unit.text, name_dates=name_dates)
    return build_records(
        source, resolve(found, unit, source, lookup, name_index), EXTRACTOR_VERSION
    )


# ---------------------------------------------------------------------------
# Database entry point
# ---------------------------------------------------------------------------

_IDS_SQL = f"""
    SELECT DISTINCT case_id FROM {SCHEMA}.case_text
     WHERE source IN ('CELLAR_ITEM', 'INFOCURIA_BLOB_HTML')
       AND fulltext IS NOT NULL
       AND document_kind IS DISTINCT FROM 'misfiled' {{where}}
"""

# Per (case, language) the decision itself before extracts before abstracts,
# a non-empty text first, then CELLAR before InfoCuria (case_text_canonical).
_TEXTS_SQL = f"""
    SELECT DISTINCT ON (t.case_id, t.language)
           t.case_id, c.ecli, c.celex_id, c.item_id, c.date_decision, t.language,
           t.source, t.fulltext, t.document_kind
      FROM {SCHEMA}.case_text t
      JOIN {SCHEMA}.cases c ON c.id = t.case_id
     WHERE t.case_id = ANY(%s)
       AND t.source IN ('CELLAR_ITEM', 'INFOCURIA_BLOB_HTML')
       AND t.document_kind IS DISTINCT FROM 'misfiled'
       AND t.fulltext IS NOT NULL AND btrim(t.fulltext) <> ''
     ORDER BY t.case_id, t.language,
              CASE WHEN t.document_kind IN ('summary', 'information', 'oj_notice') THEN 2
                   WHEN t.document_kind = 'extract' THEN 1 ELSE 0 END,
              CASE t.source WHEN 'CELLAR_ITEM' THEN 1 ELSE 2 END,
              t.id
"""

_NAME_DATE_SQL = f"""
    SELECT d.docname, d.judgement_date::date, c.id, c.ecli, c.celex_id, c.item_id,
           c.date_decision, d.doctype, d.item_id
      FROM {SCHEMA}.echr_document d
      JOIN {SCHEMA}.cases c ON c.id = d.case_id
     WHERE d.judgement_date::date = ANY(%s)
"""


def fetch_name_index(cursor, dates):
    """(normalized docname, judgement date) -> [Candidate] for the cited dates."""
    dates = sorted({d for d in dates if d})
    if not dates:
        return {}
    cursor.execute(_NAME_DATE_SQL, (dates,))
    index: Dict[tuple, dict] = {}
    for (
        docname,
        judged,
        case_id,
        ecli,
        celex,
        item_id,
        decided,
        doctype,
        _item,
    ) in cursor.fetchall():
        key = normalize_case_name(docname or "")
        if key is None:
            continue
        candidate = resolver.Candidate(
            case_id, ecli, celex, item_id, decided or judged, resolver.echr_kind(doctype), docname
        )
        index.setdefault((key, judged), {})[case_id] = candidate
    return {k: list(v.values()) for k, v in index.items()}


def extract_batch(cursor, case_ids: Sequence[int], lookup, name_dates: bool):
    cursor.execute(_TEXTS_SQL, (list(case_ids),))
    rows = cursor.fetchall()
    sources, scans = {}, []
    for case_id, ecli, celex, item_id, decided, language, text_source, fulltext, _kind in rows:
        sources[case_id] = Source(
            CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None), decided
        )
        unit = TextUnit(fulltext, "fulltext", language, text_source)
        scans.append((case_id, unit, scan(fulltext, name_dates=name_dates)))
    lookup.prefetch("echr_appno", {v for _c, _u, s in scans for v in s.appno_values()})
    name_index = None
    if name_dates:
        name_index = fetch_name_index(
            cursor, {d for _c, _u, s in scans for *_x, d, _y in s.name_dates}
        )
    pending_by_case: Dict[int, List[PendingLink]] = {}
    for case_id, unit, found in scans:
        source = sources[case_id]
        if not (source.key.ecli or source.key.celex or source.key.item_id):
            continue
        pending_by_case.setdefault(case_id, []).extend(
            resolve(found, unit, source, lookup, name_index)
        )
    records = []
    for case_id, pending in pending_by_case.items():
        records.extend(build_records(sources[case_id], pending, EXTRACTOR_VERSION))
    return records


def extract(conn, case_ids=None, id_range=None, out_path=None, name_dates=None, batch_size=500):
    """Scan CJEU texts in the database and write the link artifact.

    ``out_path`` may be a file or a directory (then ``cjeu_text_echr.jsonl``
    inside it). Returns {"records": n, "by_method": {...}, "written": n}.
    """
    if name_dates is None:
        name_dates = env_flag(NAME_DATE_FLAG, False)
    records: List[LinkRecord] = []
    with conn.cursor() as cursor:
        lookup = CandidateLookup(cursor)
        for ids in iter_case_batches(
            conn, _IDS_SQL, case_ids=case_ids, id_range=id_range, batch_size=batch_size
        ):
            records.extend(extract_batch(cursor, ids, lookup, name_dates))
            lookup.clear()
            log.info("cjeu_text: up to case %s, %s records", ids[-1], len(records))
    by_method = {}
    for record in records:
        key = record.match_method if record.target else f"{record.match_method}_unresolved"
        by_method[key] = by_method.get(key, 0) + 1
    written = None
    if out_path:
        path = out_path
        if os.path.isdir(out_path) or str(out_path).endswith(os.sep):
            os.makedirs(out_path, exist_ok=True)
            path = os.path.join(out_path, f"{DATASET}.jsonl")
        written = write_artifact(records, path)
    return {"records": len(records), "by_method": by_method, "written": written}


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = cli_args("CJEU text -> ECtHR links (R2.6)", argv)
    conn = connect(args.dsn_env)
    try:
        result = extract(
            conn, case_ids=args.case_id, id_range=(args.from_id, args.to_id), out_path=args.out
        )
    finally:
        conn.close()
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
