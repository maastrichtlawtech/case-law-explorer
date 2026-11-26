"""Read-only dataset health overview collector and Markdown reporter.

Runs safely against any ``cle_v2`` database (``db-dev`` from Airflow or live
production ``db`` from ``etl-promoter``) with zero side effects unless
``save_snapshot`` is explicitly called.

Covers:
  1. Corpus freshness & scrape recency (RS, CJEU, ECHR): total cases, full-text
     coverage %, latest decision date, latest ingest timestamp, 7d/30d additions.
  2. ETL watermarks & recent promotion batches (failures / stuck batches).
  3. Cross-dataset citation links per source_dataset (resolved/unresolved/% +
     active_in_api & counted flags).
  4. Case identifiers per scheme.
  5. Legislation catalog & law references per source_dataset (resolution %).
  6. Cited authority documents & references per kind / source_dataset.
  7. Case outcomes, case statuses, and citation count views.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"

# Staleness thresholds in days for latest decision / ingest date warnings.
DEFAULT_FRESHNESS_WARN_DAYS: Dict[str, int] = {
    "RS": 14,
    "CJEU": 30,
    "ECHR": 30,
}

DEFAULT_MIN_TEXT_COVERAGE: Dict[str, float] = {
    "RS": 0.25,
    "CJEU": 0.90,
    "ECHR": 0.85,
}


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _days_since(value: Any, now: datetime) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)
    if isinstance(value, date):
        return max(0, (now.date() - value).days)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, (now - parsed).days)
    except ValueError:
        return None


def _safe_query(cursor, sql: str, params=None) -> List[Tuple[Any, ...]]:
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    except Exception as exc:
        log.warning("Health query skipped (%s): %s", type(exc).__name__, exc)
        cursor.connection.rollback()
        return []


def collect_health_report(
    conn,
    *,
    target: str = "cle_v2",
    schema: str = SCHEMA,
    cache_dir: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Collect a comprehensive read-only health overview of all datasets."""
    now = now or datetime.now(timezone.utc)
    report: Dict[str, Any] = {
        "target": target,
        "schema": schema,
        "generated_at": now.isoformat(),
        "corpora": {},
        "watermarks": [],
        "recent_failed_batches": [],
        "citations": [],
        "identifiers": {},
        "legislation": {},
        "law_references": [],
        "authorities": {"documents": {}, "references": {}},
        "outcomes": {},
        "statuses": {},
        "citation_views": {},
        "caches": {},
        "alerts": [],
        "status": "ok",
    }

    with conn.cursor() as cur:
        # 1. Corpus totals, freshness, latest scrape, 7d/30d additions, text coverage
        rows = _safe_query(
            cur,
            f"""
            WITH corpus_cases AS (
                SELECT c.id, s.corpus, c.date_decision, c.created_at, c.updated_at
                  FROM {schema}.cases c
                  CROSS JOIN LATERAL unnest(c.sources) AS s(corpus)
                 WHERE s.corpus IN ('RS', 'CJEU', 'ECHR')
            ),
            text_cases AS (
                SELECT DISTINCT case_id
                  FROM {schema}.case_text
                 WHERE NULLIF(btrim(fulltext), '') IS NOT NULL
            )
            SELECT cc.corpus,
                   count(*)::bigint AS total_cases,
                   count(tc.case_id)::bigint AS cases_with_text,
                   max(cc.date_decision) AS latest_decision_date,
                   max(GREATEST(cc.created_at, COALESCE(cc.updated_at, cc.created_at))) AS latest_ingest_at,
                   count(*) FILTER (WHERE cc.created_at >= now() - interval '7 days')::bigint AS added_7d,
                   count(*) FILTER (WHERE cc.created_at >= now() - interval '30 days')::bigint AS added_30d
              FROM corpus_cases cc
              LEFT JOIN text_cases tc ON tc.case_id = cc.id
             GROUP BY cc.corpus
             ORDER BY cc.corpus
            """,
        )
        for corpus, total, with_text, latest_dec, latest_ing, add7, add30 in rows:
            ratio = round(with_text / total, 4) if total else 0.0
            report["corpora"][corpus] = {
                "total_cases": int(total),
                "cases_with_text": int(with_text),
                "text_coverage": ratio,
                "latest_decision_date": _iso(latest_dec),
                "days_since_latest_decision": _days_since(latest_dec, now),
                "latest_ingest_at": _iso(latest_ing),
                "days_since_latest_ingest": _days_since(latest_ing, now),
                "added_7d": int(add7),
                "added_30d": int(add30),
            }

        # 2. ETL watermarks & recent failed promotion batches
        wm_rows = _safe_query(
            cur,
            f"""
            SELECT source, promoted_through, updated_at
              FROM {schema}.etl_watermark
             ORDER BY source
            """,
        )
        for source, promoted_through, updated_at in wm_rows:
            report["watermarks"].append(
                {
                    "source": source,
                    "promoted_through": _iso(promoted_through),
                    "updated_at": _iso(updated_at),
                    "days_since_update": _days_since(updated_at, now),
                }
            )

        fail_rows = _safe_query(
            cur,
            f"""
            SELECT batch_id::text, source, airflow_dag_id, airflow_run_id,
                   status, error, created_at
              FROM {schema}.etl_promotion_batch
             WHERE status = 'failed'
               AND created_at >= now() - interval '14 days'
             ORDER BY created_at DESC
             LIMIT 20
            """,
        )
        for bid, source, dag_id, run_id, st, err, created_at in fail_rows:
            report["recent_failed_batches"].append(
                {
                    "batch_id": bid,
                    "source": source,
                    "dag_id": dag_id,
                    "run_id": run_id,
                    "status": st,
                    "error": (err or "")[:300],
                    "created_at": _iso(created_at),
                }
            )

        # 3. Citation datasets (resolved/unresolved + active/counted governance flags)
        cite_rows = _safe_query(
            cur,
            f"""
            SELECT cc.source_dataset,
                   count(*)::bigint AS total,
                   count(*) FILTER (WHERE cc.target_case_id IS NOT NULL)::bigint AS resolved,
                   count(*) FILTER (WHERE cc.target_case_id IS NULL)::bigint AS unresolved,
                   COALESCE(sd.active_in_api, false) AS active_in_api,
                   COALESCE(sd.counted, false) AS counted
              FROM {schema}.case_citation cc
              LEFT JOIN {schema}.citation_source_dataset sd ON sd.code = cc.source_dataset
             GROUP BY cc.source_dataset, sd.active_in_api, sd.counted
             ORDER BY total DESC, cc.source_dataset
            """,
        )
        for ds, total, resolved, unresolved, active_api, counted in cite_rows:
            report["citations"].append(
                {
                    "source_dataset": ds,
                    "total": int(total),
                    "resolved": int(resolved),
                    "unresolved": int(unresolved),
                    "resolution_rate": round(resolved / total, 4) if total else 0.0,
                    "active_in_api": bool(active_api),
                    "counted": bool(counted),
                }
            )

        # 4. Case identifiers
        id_rows = _safe_query(
            cur,
            f"""
            SELECT scheme, count(*)::bigint
              FROM {schema}.case_identifier
             GROUP BY scheme
             ORDER BY count(*) DESC
            """,
        )
        report["identifiers"] = {scheme: int(n) for scheme, n in id_rows}

        # 5. Legislation catalog & law references
        leg_rows = _safe_query(
            cur,
            f"""
            SELECT scheme, count(*)::bigint
              FROM {schema}.legislation
             GROUP BY scheme
             ORDER BY count(*) DESC
            """,
        )
        report["legislation"] = {scheme: int(n) for scheme, n in leg_rows}

        lr_rows = _safe_query(
            cur,
            f"""
            SELECT source_dataset,
                   count(*)::bigint AS total,
                   count(*) FILTER (WHERE legislation_id IS NOT NULL)::bigint AS resolved,
                   count(*) FILTER (WHERE legislation_id IS NULL)::bigint AS unresolved
              FROM {schema}.case_law_reference
             GROUP BY source_dataset
             ORDER BY total DESC
            """,
        )
        for ds, total, resolved, unresolved in lr_rows:
            report["law_references"].append(
                {
                    "source_dataset": ds,
                    "total": int(total),
                    "resolved": int(resolved),
                    "unresolved": int(unresolved),
                    "resolution_rate": round(resolved / total, 4) if total else 0.0,
                }
            )

        # 6. Cited authorities
        ad_rows = _safe_query(
            cur,
            f"""
            SELECT kind, count(*)::bigint
              FROM {schema}.authority_document
             GROUP BY kind
             ORDER BY count(*) DESC
            """,
        )
        ar_rows = _safe_query(
            cur,
            f"""
            SELECT source_dataset, count(*)::bigint
              FROM {schema}.case_authority_reference
             GROUP BY source_dataset
             ORDER BY count(*) DESC
            """,
        )
        report["authorities"] = {
            "documents": {kind: int(n) for kind, n in ad_rows},
            "references": {ds: int(n) for ds, n in ar_rows},
        }

        # 7. Outcomes, statuses & citation count views
        out_rows = _safe_query(
            cur,
            f"""
            SELECT source_dataset, count(*)::bigint
              FROM {schema}.case_outcome
             GROUP BY source_dataset
             ORDER BY count(*) DESC
            """,
        )
        report["outcomes"] = {ds: int(n) for ds, n in out_rows}

        st_rows = _safe_query(
            cur,
            f"""
            SELECT source_dataset, status, count(*)::bigint
              FROM {schema}.case_status
             GROUP BY source_dataset, status
             ORDER BY count(*) DESC
            """,
        )
        for ds, status, n in st_rows:
            report["statuses"].setdefault(ds, {})[status] = int(n)

        cc_rows = _safe_query(
            cur,
            f"""
            SELECT count(*)::bigint, COALESCE(sum(cites_count), 0)::bigint,
                   COALESCE(sum(cited_by_count), 0)::bigint, max(updated_at)
              FROM {schema}.case_citation_counts
            """,
        )
        if cc_rows:
            r, sc, sb, upd = cc_rows[0]
            report["citation_views"]["case_citation_counts"] = {
                "rows": int(r),
                "sum_cites": int(sc),
                "sum_cited_by": int(sb),
                "last_updated_at": _iso(upd),
            }

        cb_rows = _safe_query(
            cur,
            f"""
            SELECT count(*)::bigint,
                   count(*) FILTER (WHERE cited_by > 0)::bigint,
                   COALESCE(sum(cited_by), 0)::bigint
              FROM {schema}.case_cited_by
            """,
        )
        if cb_rows:
            r, nz, sb = cb_rows[0]
            report["citation_views"]["case_cited_by"] = {
                "rows": int(r),
                "nonzero": int(nz),
                "sum_cited_by": int(sb),
            }

    conn.rollback()

    # Optional cache-file checks (Cellar UUID caches)
    if cache_dir:
        for fname in ("cellar_uuid_dossier.json", "cellar_uuid_celex.json"):
            fpath = os.path.join(cache_dir, fname)
            if os.path.isfile(fpath):
                st = os.stat(fpath)
                mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                report["caches"][fname] = {
                    "exists": True,
                    "size_bytes": st.st_size,
                    "updated_at": mtime.isoformat(),
                    "age_days": max(0, (now - mtime).days),
                }
            else:
                report["caches"][fname] = {"exists": False}

    alerts = evaluate_alerts(report)
    report["alerts"] = alerts
    if any(a["severity"] == "error" for a in alerts):
        report["status"] = "error"
    elif any(a["severity"] == "warn" for a in alerts):
        report["status"] = "warn"
    else:
        report["status"] = "ok"
    return report


