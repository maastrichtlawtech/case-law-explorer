from airflow.providers.postgres.hooks.postgres import PostgresHook
from summarization.config import CONN_PG_CLE, SUMMARIZATION_MODEL, TARGET_ROLES

# NOTE: case_summary_version_uk_current is a plain (non-partial) unique index
# on (case_id, segment_scope, summarization_model) -- it allows only one row
# per that triple, ever, despite version_number/parent_version_id/rejected_at
# suggesting a full history table. So "new version" here means updating that
# one row in place (version_number += 1), not inserting a second row.
SQL_UPSERT_SUMMARY_VERSION = """
    INSERT INTO cle_v2.case_summary_version
        (case_id, language, summary_text, summarization_model, segment_scope, version_number, is_current, generation_source)
    VALUES
        (%(case_id)s, %(language)s, %(summary_text)s, %(summarization_model)s, %(segment_scope)s, 1, true, 'etl')
    ON CONFLICT (case_id, segment_scope, summarization_model) DO UPDATE SET
        summary_text = EXCLUDED.summary_text,
        language = EXCLUDED.language,
        version_number = cle_v2.case_summary_version.version_number + 1,
        is_current = true,
        generation_source = 'etl',
        created_at = now();
"""

# case_text.summary is what the frontend views (case_text_canonical,
# rs_v_document_with_text) actually read; case_summary_version above is the
# audit/version trail.
SQL_UPDATE_CASE_TEXT_SUMMARY = """
    UPDATE cle_v2.case_text
    SET summary = %(summary_text)s, summary_source = 'etl', updated_at = now()
    WHERE case_id = %(case_id)s AND language = %(language)s;
"""


def write_summary(**kwargs) -> int:
    ti = kwargs["ti"]
    summarized_cases = ti.xcom_pull(task_ids="call_summarization_api", key="summarized_cases") or []
    segment_scope = ",".join(TARGET_ROLES)

    hook = PostgresHook(postgres_conn_id=CONN_PG_CLE)
    conn = hook.get_conn()
    written = 0
    try:
        with conn.cursor() as cur:
            for case in summarized_cases:
                params = {
                    "case_id": case["case_id"],
                    "language": case["language"],
                    "summary_text": case["summary_text"],
                    "summarization_model": SUMMARIZATION_MODEL,
                    "segment_scope": segment_scope,
                }
                cur.execute(SQL_UPSERT_SUMMARY_VERSION, params)
                cur.execute(SQL_UPDATE_CASE_TEXT_SUMMARY, params)
                written += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print(f"{written} case summaries written.")
    return written
