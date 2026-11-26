"""Shared plumbing for the case-context extractors: case selection by
cases.id (case_ids or an inclusive id range, keyset paging) and the CLI."""

import argparse
import logging
import os

SCHEMA = "cle_v2"
BATCH_SIZE = 500

# Appended to an extractor's WHERE clause; the query must alias cases as c
# and take %(after)s, %(from_id)s, %(to_id)s, %(case_ids)s, %(limit)s.
CASE_FILTER = """
       AND c.id > %(after)s
       AND (%(from_id)s::bigint IS NULL OR c.id >= %(from_id)s)
       AND (%(to_id)s::bigint IS NULL OR c.id <= %(to_id)s)
       AND (%(case_ids)s::bigint[] IS NULL OR c.id = ANY(%(case_ids)s))
"""


def iter_rows(conn, sql, case_ids=None, id_range=None, batch_size=BATCH_SIZE, extra=None):
    """Yield batches of rows of sql (first column cases.id, ordered by it),
    ending the read snapshot between batches."""
    from_id, to_id = id_range if id_range else (None, None)
    after = 0
    while True:
        params = {
            "after": after,
            "from_id": from_id,
            "to_id": to_id,
            "case_ids": list(case_ids) if case_ids is not None else None,
            "limit": batch_size,
        }
        params.update(extra or {})
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        conn.rollback()  # read only
        if not rows:
            return
        after = rows[-1][0]
        yield rows


def cli(description, extract, argv=None):
    """``--dsn-env VAR [--from-id N] [--to-id M] --out PATH`` over extract(conn,
    id_range=..., out_path=...), read-only."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("--from-id", type=int)
    parser.add_argument("--to-id", type=int)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    import psycopg2

    logging.basicConfig(level=logging.INFO)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f"environment variable {args.dsn_env} is not set")
    conn = psycopg2.connect(dsn)
    try:
        conn.set_session(readonly=True)
        id_range = None
        if args.from_id is not None or args.to_id is not None:
            id_range = (args.from_id, args.to_id)
        written, stats = extract(conn, id_range=id_range, out_path=args.out)
    finally:
        conn.close()
    print(f"{written} records -> {args.out}; {dict(sorted(stats.items()))}")
    return 0