def evaluate_alerts(report: Dict[str, Any]) -> List[Dict[str, str]]:
    """Derive concrete warning/error alerts from a collected health report."""
    alerts: List[Dict[str, str]] = []

    corpora = report.get("corpora") or {}
    for corpus in ("RS", "CJEU", "ECHR"):
        info = corpora.get(corpus)
        if not info or info.get("total_cases", 0) == 0:
            alerts.append(
                {
                    "severity": "error",
                    "component": f"corpus:{corpus}",
                    "message": f"No cases present for corpus {corpus}",
                }
            )
            continue
        max_days = DEFAULT_FRESHNESS_WARN_DAYS[corpus]
        dec_age = info.get("days_since_latest_decision")
        if dec_age is not None and dec_age > max_days:
            alerts.append(
                {
                    "severity": "warn",
                    "component": f"corpus:{corpus}",
                    "message": (
                        f"{corpus} latest decision is {dec_age}d old "
                        f"({info.get('latest_decision_date')}; threshold {max_days}d)"
                    ),
                }
            )
        min_cov = DEFAULT_MIN_TEXT_COVERAGE[corpus]
        if info.get("text_coverage", 0.0) < min_cov:
            alerts.append(
                {
                    "severity": "warn",
                    "component": f"corpus:{corpus}",
                    "message": (
                        f"{corpus} full-text coverage {info['text_coverage']:.1%} "
                        f"is below {min_cov:.0%}"
                    ),
                }
            )

    failed = report.get("recent_failed_batches") or []
    if failed:
        alerts.append(
            {
                "severity": "warn",
                "component": "etl_promotion",
                "message": f"{len(failed)} failed promotion batch(es) in the last 14 days",
            }
        )

    for lr in report.get("law_references") or []:
        ds = lr["source_dataset"]
        if ds in ("cellar_law_ref", "echr_text_eu_law", "rs_text_eu_law") and lr["total"] > 0:
            if lr["resolution_rate"] < 0.90:
                alerts.append(
                    {
                        "severity": "warn",
                        "component": f"law_refs:{ds}",
                        "message": (
                            f"{ds} resolution rate {lr['resolution_rate']:.1%} "
                            f"({lr['unresolved']:,} unresolved) is below 90%"
                        ),
                    }
                )

    views = report.get("citation_views") or {}
    for view_name in ("case_citation_counts", "case_cited_by"):
        v = views.get(view_name)
        if v and v.get("rows", 0) == 0:
            alerts.append(
                {
                    "severity": "error",
                    "component": f"view:{view_name}",
                    "message": f"{view_name} has 0 rows",
                }
            )

    return alerts


