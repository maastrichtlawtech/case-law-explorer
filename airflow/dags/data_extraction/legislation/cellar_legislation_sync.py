"""Sync unresolved EU legislation CELEX acts from EUR-Lex CELLAR SPARQL.

Discovers every distinct unresolved `raw_scheme = 'celex'` reference in
`cle_v2.case_law_reference`, fetches official metadata (English title with
French fallback, enacted date, ELI, resource type) from EUR-Lex CELLAR's public
SPARQL endpoint, inserts new acts into `cle_v2.legislation` (idempotent
`ON CONFLICT DO NOTHING`), and resolves matching `case_law_reference` rows.

Designed to run both as a scheduled Airflow DAG (`eu_legislation_etl`) after
weekly Cellar/Rechtspraak/ECtHR loads and as a standalone CLI backfill.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from data_extraction.linking import eu_law

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
SOURCE_DATASET = "cellar_legislation_sparql"
EXTRACTOR_VERSION = "cellar_legislation_sync/1.0.0"

RESOURCE_TYPE_MAP = {
    "REG": "regulation",
    "REG_IMPL": "regulation",
    "REG_DEL": "regulation",
    "REG_FINANC": "regulation",
    "DIR": "directive",
    "DIR_IMPL": "directive",
    "DIR_DEL": "directive",
    "DEC": "decision",
    "DEC_IMPL": "decision",
    "DEC_DEL": "decision",
    "DEC_FRAMW": "framework_decision",
    "DEC_ENTSCHEID": "decision",
    "TREATY": "treaty",
    "PROT": "protocol",
    "CONVENTION": "convention",
    "AGREE_INTERNATION": "agreement",
    "AGREE_INTERNAL": "agreement",
    "RECO": "recommendation",
    "OPIN": "opinion",
    "RES": "resolution",
    "RULES_PROC": "rules_of_procedure",
    "STATUTE": "statute",
}

CELEX_TYPE_FALLBACK = {
    "R": "regulation",
    "L": "directive",
    "D": "decision",
    "F": "framework_decision",
    "Q": "rules_of_procedure",
    "A": "agreement",
    "X": "other",
    "E": "treaty",
    "M": "treaty",
    "C": "treaty",
    "P": "charter",
}


@dataclass(frozen=True)
class CellarAct:
    identifier: str
    document_type: str
    title: str
    enacted_date: Optional[str]
    enacted_year: Optional[int]
    eli: Optional[str]


def fallback_doc_type(celex: str) -> str:
    if len(celex) >= 6:
        if celex[0] == "1":
            return "protocol" if "/PRO" in celex else "treaty"
        return CELEX_TYPE_FALLBACK.get(celex[5].upper(), "eu_act")
    return "eu_act"


def year_from_celex(celex: str) -> Optional[int]:
    match = re.match(r"^[0-9CE](\d{4})", celex)
    if not match:
        return None
    year = int(match.group(1))
    return year if 1950 <= year <= 2100 else None


def candidate_celexes_for_raw(raw_resource: str) -> List[str]:
    """Return ordered canonical CELEX candidates for a raw_resource value."""
    cands: List[str] = []
    target = eu_law.cellar_target(raw_resource)
    if target is not None:
        cands.append(target.identifier)
        for alt in target.alternatives or ():
            if alt not in cands:
                cands.append(alt)
    if raw_resource not in cands:
        cands.append(raw_resource)
    return cands


def build_sparql_query(celexes: Sequence[str]) -> str:
    safe = [c for c in celexes if c and '"' not in c and "\\" not in c and "\n" not in c]
    vals = " ".join(f'"{c}"^^xsd:string' for c in safe)
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?celex
       (SAMPLE(?en_t) AS ?title_en)
       (SAMPLE(?fr_t) AS ?title_fr)
       (SAMPLE(?date) AS ?enacted_date)
       (SAMPLE(?eli) AS ?eli)
       (SAMPLE(?rt) AS ?resource_type)
WHERE {{
  VALUES ?celex {{ {vals} }}
  ?w cdm:resource_legal_id_celex ?celex .
  OPTIONAL {{ ?w cdm:work_date_document ?date }}
  OPTIONAL {{ ?w cdm:resource_legal_eli ?eli }}
  OPTIONAL {{ ?w cdm:work_has_resource-type ?rt }}
  OPTIONAL {{
    ?expr_en cdm:expression_belongs_to_work ?w ;
             cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ;
             cdm:expression_title ?en_t .
  }}
  OPTIONAL {{
    ?expr_fr cdm:expression_belongs_to_work ?w ;
             cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/FRA> ;
             cdm:expression_title ?fr_t .
  }}
}}
GROUP BY ?celex
"""


