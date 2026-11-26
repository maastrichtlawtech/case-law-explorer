"""EU, Council of Europe and UN acts in ``legislation`` (roadmap R3.1, R3.7).

Modules:

    celex          CELEX numbers: the act a reference names, its type and year
    acts           the act record, the curated fixture (external_acts.json),
                   the legislation artifact
    catalog        extractor: acts for the CELEX numbers the database refers to
    law_reference  the law-reference record and artifact (case -> provision)
    echr_articles  extractor: echr_document_article -> ECHR provisions (R3.7)

Loader: data_loading/legislation_loader.py. Weekly wiring and the backfill
CLI: linking_tasks.py (flag LEGISLATION_EXTERNAL_ENABLED).
"""
