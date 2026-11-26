"""
ECtHR scl metadata -> ECtHR case links (roadmap R6.1).

Replaces the legacy echr-extractor ECHR_edges.txt fan-out (which resolved each
cited application number against both owner ``appno`` and ``extractedappno``,
creating up to 15,597 false edges per case) with a deterministic resolver over
HUDOC's structured ``echr_document.scl`` (Strasbourg Case-Law) citation list.

Rules (verified at r6.1-v4, 100% precision on the 320-row drop/keep gate):

  1. Candidate lookup uses ONLY documents that own the application number
     (``echr_document_appno WHERE source = 'appno'`` and ``case_identifier``
     with ``scheme = 'echr_appno'``; never ``extractedappno``).
  2. Hard exclusions:
       - no self-loops (``target_case_id == source_case_id``)
       - no communicated cases (``doctype ~* 'COM'`` with no JUD/DEC)
       - no targets dated after the source (``target_date > source_date``)
  3. Kind selection:
       - ``(dec.)`` / ``(déc.)`` / Commission decision cue -> prefer ``DEC``
       - otherwise -> prefer ``JUD`` (fall back to ``DEC`` only if no ``JUD``)
  4. Tie-breaking among multiple candidates of the chosen kind:
       a. exact cited date (EN/FR month names or DD.MM.YYYY / DD.MM.YY)
       b. cited year (``ECHR YYYY-X``, ``Reports YYYY-X``, ``, YYYY``, etc.)
       c. Grand Chamber formation (``[GC]`` / ``(GC)`` / ``Grand Chamber``)
       d. explicit secondary cue (just satisfaction, revision, interpretation,
          striking out, preliminary objections, article 50/41) or principal
          judgment over secondary follow-up
       e. candidate whose ECLI 9-digit primary appno matches a cited appno
       f. earliest ``(date_decision, item_id, case_id)``

Each resolved citation is emitted as a ``LinkRecord`` with
``source_dataset = "echr_edge_v2"``, ``relation_type = "cites"``,
``target_ref_scheme = "echr_appno"``, ``match_method = "appno/<rule>"``,
and a ``metadata`` mention carrying the raw ``scl`` entry.

Pure entry points: ``split_scl``, ``parse_scl_entry``, ``choose_target_for_entry``,
``resolve_case_scl``.
Database entry point: ``extract(conn, case_ids=None, id_range=None, out_path=...)``.
CLI: ``python -m data_extraction.linking.echr_edge_v2 --dsn-env VAR --from-id N
--to-id M --out PATH``.
"""

import datetime as dt
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from data_extraction.linking import resolver
from data_extraction.linking.artifact import (
    ArtifactWriter,
    CaseKey,
    DatasetWriters,
    LinkRecord,
    Mention,
    match_method,
)
from data_extraction.linking.text_common import cli_args, connect, iter_case_batches

log = logging.getLogger(__name__)

EXTRACTOR_VERSION = "echr_edge_v2/1.0.0"
SOURCE_DATASET = "echr_edge_v2"
DATASET = SOURCE_DATASET
DATASETS = (SOURCE_DATASET,)
RELATION = "cites"
SCHEMA = resolver.SCHEMA

# Application number pattern: 1-6 digits / 2 digits (not preceded/followed by digit or slash).
APPNO_RE = re.compile(r"(?<![0-9/])(\d{1,6})/(\d{2})(?![0-9/])")

# 9-digit appno tail in HUDOC ECLIs: ECLI:CE:ECHR:2026:1119JUD003766823 -> 37668/23
ECLI_APPNO_RE = re.compile(
    r"^ECLI:CE:ECHR:\d{4}:\d{4}(?:JUD|DEC|COM)(\d{7})(\d{2})$", re.IGNORECASE
)

# Decision cues in scl entries (including Eur. Comm. H.R. / Comm. eur. D.H. entries).
DECISION_CUE_RE = re.compile(
    r"(?:\(\s*d[eé]c\.?\s*\)"
    r"|\b(?:Commission\s+decision|d[eé]cision\s+de\s+la\s+Commission)\b"
    r"|\b(?:Eur\.?\s*Comm\.?\s*H\.?R\.?|Comm\.?\s*[Ee]ur\.?\s*D\.?H\.?)\b"
    r"|\bd[eé]c\.\s*\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{2,4}\b)",
    re.IGNORECASE,
)

