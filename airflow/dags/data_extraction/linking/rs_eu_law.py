"""
EU-law references in Rechtspraak texts (roadmap R3.3).

Scans case_text rows with source 'RECHTSPRAAK' (``fulltext`` and
``summary``) for EU law cited by number, treaty articles, Charter articles and
the GDPR (rules: eu_law.scan, profile 'rs') and writes law-reference records
with source_dataset 'rs_text_eu_law' (law_artifact.py), loaded by
data_loading.law_reference_loader.

CLI: ``python -m data_extraction.linking.rs_eu_law --dsn-env VAR --from-id N
--to-id M --out PATH [--load]`` (read-only connection unless --load).
"""

import sys

from data_extraction.linking import eu_law_text

DATASET = "rs_text_eu_law"
TEXT_SOURCE = "RECHTSPRAAK"
PROFILE = "rs"
DATASETS = (DATASET,)


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size=eu_law_text.BATCH_SIZE):
    return eu_law_text.extract(
        conn,
        TEXT_SOURCE,
        DATASET,
        PROFILE,
        case_ids=case_ids,
        id_range=id_range,
        out_path=out_path,
        batch_size=batch_size,
    )


def main(argv=None):
    from data_loading.law_reference_loader import run_cli

    return run_cli(extract, "EU-law references in Rechtspraak texts (R3.3)", argv)


if __name__ == "__main__":
    sys.exit(main())