def render_markdown(report: Dict[str, Any]) -> str:
    """Render a compact, readable Markdown health overview."""
    status = report.get("status", "ok").upper()
    lines = [
        f"# Case Law Explorer Data Health Report ({report.get('target', 'cle_v2')}) — **{status}**",
        f"Generated: `{report.get('generated_at')}`",
        "",
    ]

    alerts = report.get("alerts") or []
    if alerts:
        lines.append(f"## Alerts ({len(alerts)})")
        for a in alerts:
            lines.append(f"- **[{a['severity'].upper()}]** `{a['component']}`: {a['message']}")
        lines.append("")
    else:
        lines.append("## Alerts\n- None — all checks green.\n")

    lines.append("## 1. Corpus Freshness & Completeness")
    lines.append("| Corpus | Cases | With Fulltext | Latest Decision | Latest Ingest | +7d | +30d |")
    lines.append("|---|---:|---:|---|---|---:|---:|")
    for corpus, info in sorted((report.get("corpora") or {}).items()):
        cov = f"{info['cases_with_text']:,} ({info['text_coverage']:.1%})"
        lines.append(
            f"| {corpus} | {info['total_cases']:,} | {cov} | "
            f"{info.get('latest_decision_date') or '—'} | "
            f"{(info.get('latest_ingest_at') or '—')[:10]} | "
            f"{info.get('added_7d', 0):,} | {info.get('added_30d', 0):,} |"
        )
    lines.append("")

    watermarks = report.get("watermarks") or []
    if watermarks:
        lines.append("## 2. ETL Promotion Watermarks")
        lines.append("| Source | Promoted Through | Last Updated |")
        lines.append("|---|---|---|")
        for wm in watermarks:
            lines.append(
                f"| {wm['source']} | {wm.get('promoted_through') or '—'} | "
                f"{(wm.get('updated_at') or '—')[:19]} |"
            )
        lines.append("")

    citations = report.get("citations") or []
    if citations:
        lines.append("## 3. Citation Links by Dataset")
        lines.append("| Dataset | Total | Resolved | Unresolved | Res % | API | Counted |")
        lines.append("|---|---:|---:|---:|---:|:---:|:---:|")
        for c in citations:
            lines.append(
                f"| `{c['source_dataset']}` | {c['total']:,} | {c['resolved']:,} | "
                f"{c['unresolved']:,} | {c['resolution_rate']:.1%} | "
                f"{'yes' if c['active_in_api'] else 'no'} | {'yes' if c['counted'] else 'no'} |"
            )
        lines.append("")

    law_refs = report.get("law_references") or []
    if law_refs:
        lines.append("## 4. Legislation & Law References")
        leg = report.get("legislation") or {}
        if leg:
            leg_str = ", ".join(f"`{k}`: {v:,}" for k, v in leg.items())
            lines.append(f"Catalog acts: {leg_str}\n")
        lines.append("| Dataset | Total | Resolved | Unresolved | Res % |")
        lines.append("|---|---:|---:|---:|---:|")
        for lr in law_refs:
            lines.append(
                f"| `{lr['source_dataset']}` | {lr['total']:,} | {lr['resolved']:,} | "
                f"{lr['unresolved']:,} | {lr['resolution_rate']:.1%} |"
            )
        lines.append("")

    auth = report.get("authorities") or {}
    if auth.get("references") or auth.get("documents"):
        lines.append("## 5. Cited Authorities")
        docs_total = sum((auth.get("documents") or {}).values())
        refs_str = ", ".join(f"`{k}`: {v:,}" for k, v in (auth.get("references") or {}).items())
        lines.append(f"- Unique authority documents: **{docs_total:,}**")
        lines.append(f"- References by dataset: {refs_str or 'none'}")
        lines.append("")

    outcomes = report.get("outcomes") or {}
    statuses = report.get("statuses") or {}
    if outcomes or statuses:
        lines.append("## 6. Outcomes & Case Status")
        if outcomes:
            lines.append(
                "- Outcomes: " + ", ".join(f"`{k}`: {v:,}" for k, v in outcomes.items())
            )
        if statuses:
            st_parts = []
            for ds, counts in statuses.items():
                inner = ", ".join(f"{s}={n:,}" for s, n in counts.items())
                st_parts.append(f"`{ds}` ({inner})")
            lines.append("- Statuses: " + "; ".join(st_parts))
        lines.append("")

    ids = report.get("identifiers") or {}
    if ids:
        lines.append("## 7. Identifiers & Citation Views")
        lines.append(
            "- `case_identifier`: " + ", ".join(f"`{k}`: {v:,}" for k, v in ids.items())
        )
        views = report.get("citation_views") or {}
        if "case_citation_counts" in views:
            v = views["case_citation_counts"]
            lines.append(
                f"- `case_citation_counts`: {v['rows']:,} rows "
                f"(cites={v['sum_cites']:,}, cited_by={v['sum_cited_by']:,})"
            )
        if "case_cited_by" in views:
            v = views["case_cited_by"]
            lines.append(
                f"- `case_cited_by`: {v['rows']:,} rows "
                f"(nonzero={v['nonzero']:,}, sum={v['sum_cited_by']:,})"
            )
        lines.append("")

    return "\n".join(lines)


