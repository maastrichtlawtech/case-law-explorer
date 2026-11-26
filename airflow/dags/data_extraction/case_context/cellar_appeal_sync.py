"""Sync multi-valued CJEU procedure outcomes and appeal statuses from Cellar SPARQL.

Cellar's ``cdm:case-law_has_type_procedure_concept_type_procedure`` (``fd_100``)
frequently carries multiple values per case (e.g. ``ANNU`` *and* ``PVOI%3DOB``
for a successful appeal of an annulment judgment).  ``cjeu_document.proc_type``
only stores the first value returned by the corpus loader, which hides appeal
outcomes and ``overturned`` statuses.

This module queries EUR-Lex Cellar SPARQL for CJEU appeal decisions that either
lack a ``cjeu_proc_type`` outcome or participate in an ``appeal_of`` /
``subject_to_appeal`` link without a ``cjeu_appeal_status`` row, emits standard
``OutcomeRecord`` and ``StatusRecord`` JSONL artifacts (so ``etl-promoter`` can
replay the exact hashed files into production), and loads them idempotently via
``data_loading.outcome_loader``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from data_extraction.case_context import case_status, cjeu_outcomes
from data_extraction.case_context.artifact import OutcomeRecord, StatusRecord, case_key
from data_extraction.linking.artifact import ArtifactWriter

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
EXTRACTOR_VERSION = "cellar_appeal_sync/1.0.0"

_CELEX_DECISION_RE = re.compile(r"^6\d{4}(?:CJ|TJ|FJ|CO|TO|FO|CV|CD)\d{4}", re.I)

# fd_100 concept codes -> (outcome, raw_value, is_appeal)
FD100_MAP: Dict[str, Tuple[str, str, bool]] = {
    "PVOI%3DOB": ("successful", "Appeal - successful", True),
    "SANC%3DOB": ("successful", "Appeal - successful", True),
    "PVOI%3DNF": ("unfounded", "Appeal - unfounded", True),
    "SANC%3DNF": ("unfounded", "Appeal - unfounded", True),
    "PVOI%3DIR": ("inadmissible", "Appeal - inadmissible", True),
    "PVOI%3DNL": ("decision_unnecessary", "Appeal - decision unnecessary", True),
    "PVOI%3DMI": ("interlocutory", "Appeal - interlocutory judgment", True),
    "ANNU%3DOB": ("successful", "Action for annulment - successful", False),
    "ANNU%3DNF": ("unfounded", "Action for annulment - unfounded", False),
    "ANNU%3DIR": ("inadmissible", "Action for annulment - inadmissible", False),
    "ANNU%3DNL": ("decision_unnecessary", "Action for annulment - decision unnecessary", False),
    "MANQ%3DOB": ("successful", "Action for failure to fulfil obligations - successful", False),
    "MANQ%3DNF": ("unfounded", "Action for failure to fulfil obligations - unfounded", False),
    "MANQ%3DIR": ("inadmissible", "Action for failure to fulfil obligations - inadmissible", False),
    "MANQ%3DNL": ("decision_unnecessary", "Action for failure to fulfil obligations - decision unnecessary", False),
    "PREJ%3DIR": ("inadmissible", "Reference for a preliminary ruling - inadmissible", False),
    "PREJ%3DNL": ("decision_unnecessary", "Reference for a preliminary ruling - decision unnecessary", False),
    "FONC%3DOB": ("successful", "Staff cases - successful", False),
    "FONC%3DNF": ("unfounded", "Staff cases - unfounded", False),
    "FONC%3DIR": ("inadmissible", "Staff cases - inadmissible", False),
    "FONC%3DNL": ("decision_unnecessary", "Staff cases - decision unnecessary", False),
    "FONC%3DRA": ("amicable_settlement", "Staff cases - amicable settlement", False),
    "RESP%3DOB": ("successful", "Action for damages - successful", False),
    "RESP%3DNF": ("unfounded", "Action for damages - unfounded", False),
    "RESP%3DIR": ("inadmissible", "Action for damages - inadmissible", False),
    "RESP%3DNL": ("decision_unnecessary", "Action for damages - decision unnecessary", False),
    "CARE%3DOB": ("successful", "Action for failure to act - successful", False),
    "CARE%3DNF": ("unfounded", "Action for failure to act - unfounded", False),
    "CARE%3DIR": ("inadmissible", "Action for failure to act - inadmissible", False),
    "CARE%3DNL": ("decision_unnecessary", "Action for failure to act - decision unnecessary", False),
    "AVIS%3DCO": ("agreement_compatible", "Request for an Opinion - agreement compatible", False),
    "AVIS%3DIN": ("agreement_incompatible", "Request for an Opinion - agreement incompatible", False),
}


def build_sparql_query(celexes: Sequence[str]) -> str:
    safe = [c for c in celexes if c and _CELEX_DECISION_RE.match(c) and '"' not in c]
    vals = " ".join(f'"{c}"^^xsd:string' for c in safe)
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?celex ?tp
WHERE {{
  VALUES ?celex {{ {vals} }}
  ?w cdm:resource_legal_id_celex ?celex ;
     cdm:case-law_has_type_procedure_concept_type_procedure ?tp .
}}
"""


