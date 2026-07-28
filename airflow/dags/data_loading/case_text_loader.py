"""
Loads the Cellar/ECHR full-text JSON blobs directly into cle_v2.case_text.

Replaces fulltext_bucket_saving.py (issue #42): those JSON files used to be
uploaded to the `full-text-data` S3 bucket, one object per celex/item_id.
Postgres has room for full text directly in case_text, so the bucket is no
longer needed -- this reads the same JSON files and upserts each entry.
"""

import json
import os

from definitions.storage_handler import JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR


def load_fulltext(client, files_location_paths: list) -> None:
    for file_location_path in files_location_paths:
        if not os.path.exists(file_location_path):
            print(f"FILE {file_location_path} DOES NOT EXIST")
            continue

        with open(file_location_path, encoding="utf-8") as json_file:
            data = json.load(json_file)

        loaded = 0
        for item in data:
            if file_location_path == JSON_FULL_TEXT_ECHR:
                item_id = item["item_id"]
                case_id = client.resolve_case_id_by_item_id(item_id)
                if case_id is None:
                    print(f"No case found for ECHR item_id {item_id}, skipping full text")
                    continue
                client.upsert_case_text(
                    case_id=case_id,
                    language=item.get("language", "en"),
                    source="HUDOC",
                    fulltext=item.get("full_text") or item.get("text"),
                )
                loaded += 1
            elif file_location_path == JSON_FULL_TEXT_CELLAR:
                celex = item["celex"]
                case_id = client.resolve_case_id(celex_id=celex)
                if case_id is None:
                    print(f"No case found for celex {celex}, skipping full text")
                    continue
                client.upsert_case_text(
                    case_id=case_id,
                    language=item.get("language", "en"),
                    source="CELLAR_ITEM",
                    fulltext=item.get("full_text") or item.get("text"),
                )
                loaded += 1

        print(f"{loaded}/{len(data)} full-text records loaded from {os.path.basename(file_location_path)}")
        os.remove(file_location_path)


if __name__ == "__main__":
    from clients.postgres import PostgresCLEClient

    with PostgresCLEClient() as client:
        load_fulltext(client, [JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR])
