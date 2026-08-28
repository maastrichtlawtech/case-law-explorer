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
        for item in data:
            if file_name == os.path.basename(JSON_FULL_TEXT_ECHR):
                item_id = item["item_id"]
                case_id = client.resolve_case_id_by_item_id(item_id)
                if case_id is None:
                    logging.info(
                        f"No case found for ECHR item_id {item_id}, skipping full text"
                    )
                    continue
                client.upsert_case_text(
                    case_id=case_id,
                    language=normalize_language_code(item.get("language")),
                    source="HUDOC",
                    fulltext=item.get("full_text") or item.get("text"),
                )
                loaded += 1
            elif file_name == os.path.basename(JSON_FULL_TEXT_CELLAR):
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


if __name__ == "__main__":
    from clients.postgres import PostgresCLEClient

    with PostgresCLEClient() as client:
        load_fulltext(client, [JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR])
