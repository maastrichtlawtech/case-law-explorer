"""Extract UN human rights & refugee treaty citations from ECtHR HUDOC fulltexts.

HUDOC metadata (`echr_article`) already populates ECHR Convention & Protocol
articles cleanly, and `echr_text_eu_law` extracts EU directives/regulations/Charter.
This module closes the remaining ECHR -> international treaty gap by scanning
HUDOC EN/FR fulltexts for all 9 curated UN treaties in ``cle_v2.legislation``:

  * V-2   1951 Convention relating to the Status of Refugees (Geneva Convention)
  * V-5   1967 Protocol relating to the Status of Refugees
  * IV-2  ICERD (Elimination of All Forms of Racial Discrimination)
  * IV-3  ICESCR (Economic, Social and Cultural Rights)
  * IV-4  ICCPR (Civil and Political Rights)
  * IV-8  CEDAW (Elimination of Discrimination against Women)
  * IV-9  CAT / UNCAT (Convention against Torture)
  * IV-11 CRC / UNCRC (Convention on the Rights of the Child)
  * IV-15 CRPD / UNCRPD (Rights of Persons with Disabilities)

Emits ``source_dataset = 'echr_text_treaty'`` into ``cle_v2.case_law_reference``
under the partial unique index ``case_law_reference_uk_echr_treaty`` (migration 0020).
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from data_extraction.linking import cjeu_treaty
from data_extraction.linking.cjeu_treaty import TreatyHit, TreatyRefRecord

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
DATASET = "echr_text_treaty"
EXTRACTOR_VERSION = "echr_treaty/1.0.0"
ROLE = "cited"

_ART_SPEC = cjeu_treaty._ART_SPEC
_OPT_SEP = cjeu_treaty._OPT_SEP
_NOT_L = cjeu_treaty._NOT_ECLI_L
_NOT_R = cjeu_treaty._NOT_ECLI_R

# Additional 5 UN treaties (beyond the 4 in cjeu_treaty._UN_TREATIES) -> all 9 UN treaties covered.
_EXTRA_UN_TREATIES: Tuple[Tuple[str, int, re.Pattern, re.Pattern], ...] = (
    # 1967 Protocol relating to the Status of Refugees (un_treaty / V-5)
    (
        "V-5",
        11,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of(?:\s+the)?|du)?[\s\u00a0]*"
            r"(?:1967\s+Protocol\s+relating\s+to\s+the\s+Status\s+of\s+Refugees"
            r"|Protocol\s+relating\s+to\s+the\s+Status\s+of\s+Refugees"
            r"|Protocole\s+relatif\s+au\s+statut\s+des\s+r[ée]fugi[ée]s)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:Protocol\s+relating\s+to\s+the\s+Status\s+of\s+Refugees"
            r"|Protocole\s+relatif\s+au\s+statut\s+des\s+r[ée]fugi[ée]s)",
            re.IGNORECASE,
        ),
    ),
    # ICERD (un_treaty / IV-2)
    (
        "IV-2",
        25,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of(?:\s+the)?|de(?:\s+la)?)?[\s\u00a0]*"
            r"(?:" + _NOT_L + r"ICERD" + _NOT_R
            + r"|International\s+Convention\s+on\s+the\s+Elimination\s+of\s+All\s+Forms\s+of\s+Racial\s+Discrimination"
            r"|Convention\s+internationale\s+sur\s+l['’][ée]limination\s+de\s+toutes\s+les\s+formes\s+de\s+discrimination\s+raciale)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:" + _NOT_L + r"ICERD" + _NOT_R
            + r"|International\s+Convention\s+on\s+the\s+Elimination\s+of\s+All\s+Forms\s+of\s+Racial\s+Discrimination"
            r"|Convention\s+internationale\s+sur\s+l['’][ée]limination\s+de\s+toutes\s+les\s+formes\s+de\s+discrimination\s+raciale)",
            re.IGNORECASE,
        ),
    ),
    # ICESCR (un_treaty / IV-3)
    (
        "IV-3",
        31,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of(?:\s+the)?|du|de)?[\s\u00a0]*"
            r"(?:" + _NOT_L + r"ICESCR" + _NOT_R
            + r"|International\s+Covenant\s+on\s+Economic,\s+Social\s+and\s+Cultural\s+Rights"
            r"|Pacte\s+international\s+relatif\s+aux\s+droits\s+[ée]conomiques,\s+sociaux\s+et\s+culturels)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:" + _NOT_L + r"ICESCR" + _NOT_R
            + r"|International\s+Covenant\s+on\s+Economic,\s+Social\s+and\s+Cultural\s+Rights"
            r"|Pacte\s+international\s+relatif\s+aux\s+droits\s+[ée]conomiques,\s+sociaux\s+et\s+culturels)",
            re.IGNORECASE,
        ),
    ),
    # CEDAW (un_treaty / IV-8)
    (
        "IV-8",
        30,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of(?:\s+the)?|de(?:\s+la)?)?[\s\u00a0]*"
            r"(?:" + _NOT_L + r"CEDAW" + _NOT_R
            + r"|Convention\s+on\s+the\s+Elimination\s+of\s+All\s+Forms\s+of\s+Discrimination\s+against\s+Women"
            r"|Convention\s+sur\s+l['’][ée]limination\s+de\s+toutes\s+les\s+formes\s+de\s+discrimination\s+[àa]\s+l['’][ée]gard\s+des\s+femmes)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:" + _NOT_L + r"CEDAW" + _NOT_R
            + r"|Convention\s+on\s+the\s+Elimination\s+of\s+All\s+Forms\s+of\s+Discrimination\s+against\s+Women"
            r"|Convention\s+sur\s+l['’][ée]limination\s+de\s+toutes\s+les\s+formes\s+de\s+discrimination\s+[àa]\s+l['’][ée]gard\s+des\s+femmes)",
            re.IGNORECASE,
        ),
    ),
    # CAT / UNCAT (un_treaty / IV-9)
    (
        "IV-9",
        33,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of(?:\s+the)?|de(?:\s+la)?)?[\s\u00a0]*"
            r"(?:" + _NOT_L + r"UNCAT" + _NOT_R
            + r"|(?:UN\s+|United\s+Nations\s+)?Convention\s+against\s+Torture(?:\s+and\s+Other\s+Cruel,\s+Inhuman\s+or\s+Degrading\s+Treatment\s+or\s+Punishment)?"
            r"|Convention\s+(?:des\s+Nations\s+[Uu]nies\s+)?contre\s+la\s+torture(?:\s+et\s+autres\s+peines\s+ou\s+traitements\s+cruels,\s+inhumains\s+ou\s+d[ée]gradants)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:" + _NOT_L + r"UNCAT" + _NOT_R
            + r"|(?:UN\s+|United\s+Nations\s+)?Convention\s+against\s+Torture(?:\s+and\s+Other\s+Cruel,\s+Inhuman\s+or\s+Degrading\s+Treatment\s+or\s+Punishment)?"
            r"|Convention\s+(?:des\s+Nations\s+[Uu]nies\s+)?contre\s+la\s+torture(?:\s+et\s+autres\s+peines\s+ou\s+traitements\s+cruels,\s+inhumains\s+ou\s+d[ée]gradants)?)",
            re.IGNORECASE,
        ),
    ),
)

ALL_UN_TREATIES = cjeu_treaty._UN_TREATIES + _EXTRA_UN_TREATIES


def scan(text: str, language: Optional[str] = None) -> List[TreatyHit]:
    """Scan one HUDOC text for UN treaty citations (skipping ECHR/Protocols covered by echr_article)."""
    if not text:
        return []
    hits: List[TreatyHit] = []
    covered: List[Tuple[int, int]] = []
    seen_acts: set[Tuple[str, str]] = set()

    for ident, max_art, art_re, whole_re in ALL_UN_TREATIES:
        for m in art_re.finditer(text):
            if cjeu_treaty._overlaps((m.start(), m.end()), covered):
                continue
            art_raw, p1, p2 = m.group(1), m.group(2), m.group(3)
            num = cjeu_treaty._article_number_int(art_raw)
            if num is None or not (1 <= num <= max_art):
                continue
            if ident == "V-2" and not any(
                w in m.group(0).lower()
                for w in ("refugee", "réfugié", "flüchtling", "vluchteling", "1951")
            ):
                ctx = text[max(0, m.start() - 250) : m.end() + 250].lower()
                if not any(
                    w in ctx
                    for w in ("refugee", "réfugié", "flüchtling", "vluchteling", "asylum", "asile", "1951")
                ):
                    continue
            art, sub = cjeu_treaty._format_subdivision(art_raw, p1, p2)
            hits.append(
                TreatyHit(
                    scheme="un_treaty",
                    identifier=ident,
                    article=art,
                    raw_subdivision=sub,
                    match_method="treaty_article",
                    confidence=0.95,
                    start=m.start(),
                    end=m.end(),
                    raw_text=cjeu_treaty._clean_ref(m.group(0)),
                )
            )
            covered.append((m.start(), m.end()))
            seen_acts.add(("un_treaty", ident))

        if ("un_treaty", ident) not in seen_acts:
            m = whole_re.search(text)
            if m is not None and not cjeu_treaty._overlaps((m.start(), m.end()), covered):
                hits.append(
                    TreatyHit(
                        scheme="un_treaty",
                        identifier=ident,
                        article=None,
                        raw_subdivision=None,
                        match_method="treaty_name",
                        confidence=0.90,
                        start=m.start(),
                        end=m.end(),
                        raw_text=cjeu_treaty._clean_ref(m.group(0)),
                    )
                )
                seen_acts.add(("un_treaty", ident))
    return hits


def records_for_case(
    ecli: Optional[str],
    texts: Iterable[Tuple[Optional[str], str]],
) -> List[TreatyRefRecord]:
    merged: Dict[Tuple[str, str, str], TreatyHit] = {}
    acts_with_articles: set[Tuple[str, str]] = set()
    for lang, text in texts:
        for hit in scan(text, language=lang):
            if hit.article is not None:
                acts_with_articles.add((hit.scheme, hit.identifier))
            key = (hit.scheme, hit.identifier, hit.raw_subdivision or "")
            prev = merged.get(key)
            if prev is None or hit.confidence > prev.confidence:
                merged[key] = hit

    out: List[TreatyRefRecord] = []
    for (scheme, ident, sub), hit in sorted(merged.items()):
        if not sub and (scheme, ident) in acts_with_articles:
            continue
        out.append(
            TreatyRefRecord(
                ecli=ecli or None,
                celex=None,
                scheme=scheme,
                identifier=ident,
                raw_subdivision=hit.raw_subdivision,
                article=hit.article,
                raw_reference=hit.raw_text,
                match_method=hit.match_method,
                confidence=hit.confidence,
                source_dataset=DATASET,
                extractor_version=EXTRACTOR_VERSION,
            )
        )
    return out


_INSERT_RESOLVED_SQL = f"""
    INSERT INTO {SCHEMA}.case_law_reference (
        case_id, legislation_id, provision_id,
        raw_scheme, raw_resource, raw_subdivision, raw_reference,
        role, source_dataset, extractor_version, match_method, confidence
    )
    SELECT case_id, legislation_id, provision_id,
           raw_scheme, raw_resource, raw_subdivision, raw_reference,
           role, source_dataset, extractor_version, match_method, confidence
      FROM (VALUES %s) AS v(
        ord, case_id, legislation_id, provision_id,
        raw_scheme, raw_resource, raw_subdivision, raw_reference,
        role, source_dataset, extractor_version, match_method, confidence
      )
     ORDER BY ord
    ON CONFLICT (case_id, raw_scheme, raw_resource, COALESCE(raw_subdivision, ''), role, source_dataset)
    WHERE raw_resource IS NOT NULL
      AND (legislation_id IS NOT NULL OR provision_id IS NOT NULL)
      AND source_dataset = 'echr_text_treaty'
    DO NOTHING
    RETURNING provision_id
