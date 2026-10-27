import logging

import requests
from summarization.config import (
    REQUEST_TIMEOUT_SECONDS,
    SUMMARIZATION_API_URL,
    SUMMARIZATION_MODEL,
    TARGET_ROLES,
)


def call_summarization_api(**kwargs) -> list[dict]:
    """POST each case's segments to legal-summarizer-service's /summarize
    endpoint with method=segment-based, per the contract already defined in
    the wiki's case-law-summarization-implementation-plan."""
    ti = kwargs["ti"]
    cases = ti.xcom_pull(task_ids="fetch_cases_needing_summary", key="cases_needing_summary") or []

    results = []
    for case in cases:
        try:
            response = requests.post(
                SUMMARIZATION_API_URL,
                json={
                    "case_id": case["case_id"],
                    "segments": case["segments"],
                    "method": "segment-based",
                    "model": SUMMARIZATION_MODEL,
                    "params": {"target_roles": TARGET_ROLES},
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            summary_text = response.json()["summary"]
        except (requests.RequestException, KeyError, ValueError):
            logging.exception(f"Summarization API call failed for case_id={case['case_id']}")
            continue

        results.append(
            {"case_id": case["case_id"], "language": case["language"], "summary_text": summary_text}
        )

    ti.xcom_push(key="summarized_cases", value=results)
    return results
