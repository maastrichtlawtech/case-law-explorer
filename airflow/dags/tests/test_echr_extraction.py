import json

import pandas as pd
from data_extraction.caselaw.echr.echr_extraction import (
    _canonical_item_ids,
    _full_text_coverage,
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


def test_full_text_coverage_counts_only_nonempty_matching_bodies(tmp_path):
    metadata = pd.DataFrame([{"itemid": "001-one"}, {"itemid": "001-two"}, {"itemid": "001-three"}])
    path = tmp_path / "ECHR_full_text.json"
    path.write_text(
        json.dumps(
            [
                {"item_id": "001-one", "full_text": "Judgment"},
                {"item_id": "001-two", "full_text": ""},
                {"item_id": "unrelated", "full_text": "Other"},
            ]
        ),
        encoding="utf-8",
    )

    assert _full_text_coverage(metadata, str(path)) == 1 / 3


def test_full_text_coverage_is_zero_for_a_missing_artifact(tmp_path):
    metadata = pd.DataFrame([{"itemid": "001-one"}])

    assert _full_text_coverage(metadata, str(tmp_path / "missing.json")) == 0.0


def test_full_text_coverage_excludes_language_placeholders(tmp_path):
    metadata = pd.DataFrame(
        [
            {"itemid": "001-placeholder", "isplaceholder": True},
            {"itemid": "001-real", "isplaceholder": False},
        ]
    )
    path = tmp_path / "ECHR_full_text.json"
    path.write_text(
        json.dumps([{"item_id": "001-real", "full_text": "Judgment"}]),
        encoding="utf-8",
    )

    assert _full_text_coverage(metadata, str(path)) == 1.0