"""


def load_records(conn, records: Sequence[TreatyRefRecord], batch_size: int = 1000) -> Dict[str, int]:
    """Idempotently load echr_text_treaty TreatyRefRecords into cle_v2.case_law_reference."""
    from psycopg2.extras import execute_values

    stats: Counter = Counter()
    if not records:
        return {}
    with conn.cursor() as cur:
        eclis = sorted({r.ecli for r in records if r.ecli})
        case_by_ecli: Dict[str, int] = {}
        if eclis:
            cur.execute(f"SELECT ecli, id FROM {SCHEMA}.cases WHERE ecli = ANY(%s)", (eclis,))
            case_by_ecli = {e: int(i) for e, i in cur.fetchall()}

        schemes = sorted({r.scheme for r in records})
        idents = sorted({r.identifier for r in records})
        cur.execute(
            f"SELECT scheme, identifier, min(id) FROM {SCHEMA}.legislation "
            "WHERE scheme = ANY(%s) AND identifier = ANY(%s) GROUP BY scheme, identifier",
            (schemes, idents),
        )
        leg_map: Dict[Tuple[str, str], int] = {(s, i): int(lid) for s, i, lid in cur.fetchall()}

        wanted_lids = sorted(set(leg_map.values()))
        wanted_arts = sorted({r.article.lower() for r in records if r.article})
        prov_map: Dict[Tuple[int, str], int] = {}
        if wanted_lids and wanted_arts:
            cur.execute(
                f"SELECT legislation_id, lower(article_label), min(id) FROM {SCHEMA}.legal_provision "
                "WHERE legislation_id = ANY(%s) AND element_type = 'article' AND lower(article_label) = ANY(%s) "
                "GROUP BY legislation_id, lower(article_label)",
                (wanted_lids, wanted_arts),
            )
            prov_map = {(int(lid), art): int(pid) for lid, art, pid in cur.fetchall()}

        for start in range(0, len(records), batch_size):
            chunk = records[start : start + batch_size]
            resolved_rows: List[Tuple[Any, ...]] = []
            seen: set[Tuple[Any, ...]] = set()
            for r in chunk:
                cid = case_by_ecli.get(r.ecli) if r.ecli else None
                if cid is None:
                    stats["source_missing"] += 1
                    continue
                lid = leg_map.get((r.scheme, r.identifier))
                if lid is None:
                    stats["legislation_missing"] += 1
                    continue
                nkey = (cid, r.scheme, r.identifier, r.raw_subdivision or "", r.role, r.source_dataset)
                if nkey in seen:
                    continue
                seen.add(nkey)
                pid = prov_map.get((lid, r.article.lower())) if r.article else None
                resolved_rows.append((
                    len(resolved_rows),
                    cid, lid, pid,
                    r.scheme, r.identifier, r.raw_subdivision, r.raw_reference,
                    r.role, r.source_dataset, r.extractor_version, r.match_method, r.confidence,
                ))
            if resolved_rows:
                ret = execute_values(
                    cur, _INSERT_RESOLVED_SQL, resolved_rows,
                    template=cjeu_treaty._ROW_TEMPLATE, page_size=len(resolved_rows), fetch=True,
                )
                stats["inserted"] += len(ret)
                stats["with_provision"] += sum(1 for (pid,) in ret if pid is not None)
                stats["existing"] += len(resolved_rows) - len(ret)
        conn.commit()
    return {k: v for k, v in stats.items() if v}


def load_artifact(conn, path: str) -> Dict[str, int]:
    if not os.path.exists(path):
        return {}
    return load_records(conn, cjeu_treaty.read_jsonl(path))


_CANDIDATE_TSQUERY = (
    "'ICCPR' | 'ICESCR' | 'ICERD' | 'CEDAW' | 'UNCAT' | 'UNCRC' | 'UNCRPD' | 'CRPD' | "
    "('Geneva' & 'Refugees') | ('Genève' & 'réfugiés') | "
    "('Status' & 'Refugees') | ('statut' & 'réfugiés') | "
    "('Covenant' & 'Civil' & 'Political') | ('Pacte' & 'civils' & 'politiques') | "
    "('Covenant' & 'Economic' & 'Cultural') | ('Pacte' & 'économiques' & 'culturels') | "
    "('Convention' & 'against' & 'Torture') | ('Convention' & 'contre' & 'torture') | "
    "('Rights' & 'Child' & 'Convention') | ('droits' & 'enfant' & 'Convention') | "
    "('Persons' & 'Disabilities') | ('personnes' & 'handicapées') | "
    "('Elimination' & 'Racial' & 'Discrimination') | ('élimination' & 'discrimination' & 'raciale') | "
    "('Elimination' & 'Discrimination' & 'Women') | ('élimination' & 'discrimination' & 'femmes')"
)


def extract_pending(
    conn,
    limit: int = 2000,
    out_path: Optional[str] = None,
    load: bool = False,
) -> Dict[str, Any]:
    """Find newest ECHR cases mentioning UN treaties that don't yet have echr_text_treaty rows."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT c.id
              FROM {SCHEMA}.cases c
             WHERE c.ecli LIKE 'ECLI:CE:ECHR:%%'
               AND NOT EXISTS (
                   SELECT 1 FROM {SCHEMA}.case_law_reference r
                    WHERE r.case_id = c.id AND r.source_dataset = %s
               )
               AND EXISTS (
                   SELECT 1 FROM {SCHEMA}.case_text ct
                    WHERE ct.case_id = c.id
                      AND ct.source = 'HUDOC'
                      AND ct.fulltext_tsv @@ to_tsquery('simple', %s)
               )
             ORDER BY c.id DESC
             LIMIT %s
            """,
            (DATASET, _CANDIDATE_TSQUERY, limit),
        )
        case_ids = [int(row[0]) for row in cur.fetchall()]
    conn.rollback()

    all_records: List[TreatyRefRecord] = []
    cases_with_hits = 0
    if case_ids:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.id, c.ecli, ct.language, ct.fulltext
                  FROM {SCHEMA}.case_text ct
                  JOIN {SCHEMA}.cases c ON c.id = ct.case_id
                 WHERE c.id = ANY(%s) AND ct.source = 'HUDOC' AND ct.fulltext IS NOT NULL
                 ORDER BY c.id, ct.language, ct.id
                """,
                (case_ids,),
            )
            grouped: Dict[int, Tuple[Optional[str], List[Tuple[Optional[str], str]]]] = {}
            for cid, ecli, lang, text in cur.fetchall():
                entry = grouped.get(cid)
                if entry is None:
                    entry = grouped[cid] = (ecli, [])
                entry[1].append((lang, text))
        conn.rollback()
        for cid in sorted(grouped):
            ecli, texts = grouped[cid]
            recs = records_for_case(ecli, texts)
            if recs:
                cases_with_hits += 1
                all_records.extend(recs)

    if out_path:
        cjeu_treaty.write_jsonl(out_path, all_records)
    load_stats = load_records(conn, all_records) if load and all_records else {}
    return {
        "candidates": len(case_ids),
        "cases_with_hits": cases_with_hits,
        "records": len(all_records),
        "load": load_stats,
    }