# Sub-splitting patterns for older HUDOC scl rows where semicolons were omitted.
_NL_CONTINUATION_RE = re.compile(
    r"\s*\n+\s*(?=(?:d[eé]c\.|p\.|pp\.|§|D\.R\.|DR\b))", re.IGNORECASE
)
_DR_MISSING_SEMI_RE = re.compile(
    r"(pp?\.\s*\d+(?:,\s*\d+|[-–]\d+){0,6})\s*(?=(?:Nos?\.?\s+\d|N°|n°|Eur\.?\s*Comm\.?|Comm\.?\s*[Ee]ur\.?))"
)
_COMM_HEADER_SPLIT_RE = re.compile(
    r"(?<=\S)\s+(?=(?:Eur\.?\s*Comm\.?\s*H\.?R\.?|Comm\.?\s*[Ee]ur\.?\s*D\.?H\.?)\b)"
)
_AFTER_CITATION_TAIL_SPLIT_RE = re.compile(
    r"((?:ECHR|CEDH|Reports|Recueil)\s+(?:19|20)\d{2}(?:\s*[-–]\s*[IVX]+|\s+[IVX]+|\.\.\.)?(?:\s*\(extracts\))?"
    r"|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December"
    r"|janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)\s+(?:19|20)\d{2}"
    r"|\b\d{1,2}\.\d{1,2}\.(?:19|20)\d{2}"
    r"|\b\d{1,6}/\d{2}"
    r"|\)\s*,\s*(?:and|et))"
    r"(?:\s*,\s*(?:(?:and|et)\s+)?|\s*[:.]\s*|\s*)(?=(?-i:[A-ZÀ-Ý])[^\n;]{1,80}\s+(?:v\.|c\.)\s+)",
    re.IGNORECASE,
)
_SUBSPLIT_RE = re.compile(
    r"(?:(?<=\S)\s{2,}(?=(?:(?:Eur\.?\s*Comm\.?|Comm\.?\s*[Ee]ur\.?|Nos?\.|N°|n°|(?:Case\s+of|Affaire|Arr[eê]t)\b)"
    r"|[A-ZÀ-Ý][^\n;]{1,90}\s+(?:v\.|c\.)\s+))"
    r"|(?<=\S)\s+[:.]\s+(?=[A-ZÀ-Ý][^\n;]{1,90}\s+(?:v\.|c\.)\s+))"
)

# Grand Chamber cues in scl entries.
GC_CUE_RE = re.compile(
    r"(?:\[\s*GC\s*\]|\(\s*GC\s*\)|\bGrand\s+Chamber\b|\bGrande\s+Chambre\b)",
    re.IGNORECASE,
)

# Secondary judgment cues in scl entries and docnames.
SECONDARY_CUES: Tuple[Tuple[str, re.Pattern], ...] = (
    (
        "just_satisfaction",
        re.compile(
            r"(?:just\s+satisfaction|satisfaction\s+[eé]quitable|article\s+50|art\.\s*50|article\s+41|art\.\s*41)",
            re.IGNORECASE,
        ),
    ),
    ("revision", re.compile(r"(?:\(\s*r[eé]vision\s*\)|\br[eé]vision\b)", re.IGNORECASE)),
    (
        "interpretation",
        re.compile(r"(?:\(\s*interpr[eé]tation\s*\)|\binterpr[eé]tation\b)", re.IGNORECASE),
    ),
    (
        "striking_out",
        re.compile(r"(?:striking\s+out|radiation\s+du\s+r[oô]le|\(\s*radiation\s*\))", re.IGNORECASE),
    ),
    (
        "preliminary_objections",
        re.compile(
            r"(?:preliminary\s+objection|exception\s+pr[eé]liminaire|exceptions\s+pr[eé]liminaires)",
            re.IGNORECASE,
        ),
    ),
)

