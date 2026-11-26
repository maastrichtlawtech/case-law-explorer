"""
EU-law references in ECtHR texts (roadmap R3.4).

Scans case_text rows with source 'HUDOC' (``fulltext`` and ``summary``) for
EU directives, regulations and (framework) decisions by number, TFEU/TEU/EC
Treaty articles, EU Charter articles and the GDPR (rules: eu_law.scan,
profile 'echr': the bare word "Charter"/"Charte" counts as the EU Charter only
when the text names the Charter of Fundamental Rights and no other charter),
and writes law-reference records with source_dataset 'echr_text_eu_law'.

Out of scope: the Convention's own articles (already in echr_document_article,
roadmap R3.7) and national law cited in ECtHR judgments (dozens of
legislations and languages; no rule here would be precise enough).

CLI: ``python -m data_extraction.linking.echr_eu_law --dsn-env VAR --from-id N
--to-id M --out PATH [--load]`` (read-only connection unless --load).
"""

import sys

from data_extraction.linking import eu_law_text

DATASET = "echr_text_eu_law"
TEXT_SOURCE = "HUDOC"
PROFILE = "echr"
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

    return run_cli(extract, "EU-law references in ECtHR texts (R3.4)", argv)


if __name__ == "__main__":
    sys.exit(main())
