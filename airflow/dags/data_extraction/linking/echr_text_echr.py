"""Extract outgoing ECtHR -> ECtHR citations from fulltext for empty-scl ECHR judgments.

HUDOC's structured ``scl`` (Strasbourg Case-Law) column is empty for ~60,800
Importance-4 (and ~1,550 Importance-2/3) ECtHR judgments/decisions that carry full
text citing prior ECtHR cases (e.g., ``see Ananyev and Others v. Russia, nos.
42525/07 and 60800/08, § 78, 10 January 2012``).

This extractor scans only the body (stripping the header and any APPENDIX /
ANNEXE table of joined applicant numbers), parses each cited ECtHR application-
number clause, excludes the source case's own application numbers, and delegates
target selection to ``echr_edge_v2.choose_target_for_entry`` (owner appnos only,
no self-loops, no communicated cases, no post-dated targets).

Emits ``source_dataset = 'echr_text_echr'`` (relation ``'cites'``) into
``cle_v2.case_citation`` via ``link_loader.load_artifact`` (or direct JSONL
replay in ``etl-promoter``).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from data_extraction.linking import echr_edge_v2
from data_extraction.linking.artifact import (
    ArtifactWriter,
    CaseKey,
    LinkRecord,
    Mention,
    match_method,
)

log = logging.getLogger(__name__)

SCHEMA = echr_edge_v2.SCHEMA
DATASET = "echr_text_echr"
EXTRACTOR_VERSION = "echr_text_echr/1.0.0"
RELATION = "cites"

# Appendix / joined-applications table markers: never scan past these.
_APPENDIX_RE = re.compile(
    r"(?:^|\n)\s*(?:APPENDIX|ANNEXE|LIST\s+OF\s+APPLICATIONS|LISTE\s+DES\s+REQU[ÊE]TES|"
    r"APPENDED\s+TABLE|TABLEAU\s+ANNEXE)\b",
    re.IGNORECASE,
)

# Header end markers: skip header boilerplate ("(Application no. 37668/23)") before the body.
_BODY_START_RE = re.compile(
    r"(?:^|\n)\s*(?:SUBJECT\s+MATTER\s+OF\s+THE\s+CASE|THE\s+FACTS|PROCEDURE|EN\s+FAIT|"
    r"OBJET\s+DE\s+L['’]AFFAIRE|THE\s+COURT['’]S\s+ASSESSMENT|APPR[ÉE]CIATION\s+DE\s+LA\s+COUR|"
    r"THE\s+LAW|EN\s+DROIT|1\s*\.\s+[A-ZÀ-Ý])",
    re.IGNORECASE,
)

# Citation clause containing ECtHR application number(s), tolerating missing-'s' OCR/DOCX artifacts
# ("no .", "no . 42525/07") and both EN/FR markers ("no.", "nos.", "n°", "nº", "nos").
_APPNO_MARKER_RE = re.compile(
    r"\b(?:applications?\s+nos?\s*\.?|requ[êe]tes?\s+n[°ºo]s?\s*\.?|nos?\s*\.|n[°ºo]s?\s*\.?)\s*"
    r"(?P<list>\d{1,6}/\d{2}(?![\d/])(?:\s*(?:,|;|and|et)\s*\d{1,6}/\d{2}(?![\d/]))*)",
    re.IGNORECASE,
)

# Reject domestic legislation / decree / regulation references right before the number marker.
_DOMESTIC_LAW_RE = re.compile(
    r"(?:\b(?:law|laws|act|decree|order|regulation|directive|decision|resolution|circular|"
    r"statute|code|section|article|loi|d[ée]cret|arr[êe]t[ée]|r[èe]glement|ordonnance|"
    r"circulaire|wet|besluit|verordening|richtlijn|protocol|convention|case|criminal\s+case|"
    r"file|dossier|proc[ée]dure|judgment\s+of\s+the\s+(?:supreme|constitutional|regional|district))\s*$)",
    re.IGNORECASE,
)

# Positive ECtHR precedent cues in the surrounding window (~160 chars before, ~120 chars after).
_PRECEDENT_BEFORE_RE = re.compile(
    r"(?:\b(?:v\.|c\.)\s+[A-ZÀ-Ý]|\b(?:see|cf\.|voir|comp\.|above|cited\s+above|pr[ée]cit[ée]e?)\b"
    r"|\[GC\]|\(GC\)|\(\s*d[eé]c\.?\s*\))",
    re.IGNORECASE,
)
_PRECEDENT_AFTER_RE = re.compile(
    r"(?:§|\bparas?\.|\b(?:ECHR|CEDH|Reports|Recueil)\s+(?:19|20)\d{2}\b"
    r"|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December"
    r"|janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+(?:19|20)\d{2}\b"
    r"|\b\d{1,2}\.\d{1,2}\.(?:19|20)\d{2}\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedCitationClause:
    appnos: Tuple[str, ...]
    raw_clause: str
    char_start: int
    char_end: int


def strip_header_and_appendix(text: str) -> Tuple[str, int]:
    """Return (body_slice, start_offset) excluding header appnos and appended tables."""
    if not text:
        return "", 0
    end = len(text)
    app_m = _APPENDIX_RE.search(text)
    if app_m is not None:
        end = app_m.start()
    start = 0
    body_m = _BODY_START_RE.search(text, 0, end)
    if body_m is not None and body_m.start() < min(end, 4000):
        start = body_m.start()
    return text[start:end], start


def extract_citation_clauses(
    text: str,
    own_appnos: Set[str],
) -> List[ExtractedCitationClause]:
    """Find ECtHR precedent clauses with application numbers in body text."""
    body, base_offset = strip_header_and_appendix(text)
    if not body:
        return []

    clauses: List[ExtractedCitationClause] = []
    for m in _APPNO_MARKER_RE.finditer(body):
        prefix = body[max(0, m.start() - 80) : m.start()]
        if _DOMESTIC_LAW_RE.search(prefix.rstrip(" ,;:((")):
            continue
        # Skip "the application (no. 12345/06) lodged..." referring to the applicant's own case
        if re.search(r"\b(?:the\s+application|la\s+requ[êe]te|present\s+application)\s*\(?\s*$", prefix, re.I):
            continue

        before_win = body[max(0, m.start() - 160) : m.start()]
        after_win = body[m.end() : min(len(body), m.end() + 140)]
        if not (_PRECEDENT_BEFORE_RE.search(before_win) or _PRECEDENT_AFTER_RE.search(after_win)):
            continue

        appnos = [
            echr_edge_v2.normalize_appno(a)
            for a in re.findall(r"\d{1,6}/\d{2}", m.group("list"))
        ]
        appnos = [a for a in appnos if a and a not in own_appnos]
        if not appnos:
            continue

        # Capture the surrounding citation snippet (from last sentence/paren boundary to next)
        c_start = max(
            0,
            before_win.rfind("("),
            before_win.rfind(";"),
            before_win.rfind("\n"),
        )
        # Convert c_start relative to before_win into body coordinates
        win_base = max(0, m.start() - 160)
        snip_start = win_base + c_start
        # End at closing paren, semicolon, newline, or end of after_win
        tail_cuts = [p for p in (after_win.find(")"), after_win.find(";"), after_win.find("\n")) if p != -1]
        snip_end = m.end() + (min(tail_cuts) + 1 if tail_cuts else min(len(after_win), 100))
        raw_clause = " ".join(body[snip_start:snip_end].split())[:300]

        clauses.append(
            ExtractedCitationClause(
                appnos=tuple(dict.fromkeys(appnos)),
                raw_clause=raw_clause,
                char_start=base_offset + m.start(),
                char_end=base_offset + m.end(),
            )
        )
    return clauses


def resolve_case_fulltext(
    source_case_id: int,
    source_key: CaseKey,
    source_date: Optional[dt.date],
    own_appnos: Set[str],
    texts: Sequence[Tuple[Optional[str], str]],
    owner_by_appno: Dict[str, List[echr_edge_v2.TargetCandidate]],
    stats: Optional[Counter] = None,
) -> List[LinkRecord]:
    """Resolve ECtHR precedent citations in one empty-scl case's fulltext(s)."""
    counts = stats if stats is not None else Counter()
    by_target: Dict[int, Tuple[echr_edge_v2.TargetCandidate, str, str, float, List[Mention]]] = {}

    for lang, text in texts:
        for clause in extract_citation_clauses(text, own_appnos):
            counts["clauses_scanned"] += 1
            parsed = echr_edge_v2.parse_scl_entry(clause.raw_clause)
            entry = echr_edge_v2.ParsedSclEntry(
                raw=clause.raw_clause,
                appnos=clause.appnos,
                decision_cue=parsed.decision_cue,
                grand_chamber=parsed.grand_chamber,
                cited_date=parsed.cited_date,
                cited_year=parsed.cited_year,
                secondary_cue=parsed.secondary_cue,
            )
            res = echr_edge_v2.choose_target_for_entry(
                entry,
                source_case_id=source_case_id,
                source_date=source_date,
                appno_index=owner_by_appno,
            )
            if res is None:
                counts["dropped:unresolved"] += 1
                continue
            chosen, matched_appno, rule = res
            if chosen.ecli is None and chosen.item_id is None:
                counts["dropped:no_target_key"] += 1
                continue
            counts[f"resolved:{rule}"] += 1
            conf = min(0.90, echr_edge_v2.confidence_for_rule(rule))
            m = Mention(
                text_field="fulltext",
                language=lang,
                text_source="HUDOC",
                char_start=clause.char_start,
                char_end=clause.char_end,
                raw_text=clause.raw_clause[:200],
                context=clause.raw_clause,
            )
            prev = by_target.get(chosen.case_id)
            if prev is None:
                by_target[chosen.case_id] = (chosen, matched_appno, rule, conf, [m])
            else:
                prev[4].append(m)

    records: List[LinkRecord] = []
    for _cid, (chosen, raw_appno, rule, conf, mentions) in sorted(by_target.items()):
        target_key = CaseKey(ecli=chosen.ecli, item_id=chosen.item_id)
        if target_key == source_key:
            continue
        rec = LinkRecord(
            source=source_key,
            target=target_key,
            relation_type=RELATION,
            source_dataset=DATASET,
            extractor_version=EXTRACTOR_VERSION,
            match_method=match_method("appno", rule),
            confidence=conf,
            target_ref_scheme="echr_appno",
            target_ref_raw=raw_appno,
            mentions=tuple(mentions[:5]),
        )
        records.append(rec)
    return records