# Conclusion strings indicating a follow-up/secondary judgment when no merits violation/non-violation exists.
MERITS_CONCLUSION_RE = re.compile(
    r"\b(?:violation|non-violation|no\s+violation|no\s+separate\s+issue|aucune\s+question\s+distincte)\b",
    re.IGNORECASE,
)
SECONDARY_CONCLUSION_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    (
        "just_satisfaction",
        re.compile(
            r"(?:just\s+satisfaction|satisfaction\s+[eé]quitable|pecuniary\s+damage|non-pecuniary\s+damage|"
            r"dommage\s+mat[eé]riel|pr[eé]judice\s+moral|costs\s+and\s+expenses|frais\s+et\s+d[eé]pens)",
            re.IGNORECASE,
        ),
    ),
    ("revision", re.compile(r"(?:request\s+for\s+revision|demande\s+en\s+r[eé]vision|revision)", re.IGNORECASE)),
    (
        "interpretation",
        re.compile(r"(?:request\s+for\s+interpretation|demande\s+en\s+interpr[eé]tation)", re.IGNORECASE),
    ),
    ("striking_out", re.compile(r"(?:struck\s+out|radiation\s+du\s+r[oô]le)", re.IGNORECASE)),
    (
        "preliminary_objections",
        re.compile(r"(?:preliminary\s+objection|exception\s+pr[eé]liminaire)", re.IGNORECASE),
    ),
)

# Month maps (EN + FR, with and without diacritics).
MONTHS: Dict[str, int] = {
    "january": 1, "jan": 1, "janvier": 1, "janv": 1,
    "february": 2, "feb": 2, "fevrier": 2, "février": 2, "fev": 2, "fév": 2,
    "march": 3, "mar": 3, "mars": 3,
    "april": 4, "apr": 4, "avril": 4, "avr": 4,
    "may": 5, "mai": 5,
    "june": 6, "jun": 6, "juin": 6,
    "july": 7, "jul": 7, "juillet": 7, "juil": 7,
    "august": 8, "aug": 8, "aout": 8, "août": 8,
    "september": 9, "sep": 9, "sept": 9, "septembre": 9,
    "october": 10, "oct": 10, "octobre": 10,
    "november": 11, "nov": 11, "novembre": 11,
    "december": 12, "dec": 12, "decembre": 12, "décembre": 12, "déc": 12,
}

_MONTH_ALT = "|".join(sorted(MONTHS.keys(), key=len, reverse=True))
DATE_DMY_WORD_RE = re.compile(
    rf"\b(\d{{1,2}})(?:er|st|nd|rd|th)?\s+({_MONTH_ALT})\.?\s+((?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)
DATE_MDY_WORD_RE = re.compile(
    rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)
DATE_NUMERIC_RE = re.compile(r"\b(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*((?:19|20)\d{2}|\d{2})\b")

# Year extraction from `ECHR 2000-VI`, `CEDH 2001-XI`, `Reports 1997-VI`, `, 2005`, `(2005)`.
YEAR_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"\b(?:ECHR|CEDH|Reports|Recueil)\s+((?:19|20)\d{2})\b", re.IGNORECASE),
    re.compile(r"(?:,\s*|\(\s*)((?:19|20)\d{2})(?:\s*\)|\s*[-–]\s*[IVX]+|\s*$|\s*,)", re.IGNORECASE),
    re.compile(r"\b((?:19[5-9]\d|20[0-2]\d))\b"),
)


@dataclass(frozen=True)
class TargetCandidate:
    case_id: int
    ecli: Optional[str]
    item_id: Optional[str]
    date_decision: Optional[dt.date]
    kind: str  # 'judgment' | 'decision' | 'communicated' | 'other'
    branch: Optional[str]  # 'GRANDCHAMBER', 'CHAMBER', ...
    secondary_kind: Optional[str]  # None if principal, else 'just_satisfaction' | ...


@dataclass(frozen=True)
class ParsedSclEntry:
    raw: str
    appnos: Tuple[str, ...]
    decision_cue: bool
    grand_chamber: bool
    cited_date: Optional[dt.date]
    cited_year: Optional[int]
    secondary_cue: Optional[str]


