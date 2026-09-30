import logging

import requests
from segmentation.config import REQUEST_TIMEOUT_SECONDS, SEGMENTATION_API_URL


def call_segmentation_api(**kwargs) -> list[dict]:
    """POST each case's full text to legal-summarizer-service's /segment
    endpoint. Request: {case_id, text, language}. Response: a list of
    {segment_type, segment_index, segment_text}."""
    ti = kwargs["ti"]
    cases = ti.xcom_pull(task_ids="fetch_unsegmented_cases", key="unsegmented_cases") or []

    results = []
    for case in cases:
        try:
            response = requests.post(
                SEGMENTATION_API_URL,
                json={
                    "case_id": case["case_id"],
                    "text": case["fulltext"],
                    "language": case["language"],
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            segments = response.json()
        except requests.RequestException:
            logging.exception(f"Segmentation API call failed for case_id={case['case_id']}")
            continue

        results.append({"case_id": case["case_id"], "language": case["language"], "segments": segments})

    ti.xcom_push(key="segmented_cases", value=results)
    return results
