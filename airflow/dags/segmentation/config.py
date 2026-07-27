from os import getenv

CONN_PG_CLE = "pg_cle"

# legal-summarizer-service, the service already spec'd for /summarize in the
# wiki's case-law-summarization-implementation-plan; /segment is a new
# contract added there alongside it.
SEGMENTATION_API_URL = getenv("SEGMENTATION_API_URL", "http://legal-summarizer-service/segment")

BATCH_SIZE = int(getenv("SEGMENTATION_BATCH_SIZE", "50"))
REQUEST_TIMEOUT_SECONDS = int(getenv("SEGMENTATION_TIMEOUT_SECONDS", "120"))
EXTRACTOR_VERSION = getenv("SEGMENTATION_EXTRACTOR_VERSION", "v1")
