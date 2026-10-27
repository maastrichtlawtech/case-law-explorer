from airflow.providers.postgres.hooks.postgres import PostgresHook
from segmentation.config import BATCH_SIZE, CONN_PG_CLE

SQL_FETCH_UNSEGMENTED = """
    SELECT ct.case_id, ct.language, ct.fulltext
    FROM cle_v2.case_text ct
    LEFT JOIN cle_v2.case_segment cs ON cs.case_id = ct.case_id
    WHERE ct.fulltext IS NOT NULL
      AND cs.id IS NULL
    GROUP BY ct.case_id, ct.language, ct.fulltext
    LIMIT %(batch_size)s;
"""


def fetch_unsegmented_cases(**kwargs) -> list[dict]:
    """Cases with full text but no case_segment rows yet, batched so a single
    DAG run doesn't try to segment the entire corpus at once."""
    hook = PostgresHook(postgres_conn_id=CONN_PG_CLE)
    rows = hook.get_records(SQL_FETCH_UNSEGMENTED, parameters={"batch_size": BATCH_SIZE})
    cases = [{"case_id": r[0], "language": r[1], "fulltext": r[2]} for r in rows]
    kwargs["ti"].xcom_push(key="unsegmented_cases", value=cases)
    return cases
