import json
import os

from data_loading.case_text_loader import load_fulltext
from definitions.storage_handler import JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR


class RecordingClient:
    def __init__(self):
        self.rows = []

    def resolve_case_id(self, *, celex_id):
        assert celex_id == "62026CJ0001"
        return 42

    def upsert_case_text(self, **row):
        self.rows.append(row)

    def resolve_case_id_by_item_id(self, item_id):
        assert item_id == "001-12345"
        return 43


def test_cellar_fulltexts_keep_each_translation_language(tmp_path):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_CELLAR)
    path.write_text(
        json.dumps(
            [
                {"celex": "62026CJ0001", "text_language": "EN", "text": "English"},
                {"celex": "62026CJ0001", "text_language": "FR", "text": "Français"},
                {"celex": "62026CJ0001", "text_language": "NL", "text": "Nederlands"},
            ]
        ),
        encoding="utf-8",
    )
    client = RecordingClient()

    load_fulltext(client, [str(path)])

    assert [row["language"] for row in client.rows] == ["en", "fr", "nl"]
    assert [row["fulltext"] for row in client.rows] == ["English", "Français", "Nederlands"]
    assert all(row["case_id"] == 42 for row in client.rows)
    assert all(row["source"] == "CELLAR_ITEM" for row in client.rows)
    assert not path.exists()


def test_cellar_fulltext_accepts_legacy_language_key(tmp_path):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_CELLAR)
    path.write_text(
        json.dumps([{"celex": "62026CJ0001", "language": "DE", "full_text": "Deutsch"}]),
        encoding="utf-8",
    )
    client = RecordingClient()

    load_fulltext(client, [str(path)])

    assert client.rows[0]["language"] == "de"


def test_hudoc_fulltext_normalizes_three_letter_language(tmp_path):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_ECHR)
    path.write_text(
        json.dumps([{"item_id": "001-12345", "language": "FRE", "full_text": "Français"}]),
        encoding="utf-8",
    )
    client = RecordingClient()

    load_fulltext(client, [str(path)])

    assert client.rows == [
        {"case_id": 43, "language": "fr", "source": "HUDOC", "fulltext": "Français"}
    ]
