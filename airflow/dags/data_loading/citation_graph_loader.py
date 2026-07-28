"""
Loads the Cellar/ECHR node+edge txt files directly into cle_v2.case_citation.

Replaces nodes_and_edges_loader.py (issue #42): edges used to be merged by
reading/writing whole txt files to the `cellar-nodes-edges-bucket` S3 bucket
(a manual, unlocked read-modify-write). case_citation's own unique indexes
(case_citation_uk_resolved / _uk_unresolved_ecli / _uk_unresolved_celex) make
that merge step unnecessary -- each edge is upserted once, idempotently.

Edge file format (one per line): "<source_identifier>,<target_identifier>"
(see cellar_extractor.nodes_and_edges.get_edges_list).
"""

import os
from contextlib import suppress

from definitions.storage_handler import (
    TXT_CELLAR_EDGES,
    TXT_ECHR_EDGES,
    get_path_raw,
)

CELLAR_EDGE_FILES = [(TXT_CELLAR_EDGES, "celex", "EURLEX")]
ECHR_EDGE_FILES = [(TXT_ECHR_EDGES, "ecli", "ECHR")]


def _load_edge_file(client, path: str, target_key: str, source_dataset: str) -> int:
    if not os.path.exists(path):
        print(f"FILE {path} DOES NOT EXIST")
        return 0

    loaded = 0
    with open(path, encoding="utf8") as f:
        for line in f:
            line = line.strip()
            if not line or "," not in line:
                continue
            source_id, target_id = line.split(",", 1)

            source_case_id = (
                client.resolve_case_id(celex_id=source_id)
                if target_key == "celex"
                else client.resolve_case_id(ecli=source_id)
            )
            if source_case_id is None:
                continue

            target_case_id = (
                client.resolve_case_id(celex_id=target_id)
                if target_key == "celex"
                else client.resolve_case_id(ecli=target_id)
            )

            client.upsert_citation(
                source_case_id=source_case_id,
                target_case_id=target_case_id,
                target_celex_raw=target_id if target_key == "celex" and target_case_id is None else None,
                target_ecli_raw=target_id if target_key == "ecli" and target_case_id is None else None,
                relation_type="cites",
                source_dataset=source_dataset,
            )
            loaded += 1

    # another task may have consumed the file concurrently; upserts are
    # idempotent, so a double-read is harmless and a missing file is fine
    with suppress(FileNotFoundError):
        os.remove(path)
    return loaded


def load_citation_graph(client, sources=None, edge_dir=None) -> None:
    """Load edge files into case_citation. sources limits which datasets'
    edge files are read ('EURLEX', 'ECHR'); None means all. edge_dir is
    where the files live; defaults to the global raw dir."""
    for filename, target_key, source_dataset in CELLAR_EDGE_FILES + ECHR_EDGE_FILES:
        if sources is not None and source_dataset not in sources:
            continue
        path = os.path.join(edge_dir, filename) if edge_dir else get_path_raw(filename)
        loaded = _load_edge_file(client, path, target_key, source_dataset)
        print(f"{loaded} citation edges loaded from {filename}")


if __name__ == "__main__":
    from clients.postgres import PostgresCLEClient

    with PostgresCLEClient() as client:
        load_citation_graph(client)
