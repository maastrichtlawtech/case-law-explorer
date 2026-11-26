"""Unit tests for data_health overview collector and reporter."""

import io
import json

import data_health


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _sample_report():
    return {
        "target": "production",
        "generated_at": "2026-11-26T07:00:00+00:00",
        "corpora": {
            "RS": {
                "total_cases": 3_760_000,
                "cases_with_text": 1_019_454,
                "text_coverage": 0.2711,
                "latest_decision_date": "2026-11-25",
                "days_since_latest_decision": 1,
                "latest_ingest_at": "2026-11-26T02:30:00+00:00",
                "days_since_latest_ingest": 0,
                "added_7d": 1200,
                "added_30d": 5100,
            },
            "CJEU": {
                "total_cases": 55_391,
                "cases_with_text": 54_800,
                "text_coverage": 0.9893,
                "latest_decision_date": "2026-11-20",
                "days_since_latest_decision": 6,
                "latest_ingest_at": "2026-11-26T03:30:00+00:00",
                "days_since_latest_ingest": 0,
                "added_7d": 42,
                "added_30d": 180,
            },
            "ECHR": {
                "total_cases": 102_339,
                "cases_with_text": 101_000,
                "text_coverage": 0.9869,
                "latest_decision_date": "2026-11-19",
                "days_since_latest_decision": 7,
                "latest_ingest_at": "2026-11-26T04:30:00+00:00",
                "days_since_latest_ingest": 0,
                "added_7d": 65,
                "added_30d": 250,
            },
        },
        "watermarks": [
            {"source": "rechtspraak", "promoted_through": "2026-11-25", "updated_at": "2026-11-26T06:00:00+00:00"}
        ],
        "recent_failed_batches": [],
        "citations": [
            {
                "source_dataset": "rs_text_ecli",
                "total": 74136,
                "resolved": 74136,
                "unresolved": 0,
                "resolution_rate": 1.0,
                "active_in_api": True,
                "counted": True,
            }
        ],
        "identifiers": {"ecli": 3930835, "celex": 54111},
        "legislation": {"celex": 13401, "bwb": 45000},
        "law_references": [
            {
                "source_dataset": "cellar_law_ref",
                "total": 238283,
                "resolved": 238283,
                "unresolved": 0,
                "resolution_rate": 1.0,
            }
        ],
        "authorities": {
            "documents": {"nl_parliamentary_paper": 6357},
            "references": {"rs_text_authority": 71323},
        },
        "outcomes": {"echr_conclusion": 82856, "cjeu_proc_type": 20751},
        "statuses": {"cjeu_appeal_status": {"overturned": 532}},
        "citation_views": {
            "case_citation_counts": {"rows": 873068, "sum_cites": 4845137, "sum_cited_by": 4006054},
            "case_cited_by": {"rows": 3933927, "nonzero": 553545, "sum_cited_by": 2970964},
        },
    }


def test_evaluate_alerts_clean_report_has_no_alerts():
    report = _sample_report()
    assert data_health.evaluate_alerts(report) == []


def test_evaluate_alerts_flags_stale_corpus_failed_batch_and_low_law_resolution():
    report = _sample_report()
    report["corpora"]["RS"]["days_since_latest_decision"] = 25
    report["recent_failed_batches"] = [{"batch_id": "abc", "source": "cellar"}]
    report["law_references"][0]["resolution_rate"] = 0.72
    report["law_references"][0]["unresolved"] = 50000
    report["citation_views"]["case_cited_by"]["rows"] = 0

    alerts = data_health.evaluate_alerts(report)
    components = {a["component"]: a["severity"] for a in alerts}
    assert components["corpus:RS"] == "warn"
    assert components["etl_promotion"] == "warn"
    assert components["law_refs:cellar_law_ref"] == "warn"
    assert components["view:case_cited_by"] == "error"


def test_render_markdown_contains_all_sections():
    report = _sample_report()
    report["alerts"] = []
    report["status"] = "ok"
    md = data_health.render_markdown(report)
    assert "Data Health Report (production) — **OK**" in md
    assert "## 1. Corpus Freshness & Completeness" in md
    assert "`rs_text_ecli`" in md
    assert "`cellar_law_ref`" in md
    assert "6,357" in md
    assert "overturned=532" in md


def test_post_webhook_sends_json_payload():
    seen = []

    def fake_urlopen(req, timeout=20):
        seen.append((req.full_url, json.loads(req.data.decode("utf-8"))))
        return _FakeResp(b"ok")

    report = _sample_report()
    report["status"] = "ok"
    ok = data_health.post_webhook("https://example.invalid/hook", report, "# Report", urlopen=fake_urlopen)
    assert ok is True
    assert seen[0][0] == "https://example.invalid/hook"
    assert seen[0][1]["status"] == "ok"
    assert seen[0][1]["text"] == "# Report"
