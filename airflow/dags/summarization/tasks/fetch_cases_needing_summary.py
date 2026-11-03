from airflow.providers.postgres.hooks.postgres import PostgresHook
from summarization.config import BATCH_SIZE, CONN_PG_CLE, SUMMARIZATION_MODEL

SQL_FETCH_CASE_IDS = """
    SELECT DISTINCT cs.case_id
    FROM cle_v2.case_segment cs
    WHERE NOT EXISTS (
        SELECT 1 FROM cle_v2.case_summary_version sv
        WHERE sv.case_id = cs.case_id
          AND sv.is_current = true
          AND sv.summarization_model = %(model)s
    )
    LIMIT %(batch_size)s;
"""

SQL_FETCH_SEGMENTS = """
    SELECT case_id, language, segment_type, segment_index, segment_text
    FROM cle_v2.case_segment
    WHERE case_id = ANY(%(case_ids)s)
    ORDER BY case_id, segment_index;
"""


def fetch_cases_needing_summary(**kwargs) -> list[dict]:
    """Cases with segments already computed (by case_segmentation) but no
    current summary yet for the configured model."""
    hook = PostgresHook(postgres_conn_id=CONN_PG_CLE)
    case_id_rows = hook.get_records(
        SQL_FETCH_CASE_IDS, parameters={"model": SUMMARIZATION_MODEL, "batch_size": BATCH_SIZE}
    )
    case_ids = [r[0] for r in case_id_rows]

    cases: dict[int, dict] = {}
    if case_ids:
        for case_id, language, segment_type, segment_index, segment_text in hook.get_records(
            SQL_FETCH_SEGMENTS, parameters={"case_ids": case_ids}
        ):
            case = cases.setdefault(case_id, {"case_id": case_id, "language": language, "segments": []})
            case["segments"].append(
                {"segment_type": segment_type, "segment_index": segment_index, "segment_text": segment_text}
            )

    result = list(cases.values())
    kwargs["ti"].xcom_push(key="cases_needing_summary", value=result)
    return result
