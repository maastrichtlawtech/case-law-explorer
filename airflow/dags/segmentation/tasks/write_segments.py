import hashlib

from airflow.providers.postgres.hooks.postgres import PostgresHook
from segmentation.config import CONN_PG_CLE, EXTRACTOR_VERSION

SQL_INSERT_SEGMENT = """
    INSERT INTO cle_v2.case_segment
        (case_id, language, segment_type, segment_index, segment_text, segment_hash, extractor_version)
    VALUES
        (%(case_id)s, %(language)s, %(segment_type)s, %(segment_index)s, %(segment_text)s, %(segment_hash)s, %(extractor_version)s)
    ON CONFLICT (case_id, segment_hash) DO NOTHING;
"""


def write_segments(**kwargs) -> int:
    ti = kwargs["ti"]
    segmented_cases = ti.xcom_pull(task_ids="call_segmentation_api", key="segmented_cases") or []

    hook = PostgresHook(postgres_conn_id=CONN_PG_CLE)
    conn = hook.get_conn()
    written = 0
    try:
        with conn.cursor() as cur:
            for case in segmented_cases:
                for segment in case["segments"]:
                    segment_text = segment["segment_text"]
                    segment_hash = hashlib.sha256(segment_text.encode("utf-8")).hexdigest()
                    cur.execute(
                        SQL_INSERT_SEGMENT,
                        {
                            "case_id": case["case_id"],
                            "language": case["language"],
                            "segment_type": segment.get("segment_type"),
                            "segment_index": segment.get("segment_index"),
                            "segment_text": segment_text,
                            "segment_hash": segment_hash,
                            "extractor_version": EXTRACTOR_VERSION,
                        },
                    )
                    written += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print(f"{written} new segments written across {len(segmented_cases)} cases.")
    return written
