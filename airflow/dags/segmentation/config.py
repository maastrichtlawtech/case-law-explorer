from os import getenv

from airflow.datasets import Dataset

CONN_PG_CLE = "pg_cle"

# Outlet of case_segmentation's write task; case_summarization schedules on
# it. Lives here (not in segmentation/dag.py) so summarization can import it
# without importing the DAG module -- importing a module that defines a DAG
# makes that DAG register under the importing file too, which Airflow then
# reports as a duplicated dag_id.
CASE_SEGMENTS_DATASET = Dataset("cle_v2://case_segment")

# legal-summarizer-service, the service already spec'd for /summarize in the
# wiki's case-law-summarization-implementation-plan; /segment is a new
# contract added there alongside it.
SEGMENTATION_API_URL = getenv("SEGMENTATION_API_URL", "http://legal-summarizer-service/segment")

BATCH_SIZE = int(getenv("SEGMENTATION_BATCH_SIZE", "50"))
REQUEST_TIMEOUT_SECONDS = int(getenv("SEGMENTATION_TIMEOUT_SECONDS", "120"))
EXTRACTOR_VERSION = getenv("SEGMENTATION_EXTRACTOR_VERSION", "v1")
