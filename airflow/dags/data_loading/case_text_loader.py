"""
Loads the Cellar/ECHR full-text JSON blobs directly into cle_v2.case_text.

Replaces fulltext_bucket_saving.py (issue #42): those JSON files used to be
uploaded to the `full-text-data` S3 bucket, one object per celex/item_id.
Postgres has room for full text directly in case_text, so the bucket is no
longer needed -- this reads the same JSON files and upserts each entry.
"""

import json
import logging
import os

from data_loading.language_codes import normalize_language_code
from data_transformation.utils import format_cellar_celex
from definitions.storage_handler import JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR


def load_fulltext(client, files_location_paths: list) -> None:
    for file_location_path in files_location_paths:
        if not os.path.exists(file_location_path):
            logging.warning(f"FILE {file_location_path} DOES NOT EXIST")
            continue

        with open(file_location_path, encoding="utf-8") as json_file:
            data = json.load(json_file)

        file_name = os.path.basename(file_location_path)
        loaded = 0
        if file_name == os.path.basename(JSON_FULL_TEXT_ECHR):
            loaded = _load_echr_fulltext(client, data)
            logging.info(
                f"{loaded}/{len(data)} full-text records loaded from {file_name}"
            )
            continue
        for item in data:
            if file_name == os.path.basename(JSON_FULL_TEXT_CELLAR):
                # CELLAR may identify a document with multiple CELEX values
                # (for example ``62025CJ0051;62025CJ0051_SUM``).  Metadata is
                # normalized to the canonical, non-suffixed CELEX before the
                # case row is stored, so resolve full text by that same value.
                celex = format_cellar_celex(item["celex"])
                case_id = client.resolve_case_id(celex_id=celex)
                if case_id is None:
                    logging.info(f"No case found for celex {celex}, skipping full text")
                    continue
                client.upsert_case_text(
                    case_id=case_id,
                    # cellar-extractor 2.x emits one record per available
                    # translation and names the field ``text_language``.
                    # Keep accepting the legacy ``language`` key for older
                    # artifacts, but do not collapse every translation onto
                    # the English conflict key.
                    language=normalize_language_code(
                        item.get("text_language") or item.get("language")
                    ),
                    source="CELLAR_ITEM",
                    fulltext=item.get("full_text") or item.get("text"),
                )
                loaded += 1

        logging.info(
            f"{loaded}/{len(data)} full-text records loaded from {os.path.basename(file_location_path)}"
        )


def _hudoc_doctype_rank(doctype):
    value = str(doctype or "").upper()
    if "JUD" in value:
        return 0
    if "DEC" in value:
        return 1
    if "COM" in value:
        return 2
    return 3


def _load_echr_fulltext(client, data) -> int:
    """Load the best body per case/language and preserve every other variant.

    HUDOC item IDs belong to document variants. Several variants can map to
    one conceptual case and language; ``case_text`` stores the deterministic
    JUD > DEC > COM canonical body and ``echr_document_secondary_text`` keeps
    the lossless remainder.
    """
    grouped = {}
    for item in data:
        item_id = item["item_id"]
        context = client.resolve_echr_document_context(item_id)
        if context is None:
            logging.info("No ECHR document found for item_id %s, skipping full text", item_id)
            continue
        case_id, metadata_language, doctype = context
        language = normalize_language_code(metadata_language or item.get("language"))
        grouped.setdefault((case_id, language), []).append(
            (item_id, doctype, item.get("full_text") or item.get("text"))
        )

    loaded = 0
    for (case_id, language), variants in grouped.items():
        populated = [variant for variant in variants if str(variant[2] or "").strip()]
        if not populated:
            client.upsert_case_text(
                case_id=case_id,
                language=language,
                source="HUDOC",
                fulltext=None,
                missing_reasons="HUDOC_BODY_UNAVAILABLE_AFTER_RETRIES",
                is_stub=True,
            )
            continue
        populated.sort(key=lambda value: (_hudoc_doctype_rank(value[1]), value[0]))
        canonical = populated[0]
        client.upsert_case_text(
            case_id=case_id,
            language=language,
            source="HUDOC",
            fulltext=canonical[2],
        )
        loaded += 1
        for item_id, _, fulltext in populated[1:]:
            client.upsert_echr_secondary_text(item_id, fulltext)
            loaded += 1
    return loaded


if __name__ == "__main__":
    from clients.postgres import PostgresCLEClient

    with PostgresCLEClient() as client:
        load_fulltext(client, [JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR])
