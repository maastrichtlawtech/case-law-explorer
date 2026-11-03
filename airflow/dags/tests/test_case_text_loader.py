import json
import os

import pytest
from data_loading.case_text_loader import load_fulltext
from definitions.storage_handler import JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR


class RecordingClient:
    def __init__(self):
        self.rows = []
        self.echr_language = "fr"

    def resolve_case_id(self, *, celex_id):
        assert celex_id == "62026CJ0001"
        return 42

    def upsert_case_text(self, **row):
        self.rows.append(row)

    def resolve_case_id_by_item_id(self, item_id):
        assert item_id == "001-12345"
        return 43

    def resolve_echr_language_by_item_id(self, item_id):
        assert item_id == "001-12345"
        return self.echr_language

    def resolve_echr_document_context(self, item_id):
        assert item_id == "001-12345"
        return 43, self.echr_language, "JUD"

    def upsert_echr_secondary_text(self, item_id, fulltext):
        self.rows.append({"secondary_item_id": item_id, "fulltext": fulltext})


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
    assert [row["fulltext"] for row in client.rows] == [
        "English",
        "Français",
        "Nederlands",
    ]
    assert all(row["case_id"] == 42 for row in client.rows)
    assert all(row["source"] == "CELLAR_ITEM" for row in client.rows)
    assert all(row["document_kind"] == "judgment" for row in client.rows)
    assert all(row["document_celex"] == "62026CJ0001" for row in client.rows)
    assert path.exists()


def test_cellar_fulltext_accepts_legacy_language_key(tmp_path):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_CELLAR)
    path.write_text(
        json.dumps([{"celex": "62026CJ0001", "language": "DE", "full_text": "Deutsch"}]),
        encoding="utf-8",
    )
    client = RecordingClient()

    load_fulltext(client, [str(path)])

    assert client.rows[0]["language"] == "de"


def test_cellar_fulltext_rejects_noncanonical_celex(tmp_path):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_CELLAR)
    path.write_text(
        json.dumps(
            [
                {
                    "celex": "62026CJ0001;62026CJ0001_RES",
                    "text_language": "EN",
                    "text": "English",
                }
            ]
        ),
        encoding="utf-8",
    )
    client = RecordingClient()

    with pytest.raises(ValueError, match="Refusing non-canonical CELLAR"):
        load_fulltext(client, [str(path)])

    assert client.rows == []


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


def test_hudoc_fulltext_uses_metadata_language_when_blob_omits_it(tmp_path):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_ECHR)
    path.write_text(
        json.dumps([{"item_id": "001-12345", "full_text": "Texte français"}]),
        encoding="utf-8",
    )
    client = RecordingClient()

    load_fulltext(client, [str(path)])

    assert client.rows == [
        {
            "case_id": 43,
            "language": "fr",
            "source": "HUDOC",
            "fulltext": "Texte français",
        }
    ]


def test_hudoc_fulltext_preserves_noncanonical_same_language_variant(tmp_path):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_ECHR)
    path.write_text(
        json.dumps(
            [
                {"item_id": "001-decision", "full_text": "Decision"},
                {"item_id": "001-judgment", "full_text": "Judgment"},
            ]
        ),
        encoding="utf-8",
    )

    class MultiVariantClient(RecordingClient):
        def resolve_echr_document_context(self, item_id):
            doctype = "DEC" if item_id.endswith("decision") else "JUD"
            return 43, "en", doctype

    client = MultiVariantClient()
    load_fulltext(client, [str(path)])

    assert client.rows == [
        {"case_id": 43, "language": "en", "source": "HUDOC", "fulltext": "Judgment"},
        {"secondary_item_id": "001-decision", "fulltext": "Decision"},
    ]


class EcliClient:
    """Resolves ECLIs; the CELEX belongs to a different case in cle_v2."""

    def __init__(self):
        self.rows = []

    def resolve_case_id(self, *, ecli=None, celex_id=None):
        if celex_id is not None:
            return 99  # the other case that holds this CELEX
        return {"ECLI:EU:T:2026:503": 7}.get(ecli)

    def upsert_case_text(self, **row):
        self.rows.append(row)


def _write(tmp_path, records):
    path = tmp_path / os.path.basename(JSON_FULL_TEXT_CELLAR)
    path.write_text(json.dumps(records), encoding="utf-8")
    return str(path)


def test_cellar_fulltext_resolves_by_the_record_ecli_not_its_celex(tmp_path):
    client = EcliClient()
    load_fulltext(client, [_write(tmp_path, [
        {"celex": "62024TO0346", "ecli": "ECLI:EU:T:2026:503", "text_language": "EN",
         "text": "Order", "text_source": "CELLAR_ITEM", "text_format": "xhtml"},
        {"celex": "62024TO0346", "ecli": "ECLI:EU:T:2099:1", "text_language": "EN",
         "text": "Unknown case"},
    ])])

    assert [row["case_id"] for row in client.rows] == [7]
    assert client.rows[0]["document_kind"] == "order"
    assert client.rows[0]["text_format"] == "xhtml"


def test_cellar_fulltext_keeps_infocuria_sources_and_marks_missing_bodies(tmp_path):
    client = EcliClient()
    load_fulltext(client, [_write(tmp_path, [
        {"celex": "62024TO0346", "ecli": "ECLI:EU:T:2026:503", "text_language": "DE",
         "text": "Beschluss", "text_source": "INFOCURIA_BLOB_HTML", "text_format": "html"},
        {"celex": "62024TO0346", "ecli": "ECLI:EU:T:2026:503", "text_language": "FR",
         "text": "Avis", "text_source": "INFOCURIA_OJ_NOTICE"},
        {"celex": "62024TO0346", "ecli": "ECLI:EU:T:2026:503", "text_language": "IT",
         "text": "", "text_source": "", "missing_reasons": "FULLTEXT_UNAVAILABLE_UPSTREAM"},
    ])])

    assert [row["source"] for row in client.rows] == [
        "INFOCURIA_BLOB_HTML", "INFOCURIA_OJ_NOTICE", "CELLAR_ITEM"]
    assert [row["document_kind"] for row in client.rows] == ["order", "oj_notice", "order"]
    assert [row["is_stub"] for row in client.rows] == [False, False, True]
    assert client.rows[2]["missing_reasons"] == "FULLTEXT_UNAVAILABLE_UPSTREAM"