def save_snapshot(conn, report: Dict[str, Any], *, schema: str = SCHEMA) -> Optional[int]:
    """Insert a health snapshot row if ``etl_health_snapshot`` exists."""
    from psycopg2.extras import Json

    summary_md = render_markdown(report)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {schema}.etl_health_snapshot
                    (target, status, alerts, summary_md, report)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    report.get("target", "cle_v2"),
                    report.get("status", "ok"),
                    Json(report.get("alerts") or []),
                    summary_md,
                    Json(report),
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return int(row[0]) if row else None
    except Exception as exc:
        conn.rollback()
        log.warning("Could not persist etl_health_snapshot (%s): %s", type(exc).__name__, exc)
        return None


def post_webhook(
    webhook_url: str,
    report: Dict[str, Any],
    markdown: str,
    *,
    urlopen=None,
) -> bool:
    """Optional best-effort webhook delivery (Slack/Discord/generic JSON)."""
    url = (webhook_url or "").strip()
    if not url:
        return False
    opener = urlopen or urllib.request.urlopen
    # Include both "text" (Slack/generic) and "content" (Discord) + structured summary.
    short_md = markdown[:1900]
    payload = {
        "target": report.get("target"),
        "status": report.get("status"),
        "generated_at": report.get("generated_at"),
        "alerts": report.get("alerts") or [],
        "text": short_md,
        "content": short_md,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "CaseLawExplorer-HealthETL/1.0",
        },
        method="POST",
    )
    try:
        with opener(req, timeout=20):
            return True
    except (urllib.error.URLError, OSError) as exc:
        log.warning("Health webhook delivery failed (non-fatal): %s", exc)
        return False