@dataclass(frozen=True)
class ResolvedEdge:
    source_case_id: int
    source_ecli: Optional[str]
    source_item_id: Optional[str]
    target_case_id: int
    target_ecli: Optional[str]
    target_item_id: Optional[str]
    scl_reference: str
    appno: str
    rule: str


def normalize_appno(raw: str) -> Optional[str]:
    """Normalize an ECtHR application number ('0046221/99' -> '46221/99')."""
    if not raw:
        return None
    m = APPNO_RE.search(raw.strip())
    if not m:
        return None
    num = str(int(m.group(1)))
    yr = m.group(2)
    return f"{num}/{yr}"


def appno_from_ecli(ecli: Optional[str]) -> Optional[str]:
    """Recover the primary owner appno from a 9-digit HUDOC ECLI tail."""
    if not ecli:
        return None
    m = ECLI_APPNO_RE.match(ecli.strip())
    if not m:
        return None
    num = int(m.group(1))
    if num <= 0:
        return None
    return f"{num}/{m.group(2)}"


def classify_target_kind(has_jud: bool, has_dec: bool, has_com: bool) -> str:
    if has_jud:
        return "judgment"
    if has_dec:
        return "decision"
    if has_com:
        return "communicated"
    return "other"


def classify_secondary_judgment(docname: Optional[str], conclusion: Optional[str]) -> Optional[str]:
    """Identify whether an ECtHR judgment is a secondary follow-up judgment."""
    dn = docname or ""
    for label, pat in SECONDARY_CUES:
        if pat.search(dn):
            return label
    conc = conclusion or ""
    if conc and not MERITS_CONCLUSION_RE.search(conc):
        for label, pat in SECONDARY_CONCLUSION_PATTERNS:
            if pat.search(conc):
                return label
    return None


def parse_date_from_text(text: str) -> Optional[dt.date]:
    """Extract an exact calendar date from an EN or FR HUDOC scl entry."""
    for pat, order in (
        (DATE_DMY_WORD_RE, "dmy"),
        (DATE_MDY_WORD_RE, "mdy"),
        (DATE_NUMERIC_RE, "num"),
    ):
        m = pat.search(text)
        if not m:
            continue
        try:
            if order == "dmy":
                day = int(m.group(1))
                month = MONTHS[m.group(2).lower()]
                year = int(m.group(3))
            elif order == "mdy":
                month = MONTHS[m.group(1).lower()]
                day = int(m.group(2))
                year = int(m.group(3))
            else:
                day = int(m.group(1))
                month = int(m.group(2))
                yr_raw = m.group(3)
                year = int(yr_raw)
                if len(yr_raw) == 2:
                    year = 1900 + year if year >= 50 else 2000 + year
            return dt.date(year, month, day)
        except (ValueError, KeyError):
            continue
    return None


def parse_year_from_text(text: str, cited_date: Optional[dt.date]) -> Optional[int]:
    if cited_date is not None:
        return cited_date.year
    cleaned = APPNO_RE.sub(" ", text)
    cleaned = re.sub(r"§+\s*[\d\-–,\s]+", " ", cleaned)
    for pat in YEAR_PATTERNS:
        m = pat.search(cleaned)
        if m:
            yr = int(m.group(1))
            if 1959 <= yr <= 2030:
                return yr
    return None


def parse_scl_entry(entry: str) -> ParsedSclEntry:
    raw = entry.strip()
    appnos: List[str] = []
    seen: Set[str] = set()
    for m in APPNO_RE.finditer(raw):
        norm = f"{int(m.group(1))}/{m.group(2)}"
        if norm not in seen:
            seen.add(norm)
            appnos.append(norm)
    decision_cue = bool(DECISION_CUE_RE.search(raw))
    grand_chamber = bool(GC_CUE_RE.search(raw))
    cited_date = parse_date_from_text(raw)
    cited_year = parse_year_from_text(raw, cited_date)
    secondary_cue: Optional[str] = None
    for label, pat in SECONDARY_CUES:
        if pat.search(raw):
            secondary_cue = label
            break
    return ParsedSclEntry(
        raw=raw,
        appnos=tuple(appnos),
        decision_cue=decision_cue,
        grand_chamber=grand_chamber,
        cited_date=cited_date,
        cited_year=cited_year,
        secondary_cue=secondary_cue,
    )


