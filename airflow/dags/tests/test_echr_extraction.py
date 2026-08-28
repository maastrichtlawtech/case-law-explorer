import pandas as pd
from data_extraction.caselaw.echr.echr_extraction import (
    _canonical_item_ids,
    _normalize_edge_identifiers,
)


def test_canonical_item_ids_prefer_non_placeholder_variant():
    metadata = pd.DataFrame(
        [
            {
                "ecli": "ECLI:CE:ECHR:2026:TEST",
                "itemid": "001-placeholder",
                "extractedappno": None,
            },
            {
                "ecli": "ECLI:CE:ECHR:2026:TEST",
                "itemid": "001-real",
                "extractedappno": "12345/26",
            },
        ]
    )

    assert _canonical_item_ids(metadata) == {"ECLI:CE:ECHR:2026:TEST": "001-real"}


def test_normalize_edges_uses_item_ids_for_corpus_documents(tmp_path):
    metadata = pd.DataFrame(
        [
            {
                "ecli": "ECLI:CE:ECHR:2026:SOURCE",
                "itemid": "001-source",
                "extractedappno": "1/26",
            },
            {
                "ecli": "ECLI:CE:ECHR:2025:TARGET",
                "itemid": "001-target",
                "extractedappno": "2/25",
            },
        ]
    )
    path = tmp_path / "ECHR_edges.txt"
    path.write_text(
        "ECLI:CE:ECHR:2026:SOURCE,ECLI:CE:ECHR:2025:TARGET\n"
        "ECLI:CE:ECHR:2026:SOURCE,ECLI:CE:ECHR:2000:EXTERNAL\n",
        encoding="utf-8",
    )

    _normalize_edge_identifiers(metadata, str(path))

    assert path.read_text(encoding="utf-8").splitlines() == [
        "001-source,001-target",
        "001-source,ECLI:CE:ECHR:2000:EXTERNAL",
    ]
