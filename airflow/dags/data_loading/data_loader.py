"""
Main data loader. Upload Cellar, ECHR and RS case metadata, full text, and
citation graph edges into Postgres (cle_v2 schema, issue #42).

"""

import csv
import logging
import os
import time
from csv import DictReader
from ctypes import c_long, sizeof
from os.path import basename

from data_loading.case_text_loader import load_fulltext
from data_loading.citation_graph_loader import load_citation_graph
from data_loading.clients.postgres import PostgresCLEClient
from data_loading.row_processors.postgres import (
    PostgresCelexProcessor,
    PostgresItemIdProcessor,
    PostgresRSProcessor,
)
from definitions.storage_handler import (
    CSV_CELLAR_CASES,
    CSV_ECHR_CASES,
    CSV_RS_CASES,
    JSON_FULL_TEXT_CELLAR,
    JSON_FULL_TEXT_ECHR,
    get_path_processed,
)
from dotenv import load_dotenv

load_dotenv()

signed = c_long(-1).value < c_long(0).value
bit_size = sizeof(c_long) * 8
signed_limit = 2 ** (bit_size - 1)
csv.field_size_limit(signed_limit - 1 if signed else 2 * signed_limit - 1)

# rows per multi-row upsert statement; one commit per batch
BATCH_SIZE = int(os.getenv("LOAD_BATCH_SIZE", "500"))


def _processor_for(input_path, client):
    """Pick the row processor from the file name (works for both the global
    processed paths and month-scoped ones)."""
    name = basename(input_path)
    if name.startswith(CSV_CELLAR_CASES.split(".csv")[0]):
        return PostgresCelexProcessor(input_path, client)
    if name.startswith(CSV_ECHR_CASES.split(".csv")[0]):
        return PostgresItemIdProcessor(input_path, client)
    return PostgresRSProcessor(input_path, client)


def _deduplicate_rows(rows, row_processor):
    """Collapse a processed artifact to its source-specific identity.

    The loaders upsert by natural key, so repeated keys are not missing rows.
    Deduplicating the whole artifact (rather than independently per batch)
    also avoids counting or loading the same case more than once when source
    windows overlap or a feed repeats an entry.  The last occurrence wins,
    matching ``_BaseRowProcessor.upload_rows``.
    """
    by_key = {}
    missing_keys = 0
    for row in rows:
        key = row_processor._key(row)
        if not key:
            missing_keys += 1
            continue
        by_key[key] = row
    return list(by_key.values()), missing_keys


def load_data(
    input_paths=None, full_text_paths=None, citation_sources=None, edge_dir=None
):
    """
    Load processed CSVs (and optionally full-text JSONs + citation edge
    files) into Postgres.

    input_paths: processed *_clean.csv files; defaults to the three global
        processed paths.
    full_text_paths: full-text JSON files to load; defaults to both the
        Cellar and ECHR globals. Pass [] to skip.
    citation_sources: which edge-file sets to load ('EURLEX', 'ECHR');
        defaults to both. Pass [] to skip.
    edge_dir: directory holding the edge txt files; defaults to the global
        raw dir.
    """
    start = time.time()
    if input_paths is None:
        input_paths = [
            get_path_processed(CSV_RS_CASES),
            get_path_processed(CSV_ECHR_CASES),
            get_path_processed(CSV_CELLAR_CASES),
        ]
    if full_text_paths is None:
        full_text_paths = [JSON_FULL_TEXT_CELLAR, JSON_FULL_TEXT_ECHR]
    logging.info(
        "Loading into Postgres (cle_v2): %s", [basename(p) for p in input_paths]
    )

    with PostgresCLEClient() as client:
        for input_path in input_paths:
            if not os.path.exists(input_path):
                logging.warning(f"FILE {input_path} DOES NOT EXIST")
                continue
            logging.info(f"--- START {basename(input_path)} ---")

            case_counter = 0
            row_counter = 0
            row_processor = _processor_for(input_path, client)

            with open(input_path, "r", newline="", encoding="utf8") as in_file:
                reader = DictReader(in_file)
                # ECHR variants must be grouped across the complete monthly
                # artifact. Splitting at an arbitrary batch boundary can put
                # the English and French documents for one case into separate
                # case rows. Monthly HUDOC files are small enough to retain.
                if isinstance(row_processor, PostgresItemIdProcessor):
                    rows = list(reader)
                    case_counter = len(rows)
                    row_counter = row_processor.upload_rows(rows)
                    logging.info(f"... {case_counter} rows read")
                    logging.info(
                        f"{case_counter} cases processed ({row_counter} rows upserted)."
                    )
                    if row_counter != case_counter:
                        raise RuntimeError(
                            f"ECHR load incomplete: {row_counter}/{case_counter} document rows upserted"
                        )
                    continue
                rows = list(reader)
                case_counter = len(rows)
                unique_rows, missing_keys = _deduplicate_rows(rows, row_processor)
                if missing_keys:
                    raise RuntimeError(
                        f"Load input {basename(input_path)} contains "
                        f"{missing_keys} row(s) without {row_processor.key_field}"
                    )
                duplicate_count = case_counter - len(unique_rows)
                if duplicate_count:
                    logging.info(
                        "Collapsed %s duplicate source row(s) in %s to %s unique identities",
                        duplicate_count,
                        basename(input_path),
                        len(unique_rows),
                    )
                for offset in range(0, len(unique_rows), BATCH_SIZE):
                    batch = unique_rows[offset : offset + BATCH_SIZE]
                    row_counter += row_processor.upload_rows(batch)
                    logging.info(
                        "... %s/%s unique rows loaded",
                        min(offset + BATCH_SIZE, len(unique_rows)),
                        len(unique_rows),
                    )

            expected_count = len(unique_rows)
            logging.info(
                "%s source rows processed (%s unique rows, %s upserted).",
                case_counter,
                expected_count,
                row_counter,
            )
            if row_counter != expected_count:
                raise RuntimeError(
                    f"Load incomplete for {basename(input_path)}: "
                    f"{row_counter}/{expected_count} unique rows upserted"
                )

        if full_text_paths:
            load_fulltext(client, full_text_paths)
        if citation_sources is None or citation_sources:
            load_citation_graph(client, sources=citation_sources, edge_dir=edge_dir)
    end = time.time()
    logging.info("--- DONE ---")
    logging.info(f"Time taken: {time.strftime('%H:%M:%S', time.gmtime(end - start))}")


if __name__ == "__main__":
    load_data()