def split_scl(scl: str) -> List[str]:
    if not scl:
        return []
    cleaned = _NL_CONTINUATION_RE.sub(" ", scl)
    cleaned = _DR_MISSING_SEMI_RE.sub(r"\1; ", cleaned)
    cleaned = _COMM_HEADER_SPLIT_RE.sub("; ", cleaned)
    cleaned = _AFTER_CITATION_TAIL_SPLIT_RE.sub(r"\1; ", cleaned)
    out: List[str] = []
    for chunk in re.split(r"[;\n]+", cleaned):
        chunk = chunk.strip()
        if not chunk:
            continue
        for sub in _SUBSPLIT_RE.split(chunk):
            sub = sub.strip()
            if sub:
                out.append(sub)
    return out


def choose_target_for_entry(
    parsed: ParsedSclEntry,
    source_case_id: int,
    source_date: Optional[dt.date],
    appno_index: Dict[str, List[TargetCandidate]],
) -> Optional[Tuple[TargetCandidate, str, str]]:
    """Resolve one parsed scl entry to (TargetCandidate, matched_appno, rule) or None."""
    if not parsed.appnos:
        return None

    by_case: Dict[int, Tuple[TargetCandidate, str]] = {}
    for ap in parsed.appnos:
        for cand in appno_index.get(ap, ()):
            if cand.case_id == source_case_id:
                continue
            if cand.kind == "communicated":
                continue
            if (
                source_date is not None
                and cand.date_decision is not None
                and cand.date_decision > source_date
            ):
                continue
            if cand.case_id not in by_case:
                by_case[cand.case_id] = (cand, ap)

    if not by_case:
        return None

    candidates = [pair[0] for pair in by_case.values()]
    judgments = [c for c in candidates if c.kind == "judgment"]
    decisions = [c for c in candidates if c.kind == "decision"]

    if parsed.decision_cue and decisions:
        pool = decisions
        rule = "scl_decision_cue"
    elif judgments:
        pool = judgments
        rule = "scl_judgment"
    elif decisions:
        pool = decisions
        rule = "scl_decision_no_judgment"
    else:
        return None

    pool = sorted(pool, key=lambda c: (c.date_decision or dt.date.max, c.item_id or "", c.case_id))

    if len(pool) > 1 and parsed.cited_date is not None:
        exact = [c for c in pool if c.date_decision == parsed.cited_date]
        if exact:
            pool = exact
            rule += "_exact_date"

    if len(pool) > 1 and parsed.cited_year is not None:
        same_year = [
            c for c in pool if c.date_decision is not None and c.date_decision.year == parsed.cited_year
        ]
        if same_year:
            pool = same_year
            rule += "_year"

    if len(pool) > 1 and parsed.grand_chamber:
        gc = [c for c in pool if (c.branch or "").upper() == "GRANDCHAMBER"]
        if gc:
            pool = gc
            rule += "_gc"

    if len(pool) > 1:
        if parsed.secondary_cue is not None:
            matched_sec = [c for c in pool if c.secondary_kind == parsed.secondary_cue]
            if matched_sec:
                pool = matched_sec
                rule += f"_{parsed.secondary_cue}"
        else:
            principals = [c for c in pool if c.secondary_kind is None]
            if principals:
                pool = principals
                rule += "_principal"

    if len(pool) > 1:
        cited_set = set(parsed.appnos)
        ecli_match = [c for c in pool if appno_from_ecli(c.ecli) in cited_set]
        if ecli_match and len(ecli_match) < len(pool):
            pool = ecli_match
            rule += "_ecli_appno"

    if len(pool) > 1:
        rule += "_earliest"

    chosen = pool[0]
    matched_appno = by_case[chosen.case_id][1]
    return chosen, matched_appno, rule