def parse_fd100_bindings(bindings: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Return {celex: sorted distinct fd_100 code strings}."""
    by_celex: Dict[str, set[str]] = {}
    for binding in bindings:
        celex = (binding.get("celex") or {}).get("value")
        tp_uri = (binding.get("tp") or {}).get("value") or ""
        if not celex or not tp_uri:
            continue
        code = tp_uri.rsplit("/", 1)[-1]
        if code:
            by_celex.setdefault(celex, set()).add(code)
    return {c: sorted(codes) for c, codes in by_celex.items()}


def fetch_fd100_codes(
    celexes: Sequence[str],
    *,
    endpoint: str = SPARQL_ENDPOINT,
    batch_size: int = 120,
    pause: float = 0.5,
    urlopen: Optional[Callable] = None,
) -> Dict[str, List[str]]:
    opener = urlopen or urllib.request.urlopen
    ordered = sorted({c for c in celexes if c and _CELEX_DECISION_RE.match(c)})
    found: Dict[str, set[str]] = {}
    for idx in range(0, len(ordered), batch_size):
        chunk = ordered[idx : idx + batch_size]
        query = build_sparql_query(chunk)
        payload = urllib.parse.urlencode({"query": query}).encode("utf-8")
        data: Dict[str, Any] = {"results": {"bindings": []}}
        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={
                        "Accept": "application/sparql-results+json",
                        "User-Agent": "CaseLawExplorer/1.0 (https://caselawexplorer.tech)",
                    },
                )
                with opener(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except Exception as exc:
                if attempt == 3:
                    log.warning("Cellar appeal SPARQL batch %d failed: %s", idx, exc)
                else:
                    time.sleep(3.0 * (attempt + 1))
        for c, codes in parse_fd100_bindings(data.get("results", {}).get("bindings", [])).items():
            found.setdefault(c, set()).update(codes)
        if pause and idx + batch_size < len(ordered):
            time.sleep(pause)
    return {c: sorted(codes) for c, codes in found.items()}


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def build_records(
    appeal_pairs: Sequence[Dict[str, Any]],
    fd100_by_celex: Dict[str, List[str]],
) -> Tuple[List[OutcomeRecord], List[StatusRecord]]:
    """Build OutcomeRecord (cjeu_proc_type) and StatusRecord (cjeu_appeal_status) lists."""
    outcomes_by_key: Dict[Tuple[Any, str], OutcomeRecord] = {}
    statuses_by_key: Dict[Tuple[Any, Optional[date]], StatusRecord] = {}

    for row in appeal_pairs:
        a_celex = row.get("a_celex")
        if not a_celex or not cjeu_outcomes.is_decision_celex(a_celex):
            continue
        codes = fd100_by_celex.get(a_celex) or []
        if not codes:
            continue
        a_key = case_key(ecli=row.get("a_ecli"), celex=a_celex)
        u_key = case_key(ecli=row.get("u_ecli"), celex=row.get("u_celex"))
        a_date = _as_date(row.get("a_date"))
        for code in codes:
            mapped = FD100_MAP.get(code)
            if mapped is None:
                continue
            outcome, raw_value, is_appeal = mapped
            if a_key is not None:
                outcomes_by_key.setdefault(
                    (a_key, outcome),
                    OutcomeRecord(
                        case=a_key,
                        outcome=outcome,
                        raw_value=raw_value,
                        confidence=cjeu_outcomes.CONFIDENCE,
                        rule="cellar_sparql_fd100",
                        source_dataset=cjeu_outcomes.SOURCE_DATASET,
                        extractor_version=EXTRACTOR_VERSION,
                    ).validate(),
                )
            if is_appeal and outcome == "successful" and u_key is not None and a_key is not None and u_key != a_key:
                statuses_by_key.setdefault(
                    (u_key, a_date),
                    StatusRecord(
                        case=u_key,
                        status="overturned",
                        status_date=a_date,
                        related=a_key,
                        raw_value=raw_value,
                        confidence=case_status.CONFIDENCE["appeal_successful"],
                        rule="cellar_sparql_appeal_successful",
                        source_dataset=case_status.CJEU_DATASET,
                        extractor_version=EXTRACTOR_VERSION,
                    ).validate(),
                )

    return list(outcomes_by_key.values()), list(statuses_by_key.values())


def sync_connection(
    conn,
    *,
    out_dir: Optional[str] = None,
    batch_size: int = 120,
    pause: float = 0.5,
    urlopen: Optional[Callable] = None,
    load: bool = True,
) -> Dict[str, Any]:
    """Query Cellar SPARQL for CJEU appeal pairs missing outcomes/overturned statuses."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT a.id, a.ecli, COALESCE(ad.celex_id, a.celex_id) AS a_celex, a.date_decision,
                   u.id, u.ecli, COALESCE(ud.celex_id, u.celex_id) AS u_celex
              FROM {SCHEMA}.case_citation cc
              JOIN {SCHEMA}.cases a
                ON a.id = CASE cc.relation_type WHEN 'appeal_of' THEN cc.source_case_id
                                                ELSE cc.target_case_id END
              JOIN {SCHEMA}.cases u
                ON u.id = CASE cc.relation_type WHEN 'appeal_of' THEN cc.target_case_id
                                                ELSE cc.source_case_id END
              LEFT JOIN {SCHEMA}.cjeu_document ad ON ad.case_id = a.id
              LEFT JOIN {SCHEMA}.cjeu_document ud ON ud.case_id = u.id
             WHERE cc.relation_type IN ('appeal_of', 'subject_to_appeal')
               AND cc.target_case_id IS NOT NULL
               AND cc.source_case_id <> cc.target_case_id
               AND COALESCE(ad.celex_id, a.celex_id) IS NOT NULL
               AND (
                   NOT EXISTS (
                       SELECT 1 FROM {SCHEMA}.case_outcome co
                        WHERE co.case_id = a.id AND co.source_dataset = 'cjeu_proc_type'
                   )
                   OR NOT EXISTS (
                       SELECT 1 FROM {SCHEMA}.case_status cs
                        WHERE cs.case_id = u.id AND cs.status = 'overturned'
                          AND cs.source_dataset = 'cjeu_appeal_status'
                   )
               )
            """
        )
        pairs = [
            {
                "a_id": r[0],
                "a_ecli": r[1],
                "a_celex": r[2],
                "a_date": r[3],
                "u_id": r[4],
                "u_ecli": r[5],
                "u_celex": r[6],
            }
            for r in cur.fetchall()
        ]
    conn.rollback()

    celexes = sorted({p["a_celex"] for p in pairs if p.get("a_celex") and _CELEX_DECISION_RE.match(p["a_celex"])})
    fd100 = (
        fetch_fd100_codes(celexes, batch_size=batch_size, pause=pause, urlopen=urlopen)
        if celexes
        else {}
    )
    outcomes, statuses = build_records(pairs, fd100)

    out_paths: Dict[str, str] = {}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        outcomes_path = os.path.join(out_dir, "cjeu_proc_type_sparql.jsonl")
        statuses_path = os.path.join(out_dir, "cjeu_appeal_status_sparql.jsonl")
        with ArtifactWriter(outcomes_path) as writer:
            writer.write(outcomes)
        with ArtifactWriter(statuses_path) as writer:
            writer.write(statuses)
        out_paths = {"outcomes": outcomes_path, "statuses": statuses_path}

    loaded: Dict[str, Any] = {}
    if load and out_paths:
        from data_loading import outcome_loader

        for key, path in out_paths.items():
            loaded[key] = outcome_loader.load_artifact(conn, path)
    elif load and (outcomes or statuses):
        import tempfile
        from data_loading import outcome_loader

        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, "cjeu_proc_type_sparql.jsonl")
            p2 = os.path.join(tmp, "cjeu_appeal_status_sparql.jsonl")
            with ArtifactWriter(p1) as w:
                w.write(outcomes)
            with ArtifactWriter(p2) as w:
                w.write(statuses)
            loaded["outcomes"] = outcome_loader.load_artifact(conn, p1)
            loaded["statuses"] = outcome_loader.load_artifact(conn, p2)

    return {
        "candidate_appeal_pairs": len(pairs),
        "queried_celexes": len(celexes),
        "found_in_cellar": len(fd100),
        "outcomes_prepared": len(outcomes),
        "statuses_prepared": len(statuses),
        "loaded": loaded,
    }