def parse_sparql_bindings(bindings: Iterable[Dict[str, Any]]) -> Dict[str, CellarAct]:
    out: Dict[str, CellarAct] = {}
    for binding in bindings:
        celex = binding["celex"]["value"]
        raw_title = (binding.get("title_en") or binding.get("title_fr") or {}).get("value")
        title = " ".join(raw_title.split())[:1000] if raw_title else f"EU Act {celex}"
        raw_date = (binding.get("enacted_date") or {}).get("value")
        enacted_date = (
            raw_date[:10] if raw_date and re.match(r"^\d{4}-\d{2}-\d{2}", raw_date) else None
        )
        enacted_year = int(enacted_date[:4]) if enacted_date else year_from_celex(celex)
        eli = (binding.get("eli") or {}).get("value")
        rt_uri = (binding.get("resource_type") or {}).get("value", "")
        rt_code = rt_uri.rsplit("/", 1)[-1] if rt_uri else ""
        doc_type = RESOURCE_TYPE_MAP.get(rt_code, fallback_doc_type(celex))
        out[celex] = CellarAct(
            identifier=celex,
            document_type=doc_type,
            title=title,
            enacted_date=enacted_date,
            enacted_year=enacted_year,
            eli=eli,
        )
    return out


def fetch_cellar_metadata(
    celexes: Sequence[str],
    *,
    endpoint: str = SPARQL_ENDPOINT,
    batch_size: int = 120,
    pause: float = 0.15,
    urlopen: Optional[Callable] = None,
) -> Dict[str, CellarAct]:
    opener = urlopen or urllib.request.urlopen
    found: Dict[str, CellarAct] = {}
    ordered = sorted({c for c in celexes if c})
    for idx in range(0, len(ordered), batch_size):
        chunk = ordered[idx : idx + batch_size]
        query = build_sparql_query(chunk)
        payload = urllib.parse.urlencode({"query": query}).encode("utf-8")
        data: Dict[str, Any] = {"results": {"bindings": []}}
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={"Accept": "application/sparql-results+json"},
                )
                with opener(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except Exception as exc:
                if attempt == 2:
                    log.warning("SPARQL batch %d failed after 3 attempts: %s", idx, exc)
                else:
                    time.sleep(1.5 * (attempt + 1))
        found.update(parse_sparql_bindings(data.get("results", {}).get("bindings", [])))
        if pause and idx + batch_size < len(ordered):
            time.sleep(pause)
    return found


_INSERT_LEGISLATION = f"""
INSERT INTO {SCHEMA}.legislation (
    scheme, identifier, jurisdiction_id, document_type, title,
    enacted_date, enacted_year, eli, source_dataset, extractor_version
)
SELECT
    'celex', u.identifier, j.id, u.document_type, u.title,
    u.enacted_date, u.enacted_year, u.eli, u.source_dataset, u.extractor_version
  FROM unnest(
      %s::text[], %s::text[], %s::text[], %s::date[], %s::smallint[],
      %s::text[], %s::text[], %s::text[]
  ) AS u(
      identifier, document_type, title, enacted_date, enacted_year,
      eli, source_dataset, extractor_version
  )
  JOIN {SCHEMA}.jurisdiction j ON j.iso_code = 'EU'
ON CONFLICT (scheme, identifier)
WHERE scheme IN ('celex', 'coe_treaty', 'un_treaty')
DO NOTHING
"""

_RESOLVE_REFS = f"""
UPDATE {SCHEMA}.case_law_reference clr
   SET legislation_id = m.leg_id
  FROM unnest(%s::text[], %s::bigint[]) AS m(raw_res, leg_id)
 WHERE clr.raw_scheme = 'celex'
   AND clr.raw_resource = m.raw_res
   AND clr.legislation_id IS NULL
   AND NOT EXISTS (
       SELECT 1
         FROM {SCHEMA}.case_law_reference dup
        WHERE dup.case_id = clr.case_id
          AND dup.raw_scheme = clr.raw_scheme
          AND dup.raw_resource = clr.raw_resource
          AND COALESCE(dup.raw_subdivision, '') = COALESCE(clr.raw_subdivision, '')
          AND dup.role = clr.role
          AND dup.source_dataset = clr.source_dataset
          AND (dup.legislation_id IS NOT NULL OR dup.provision_id IS NOT NULL)
   )
"""


def sync_connection(
    conn,
    *,
    batch_size: int = 120,
    pause: float = 0.15,
    urlopen: Optional[Callable] = None,
) -> Dict[str, int]:
    """Discover missing CELEX acts, fetch from Cellar SPARQL, insert & resolve."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT identifier, id FROM {SCHEMA}.legislation WHERE scheme = 'celex'"
        )
        existing: Dict[str, int] = {row[0]: int(row[1]) for row in cur.fetchall()}
        cur.execute(
            f"""
            SELECT a.alias, a.legislation_id
              FROM {SCHEMA}.legislation_alias a
              JOIN {SCHEMA}.legislation l ON l.id = a.legislation_id
             WHERE l.scheme IN ('celex', 'coe_treaty', 'un_treaty')
            """
        )
        for alias, leg_id in cur.fetchall():
            existing.setdefault(alias, int(leg_id))
        cur.execute(
            f"""
            SELECT DISTINCT raw_resource
              FROM {SCHEMA}.case_law_reference
             WHERE legislation_id IS NULL
               AND raw_scheme = 'celex'
               AND raw_resource IS NOT NULL
            """
        )
        raw_resources = [row[0] for row in cur.fetchall()]

    raw_to_cands: Dict[str, List[str]] = {}
    missing: set[str] = set()
    for raw in raw_resources:
        cands = candidate_celexes_for_raw(raw)
        raw_to_cands[raw] = cands
        for cand in cands:
            if cand not in existing:
                missing.add(cand)

    acts = (
        fetch_cellar_metadata(sorted(missing), batch_size=batch_size, pause=pause, urlopen=urlopen)
        if missing
        else {}
    )
    acts_inserted = 0
    if acts:
        rows = [
            (
                a.identifier,
                a.document_type,
                a.title,
                a.enacted_date,
                a.enacted_year,
                a.eli,
                SOURCE_DATASET,
                EXTRACTOR_VERSION,
            )
            for a in acts.values()
        ]
        with conn.cursor() as cur:
            for i in range(0, len(rows), 500):
                cols = list(zip(*rows[i : i + 500]))
                cur.execute(_INSERT_LEGISLATION, [list(col) for col in cols])
                acts_inserted += max(cur.rowcount, 0)
        conn.commit()

    # Reload full celex -> legislation.id map
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT identifier, id FROM {SCHEMA}.legislation WHERE scheme = 'celex'"
        )
        leg_map: Dict[str, int] = {row[0]: int(row[1]) for row in cur.fetchall()}
        cur.execute(
            f"""
            SELECT a.alias, a.legislation_id
              FROM {SCHEMA}.legislation_alias a
              JOIN {SCHEMA}.legislation l ON l.id = a.legislation_id
             WHERE l.scheme IN ('celex', 'coe_treaty', 'un_treaty')
            """
        )
        for alias, leg_id in cur.fetchall():
            leg_map.setdefault(alias, int(leg_id))

    pairs: List[Tuple[str, int]] = []
    for raw, cands in raw_to_cands.items():
        for cand in cands:
            if cand in leg_map:
                pairs.append((raw, leg_map[cand]))
                break

    refs_resolved = 0
    if pairs:
        with conn.cursor() as cur:
            for i in range(0, len(pairs), 500):
                chunk = pairs[i : i + 500]
                cur.execute(_RESOLVE_REFS, ([p[0] for p in chunk], [p[1] for p in chunk]))
                refs_resolved += max(cur.rowcount, 0)
        conn.commit()

    return {
        "distinct_unresolved_raw": len(raw_resources),
        "queried_sparql": len(missing),
        "found_in_cellar": len(acts),
        "acts_inserted": acts_inserted,
        "raw_resources_mapped": len(pairs),
        "refs_resolved": refs_resolved,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    import psycopg2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn-env", default="POSTGRES_DSN")
    parser.add_argument("--batch-size", type=int, default=120)
    args = parser.parse_args(argv)
    dsn = os.environ[args.dsn_env]
    conn = psycopg2.connect(dsn)
    try:
        summary = sync_connection(conn, batch_size=args.batch_size)
    finally:
        conn.close()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