def confidence_for_rule(rule: str) -> float:
    """Confidence score matching the R6.1 historical backfill."""
    if "earliest" in rule:
        return 0.80
    if "decision_no_judgment" in rule:
        return 0.85
    if "year" in rule:
        return 0.90
    return 0.95


def resolve_case_scl(
    source_case_id: int,
    source_ecli: Optional[str],
    source_item_id: Optional[str],
    source_date: Optional[dt.date],
    scl_texts: Iterable[str],
    appno_index: Dict[str, List[TargetCandidate]],
) -> Tuple[List[ResolvedEdge], Counter]:
    """Resolve all scl entries for a single source case, deduplicating per target_case_id."""
    stats: Counter = Counter()
    chosen_by_target: Dict[int, ResolvedEdge] = {}
    seen_entries: Set[str] = set()

    for scl in scl_texts:
        for raw_entry in split_scl(scl):
            if raw_entry in seen_entries:
                continue
            seen_entries.add(raw_entry)
            stats["scl_entries_total"] += 1
            parsed = parse_scl_entry(raw_entry)
            if not parsed.appnos:
                stats["scl_entries_no_appno"] += 1
                continue
            stats["scl_entries_with_appno"] += 1
            res = choose_target_for_entry(parsed, source_case_id, source_date, appno_index)
            if res is None:
                stats["scl_entries_unresolved"] += 1
                continue
            cand, matched_appno, rule = res
            stats["scl_entries_resolved"] += 1
            if cand.case_id in chosen_by_target:
                stats["scl_entries_dedup_same_target"] += 1
                continue
            chosen_by_target[cand.case_id] = ResolvedEdge(
                source_case_id=source_case_id,
                source_ecli=source_ecli,
                source_item_id=source_item_id,
                target_case_id=cand.case_id,
                target_ecli=cand.ecli,
                target_item_id=cand.item_id,
                scl_reference=raw_entry[:500],
                appno=matched_appno,
                rule=rule,
            )

    return list(chosen_by_target.values()), stats


def edge_to_record(edge: ResolvedEdge) -> Optional[LinkRecord]:
    """Convert one ResolvedEdge to a LinkRecord, or None if natural keys are missing."""
    if not (edge.source_ecli or edge.source_item_id):
        return None
    if not (edge.target_ecli or edge.target_item_id):
        return None
    source_key = CaseKey(ecli=edge.source_ecli or None, item_id=edge.source_item_id or None)
    target_key = CaseKey(ecli=edge.target_ecli or None, item_id=edge.target_item_id or None)
    if source_key == target_key:
        return None
    mentions = (
        (Mention(text_field="metadata", raw_text=edge.scl_reference),)
        if edge.scl_reference
        else ()
    )
    record = LinkRecord(
        source=source_key,
        target=target_key,
        target_ref_raw=edge.appno,
        target_ref_scheme="echr_appno",
        relation_type=RELATION,
        source_dataset=SOURCE_DATASET,
        extractor_version=EXTRACTOR_VERSION,
        match_method=match_method("appno", edge.rule),
        confidence=confidence_for_rule(edge.rule),
        mentions=mentions,
    )
    record.validate()
    return record


# ---------------------------------------------------------------------------
# Database queries & batch extraction
# ---------------------------------------------------------------------------

_IDS_SQL = f"""
    SELECT DISTINCT d.case_id
      FROM {SCHEMA}.echr_document d
     WHERE d.case_id IS NOT NULL
       AND d.scl IS NOT NULL
       AND btrim(d.scl) <> ''
"""

_SOURCE_SCLS_SQL = f"""
    SELECT c.id,
           c.ecli,
           c.item_id,
           c.date_decision,
           d.scl
      FROM {SCHEMA}.cases c
      JOIN {SCHEMA}.echr_document d ON d.case_id = c.id
     WHERE c.id = ANY(%s)
       AND d.scl IS NOT NULL
       AND btrim(d.scl) <> ''
     ORDER BY c.id, d.item_id
"""

