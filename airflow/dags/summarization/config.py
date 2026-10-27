from os import getenv

CONN_PG_CLE = "pg_cle"

SUMMARIZATION_API_URL = getenv("SUMMARIZATION_API_URL", "http://legal-summarizer-service/summarize")

BATCH_SIZE = int(getenv("SUMMARIZATION_BATCH_SIZE", "50"))
REQUEST_TIMEOUT_SECONDS = int(getenv("SUMMARIZATION_TIMEOUT_SECONDS", "120"))

SUMMARIZATION_MODEL = getenv("SUMMARIZATION_MODEL", "segment-based:default")
TARGET_ROLES = getenv(
    "SUMMARIZATION_TARGET_ROLES", "considerations,decision,ruling,RATIO"
).split(",")
