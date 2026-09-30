"""
Shared lido.db/lido-export.ttl.gz path resolution for lido_sqlite_build.py and
rechtspraak_etl.py/rechtspraak_extraction.py.

Kept in its own module, separate from lido_sqlite_build.py's DAG definition:
a plain top-level import of a DAG-defining file re-executes that file's
`with dag:` block as a side effect, which Airflow's DagContext auto-registers
a second time and then rejects as a duplicate dag_id -- breaking the importing
file's own DAG in the process. See lido_sqlite_build.py for the DAG itself.
"""

from pathlib import Path

from etl_factory import get_data_path


def get_lido_sqlite_paths(data_path: str | None = None) -> tuple[Path, Path]:
    """(ttl_gz_path, db_path) under data/lido_sqlite/, shared with rechtspraak_etl."""
    data_dir = Path(data_path or get_data_path()) / "lido_sqlite"
    return data_dir / "lido-export.ttl.gz", data_dir / "lido.db"