_TARGET_CANDIDATES_SQL = f"""
    WITH matched_cases AS (
        SELECT DISTINCT d.case_id
          FROM {SCHEMA}.echr_document_appno a
          JOIN {SCHEMA}.echr_document d ON d.item_id = a.item_id
         WHERE a.source = 'appno'
           AND a.appno = ANY(%(raw_appnos)s)
           AND d.case_id IS NOT NULL
        UNION
        SELECT DISTINCT ci.case_id
          FROM {SCHEMA}.case_identifier ci
         WHERE ci.scheme = 'echr_appno'
           AND ci.value_normalized = ANY(%(norm_appnos)s)
    )
    SELECT c.id,
           c.ecli,
           c.item_id,
           c.date_decision,
           bool_or(d.doctype ~* 'JUD') AS has_jud,
           bool_or(d.doctype ~* 'DEC') AS has_dec,
           bool_or(d.doctype ~* 'COM') AS has_com,
           bool_or(upper(COALESCE(d.doctype_branch, '')) = 'GRANDCHAMBER') AS is_gc,
           COALESCE(
               MAX(CASE WHEN d.doctype = 'HEJUD' THEN d.docname END),
               MAX(CASE WHEN d.doctype = 'HFJUD' THEN d.docname END),
               MAX(d.docname)
           ) AS docname,
           COALESCE(
               MAX(CASE WHEN d.doctype = 'HEJUD' THEN d.conclusion END),
               MAX(CASE WHEN d.doctype = 'HFJUD' THEN d.conclusion END),
               MAX(d.conclusion)
           ) AS conclusion,
           array_remove(array_agg(DISTINCT a.appno), NULL) AS owner_appnos,
           array_remove(array_agg(DISTINCT ci.value_normalized), NULL) AS ident_appnos
      FROM matched_cases mc
      JOIN {SCHEMA}.cases c ON c.id = mc.case_id
      JOIN {SCHEMA}.echr_document d ON d.case_id = c.id
      LEFT JOIN {SCHEMA}.echr_document_appno a
        ON a.item_id = d.item_id AND a.source = 'appno'
      LEFT JOIN {SCHEMA}.case_identifier ci
        ON ci.case_id = c.id AND ci.scheme = 'echr_appno'
     GROUP BY c.id, c.ecli, c.item_id, c.date_decision
"""


def _appno_raw_variants(norm_appnos: Iterable[str]) -> List[str]:
    """Expand normalized appnos ('123/99') with common zero-padded forms stored in HUDOC."""
    variants: Set[str] = set()
    for ap in norm_appnos:
        variants.add(ap)
        num, sep, yr = ap.partition("/")
        if sep and num.isdigit():
            for width in (5, 6, 7):
                if len(num) < width:
                    variants.add(f"{num.zfill(width)}/{yr}")
    return sorted(variants)


def _as_date(value) -> Optional[dt.date]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def fetch_target_candidates(cursor, norm_appnos: Set[str]) -> Dict[str, List[TargetCandidate]]:
    """Fetch owner target candidates for the given normalized appnos."""
    if not norm_appnos:
        return {}
    norm_sorted = sorted(norm_appnos)
    cursor.execute(
        _TARGET_CANDIDATES_SQL,
        {"raw_appnos": _appno_raw_variants(norm_sorted), "norm_appnos": norm_sorted},
    )
    appno_index: Dict[str, List[TargetCandidate]] = defaultdict(list)
    for row in cursor.fetchall():
        (
            case_id,
            ecli,
            item_id,
            date_decision,
            has_jud,
            has_dec,
            has_com,
            is_gc,
            docname,
            conclusion,
            owner_appnos,
            ident_appnos,
        ) = row
        kind = classify_target_kind(bool(has_jud), bool(has_dec), bool(has_com))
        branch = "GRANDCHAMBER" if is_gc else None
        sec_kind = (
            classify_secondary_judgment(docname, conclusion)
            if kind == "judgment"
            else None
        )
        cand = TargetCandidate(
            case_id=int(case_id),
            ecli=ecli or None,
            item_id=item_id or None,
            date_decision=_as_date(date_decision),
            kind=kind,
            branch=branch,
            secondary_kind=sec_kind,
        )
        seen_ap: Set[str] = set()
        for raw_ap in list(owner_appnos or ()) + list(ident_appnos or ()):
            norm = normalize_appno(raw_ap)
            if norm and norm not in seen_ap:
                seen_ap.add(norm)
                appno_index[norm].append(cand)
        if not seen_ap:
            fallback_ap = appno_from_ecli(cand.ecli)
            if fallback_ap:
                appno_index[fallback_ap].append(cand)
    return dict(appno_index)