def extract_pending(
    conn,
    limit: int = 2000,
    out_path: Optional[str] = None,
    load: bool = False,
) -> Dict[str, Any]:
    """Extract outgoing ECtHR citations from empty-scl ECHR fulltexts (newest cases first)."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT c.id, c.ecli, c.item_id, c.date_decision
              FROM {SCHEMA}.cases c
              JOIN {SCHEMA}.echr_document ed ON ed.case_id = c.id
             WHERE c.ecli LIKE 'ECLI:CE:ECHR:%%'
               AND (ed.scl IS NULL OR trim(ed.scl) = '')
               AND NOT EXISTS (
                   SELECT 1 FROM {SCHEMA}.case_citation cc
                    WHERE cc.source_case_id = c.id
                      AND cc.source_dataset IN ('echr_edge_v2', %s)
               )
               AND EXISTS (
                   SELECT 1 FROM {SCHEMA}.case_text ct
                    WHERE ct.case_id = c.id AND ct.fulltext IS NOT NULL
               )
             GROUP BY c.id, c.ecli, c.item_id, c.date_decision
             ORDER BY c.id DESC
             LIMIT %s
            """,
            (DATASET, limit),
        )
        source_rows = cur.fetchall()
    conn.rollback()

    if not source_rows:
        if out_path:
            with ArtifactWriter(out_path):
                pass
        return {"candidates": 0, "cases_with_hits": 0, "records": 0, "load": {}}

    case_ids = [int(r[0]) for r in source_rows]
    # Load owner appnos for the source cases so we never self-cite joined applicant numbers.
    own_by_case: Dict[int, Set[str]] = {cid: set() for cid in case_ids}
    texts_by_case: Dict[int, List[Tuple[Optional[str], str]]] = {cid: [] for cid in case_ids}
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT ed.case_id, a.appno
              FROM {SCHEMA}.echr_document ed
              JOIN {SCHEMA}.echr_document_appno a ON a.item_id = ed.item_id
             WHERE ed.case_id = ANY(%s) AND a.source = 'appno'
            """,
            (case_ids,),
        )
        for cid, appno in cur.fetchall():
            norm = echr_edge_v2.normalize_appno(appno)
            if norm:
                own_by_case.setdefault(int(cid), set()).add(norm)
        cur.execute(
            f"""
            SELECT case_id, language, fulltext
              FROM {SCHEMA}.case_text
             WHERE case_id = ANY(%s) AND fulltext IS NOT NULL
             ORDER BY case_id, language, id
            """,
            (case_ids,),
        )
        for cid, lang, text in cur.fetchall():
            texts_by_case.setdefault(int(cid), []).append((lang, text))
    conn.rollback()

    # Pre-scan cited appnos across the batch so target lookup is one indexed query.
    needed_appnos: Set[str] = set()
    for cid, ecli, _item_id, _dec_date in source_rows:
        cid_int = int(cid)
        own = own_by_case.setdefault(cid_int, set())
        ecli_app = echr_edge_v2.appno_from_ecli(ecli)
        if ecli_app:
            own.add(ecli_app)
        for _lang, text in texts_by_case.get(cid_int, ()):
            for clause in extract_citation_clauses(text, own):
                needed_appnos.update(clause.appnos)

    with conn.cursor() as cur:
        owner_by_appno = echr_edge_v2.fetch_target_candidates(cur, needed_appnos)
    conn.rollback()

    stats: Counter = Counter()
    all_records: List[LinkRecord] = []
    cases_with_hits = 0
    for cid, ecli, item_id, dec_date in source_rows:
        cid_int = int(cid)
        key = CaseKey(ecli=ecli or None, item_id=item_id or None)
        own = own_by_case.get(cid_int, set())
        recs = resolve_case_fulltext(
            source_case_id=cid_int,
            source_key=key,
            source_date=echr_edge_v2._as_date(dec_date),
            own_appnos=own,
            texts=texts_by_case.get(cid_int, ()),
            owner_by_appno=owner_by_appno,
            stats=stats,
        )
        if recs:
            cases_with_hits += 1
            all_records.extend(recs)

    if out_path:
        with ArtifactWriter(out_path) as writer:
            writer.write(all_records)

    load_stats: Dict[str, Any] = {}
    if load and out_path and all_records:
        from data_loading import link_loader

        load_stats = link_loader.load_artifact(conn, out_path)

    return {
        "candidates": len(source_rows),
        "cases_with_hits": cases_with_hits,
        "records": len(all_records),
        "stats": dict(stats),
        "load": load_stats,
    }


def load_artifact(conn, path: str) -> Dict[str, Any]:
    """Load an echr_text_echr.jsonl artifact into cle_v2.case_citation via link_loader."""
    if not os.path.exists(path):
        return {}
    from data_loading import link_loader

    return link_loader.load_artifact(conn, path)