def extract_batch(cursor, case_ids: Sequence[int]) -> List[LinkRecord]:
    """Extract echr_edge_v2 LinkRecords for a batch of source case_ids."""
    if not case_ids:
        return []
    cursor.execute(_SOURCE_SCLS_SQL, (list(case_ids),))
    rows = cursor.fetchall()
    if not rows:
        return []

    sources: Dict[int, Tuple[Optional[str], Optional[str], Optional[dt.date], List[str]]] = {}
    for case_id, ecli, item_id, date_decision, scl in rows:
        cid = int(case_id)
        if cid not in sources:
            sources[cid] = (ecli or None, item_id or None, _as_date(date_decision), [])
        sources[cid][3].append(scl)

    # Collect all distinct normalized appnos referenced across the batch's scl entries
    # so target lookup is a single indexed query per batch.
    needed_appnos: Set[str] = set()
    for _cid, (_ecli, _item_id, _date, scl_texts) in sources.items():
        for scl in scl_texts:
            for raw_entry in split_scl(scl):
                for m in APPNO_RE.finditer(raw_entry):
                    needed_appnos.add(f"{int(m.group(1))}/{m.group(2)}")

    appno_index = fetch_target_candidates(cursor, needed_appnos)

    records: List[LinkRecord] = []
    for cid in sorted(sources):
        ecli, item_id, date_decision, scl_texts = sources[cid]
        edges, _stats = resolve_case_scl(
            source_case_id=cid,
            source_ecli=ecli,
            source_item_id=item_id,
            source_date=date_decision,
            scl_texts=scl_texts,
            appno_index=appno_index,
        )
        for edge in edges:
            record = edge_to_record(edge)
            if record is not None:
                records.append(record)
    return records


def _is_dir(out_path) -> bool:
    return os.path.isdir(out_path) or str(out_path).endswith(os.sep)


def open_writers(out_path, datasets=DATASETS):
    if _is_dir(out_path):
        os.makedirs(out_path, exist_ok=True)
        return DatasetWriters({d: os.path.join(out_path, f"{d}.jsonl") for d in datasets})
    return ArtifactWriter(out_path)


def _written(writers):
    if isinstance(writers, DatasetWriters):
        return writers.counts
    return {"all": writers.count}


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size=500):
    """Resolve HUDOC scl citations for ECtHR cases and write the link artifact.

    Returns {"records": n, "by_dataset": {...}, "written": {...}}.
    """
    total, by_dataset = 0, {}
    writers = open_writers(out_path) if out_path else ArtifactWriter(None)
    with writers, conn.cursor() as cursor:
        for ids in iter_case_batches(
            conn, _IDS_SQL, case_ids=case_ids, id_range=id_range, batch_size=batch_size
        ):
            records = extract_batch(cursor, ids)
            conn.rollback()  # read-only; release snapshot between batches
            for record in records:
                by_dataset[record.source_dataset] = by_dataset.get(record.source_dataset, 0) + 1
            total += writers.write(records)
            log.info("echr_edge_v2: up to case %s, %s records", ids[-1], total)
    written = _written(writers) if out_path else {}
    return {"records": total, "by_dataset": by_dataset, "written": written}


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = cli_args("ECtHR scl metadata -> ECtHR case links (R6.1)", argv)
    conn = connect(args.dsn_env)
    try:
        result = extract(
            conn,
            case_ids=args.case_id,
            id_range=(args.from_id, args.to_id),
            out_path=args.out,
            batch_size=args.batch_size,
        )
    finally:
        conn.close()
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
