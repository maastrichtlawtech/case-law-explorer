"""
Fill and maintain cle_v2.case_identifier (R1.2 / R1.2a) from data already in
the database.

For a list of case ids (the weekly loaders, after each batch) or an id range
(the historical backfill, cjeu-migration 65_backfill_case_identifier.py) it
reads the raw identifiers, normalises them with
data_extraction/linking/identifiers.py (in Python, so there is no SQL twin to
keep in step) and inserts one row per (case, scheme, normalised value):

    scheme            source                              is_primary
    ecli              cases.ecli                          true
    celex             cases.celex_id                      true for CJEU cases
    cjeu_case_number  cjeu_document.case_number           true for its first number
    cjeu_case_number  cellar_joins                        false
    echr_appno        echr_document_appno                 true when it is cases.case_number
    nl_zaaknummer     rs_document.zaaknummer              false (every variant)
    ljn               rs_document.replaces_identifier     false

Cellar ``joins`` rows are case_citation rows (relation_type 'joins',
source_dataset 'cellar_sparql') whose target is, in production, a Cellar
dossier URI kept in target_celex_raw. A member's case number is found without
network access when the target is resolved (target_case_id), when the raw
value is a CELEX (the case number follows from the CELEX), or when another
document in the database belongs to that dossier (cjeu_document.dossier_uri).
Members whose dossier holds no document of ours stay unresolved and are
counted; resolving them needs Cellar's cdm:dossier_identifier (R2.5).

Insert-only: ON CONFLICT (case_id, scheme, value_normalized) DO NOTHING, so a
batch can be replayed (the promoter) and the backfill rerun. Nothing is
updated or deleted. The caller owns the transaction unless commit=True.

Weekly loaders call maintain_for_keys() behind CASE_IDENTIFIER_ENABLED (env,
default off), so the code ships before migration 0009 is deployed.

Backfill CLI (prints counts as JSON):

    python -m data_loading.identifier_loader --dsn-env CLE_DSN --from-id 1 --to-id 500000
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict

from data_extraction.linking.identifiers import (
    CJEU_CASE_NUMBER_RE,
    normalize_celex,
    normalize_cjeu_case_number,
    normalize_echr_appno,
    normalize_ecli,
    normalize_ljn,
    zaaknummer_variants,
)

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
FLAG = "CASE_IDENTIFIER_ENABLED"
SCHEMES = ("ecli", "celex", "cjeu_case_number", "echr_appno", "nl_zaaknummer", "ljn")
MAX_EXAMPLES = 20
INSERT_PAGE_SIZE = 1000
DEFAULT_RANGE_BATCH = 5000


def enabled():
    """CASE_IDENTIFIER_ENABLED is set to a true value (default off)."""
    return os.getenv(FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# splitting raw values (pure)
# ---------------------------------------------------------------------------

# Words between two case numbers that make a range: "C-199/12 tot en met
# C-201/12", "C-199/12 to C-201/12", "C-199/12 à C-201/12", "t/m".
_RANGE_GAP_RE = re.compile(
    r"^\s*(?:tot\s+en\s+met|t/m|to|until|à|a|bis|al)\s*$", flags=re.IGNORECASE
)
# A range is expanded only within one court and year, and only when short;
# anything longer is more likely two unrelated numbers than a joined batch.
MAX_RANGE = 50


def split_cjeu_case_numbers(text):
    """Every case number in a cjeu_document.case_number-style text, as found.

    'C-199/12, C-200/12' -> ['C-199/12', 'C-200/12'];
    'C‑199/12 tot en met C‑201/12' -> ['C‑199/12', 'C-200/12', 'C‑201/12'];
    'C-221/17 P' -> ['C-221/17 P']. Values are what identifiers.py parses;
    numbers filled in from a range are written 'C-200/12'.
    """
    if not text:
        return []
    text = str(text)
    upper = text.upper()
    if len(upper) != len(text):  # 'ß' -> 'SS' would shift the offsets
        text = upper
    matches = list(CJEU_CASE_NUMBER_RE.finditer(upper))
    # (start, end of the value) per match. 'TO' is also a procedure suffix
    # (third-party opposition); directly followed by another case number it is
    # the word 'to' of a range, not part of the first number.
    spans = []
    for index, match in enumerate(matches):
        end = match.end()
        if (
            match.group("suffix") == "TO"
            and index + 1 < len(matches)
            and not upper[match.end() : matches[index + 1].start()].strip()
        ):
            end = match.start("suffix")
        spans.append((match.start(), end))
    found = []
    for index, match in enumerate(matches):
        if index > 0:
            previous = matches[index - 1]
            gap = text[spans[index - 1][1] : match.start()]
            court, year = match.group("court") or "", match.group("year")
            first, last = int(previous.group("number")), int(match.group("number"))
            if (
                _RANGE_GAP_RE.match(gap)
                and (previous.group("court") or "") == court
                and previous.group("year") == year
                and 1 < last - first <= MAX_RANGE
            ):
                prefix = f"{court}-" if court else ""
                found.extend(f"{prefix}{n}/{year}" for n in range(first + 1, last))
        start, end = spans[index]
        found.append(text[start:end].strip())
    return found


# Separators between several zaaknummers in one rs_document.zaaknummer value:
# ',', ';', ' en ', ' and ', ' & '. A slash, even with spaces round it
# ('C/13/123456 / HA ZA 12-345'), is part of one number.
_ZAAKNUMMER_SPLIT_RE = re.compile(r"\s*[;,]\s*|\s+(?:en|and|&)\s+", flags=re.IGNORECASE)


def split_zaaknummers(text):
    """'201504577/1/A3, 201507057/1/A3 en 201601993/1/A3' -> three numbers, as found."""
    if not text:
        return []
    return [piece.strip() for piece in _ZAAKNUMMER_SPLIT_RE.split(str(text)) if piece.strip()]


_LJN_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{2}\d{4}(?![A-Za-z0-9])")


def split_ljns(text):
    """LJNs in rs_document.replaces_identifier ('BW3076', 'LJN: BW3076'), as found.

    Anything else there (an ECLI, a free-text label) yields nothing."""
    if not text:
        return []
    value = str(text).strip()
    if normalize_ecli(value):
        return []
    return [match.group(0) for match in _LJN_TOKEN_RE.finditer(value)]


def split_appnos(text):
    """echr_document_appno.appno is one number per row; tolerate ';' lists."""
    if not text:
        return []
    return [piece.strip() for piece in str(text).split(";") if piece.strip()]


_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def cellar_uuid(value):
    """The Cellar UUID in a resource URI, lower-case, or None."""
    match = _UUID_RE.search(str(value or "").lower())
    return match.group(0) if match else None


def case_number_from_celex(celex):
    """'62012CJ0199' -> 'C-199/12' (sector 6 and 8 case law), else None.

    Same rule as cjeu_mapping.case_number, which is how cjeu_document.case_number
    is filled."""
    from data_loading.cjeu_mapping import case_number

    return case_number(normalize_celex(celex))


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------


class _Collector:
    """Candidate rows plus per-scheme counts and rejected examples."""

    def __init__(self):
        self.rows = {}  # (case_id, scheme, value_normalized) -> row tuple, first wins
        self.counts = defaultdict(Counter)
        self.examples = defaultdict(list)

    def add(self, case_id, scheme, value, normalized, source, is_primary):
        self.counts[scheme]["candidates"] += 1
        key = (case_id, scheme, normalized)
        if key in self.rows:
            # Same identifier from a second source: already present.
            self.counts[scheme]["duplicate_in_batch"] += 1
            return
        self.rows[key] = (case_id, scheme, value, normalized, source, is_primary)

    def reject(self, scheme, case_id, value, source, reason="unparseable"):
        self.counts[scheme]["rejected"] += 1
        if len(self.examples[scheme]) < MAX_EXAMPLES:
            self.examples[scheme].append(
                {"case_id": case_id, "value": value, "source": source, "reason": reason}
            )

    def unresolved(self, scheme, case_id, value, source, reason):
        self.counts[scheme]["unresolved"] += 1
        key = f"{scheme}:unresolved"
        if len(self.examples[key]) < MAX_EXAMPLES:
            self.examples[key].append(
                {"case_id": case_id, "value": value, "source": source, "reason": reason}
            )


def _where(column, case_ids, id_range):
    if case_ids is not None:
        return f"{column} = ANY(%(ids)s)", {"ids": sorted(set(case_ids))}
    low, high = id_range
    return f"{column} BETWEEN %(low)s AND %(high)s", {"low": low, "high": high}


def _fetch(cursor, sql, params):
    cursor.execute(sql, params)
    return cursor.fetchall()


def _collect_cases(cursor, out, where):
    clause, params = where("id")
    rows = _fetch(
        cursor, f"SELECT id, ecli, celex_id, sources FROM {SCHEMA}.cases WHERE {clause}", params
    )
    for case_id, ecli, celex, sources in rows:
        if ecli:
            normalized = normalize_ecli(ecli)
            if normalized:
                out.add(case_id, "ecli", ecli, normalized, "cases.ecli", True)
            else:
                out.reject("ecli", case_id, ecli, "cases.ecli")
        if celex:
            normalized = normalize_celex(celex)
            if normalized:
                is_cjeu = "CJEU" in (sources or [])
                out.add(case_id, "celex", celex, normalized, "cases.celex_id", is_cjeu)
            else:
                out.reject("celex", case_id, celex, "cases.celex_id")


def _add_case_numbers(out, case_id, text, source, primary_first):
    numbers = split_cjeu_case_numbers(text)
    if not numbers:
        out.reject("cjeu_case_number", case_id, text, source)
        return
    for index, value in enumerate(numbers):
        normalized = normalize_cjeu_case_number(value)
        if normalized is None:  # cannot happen for a regex match; keep the guard
            out.reject("cjeu_case_number", case_id, value, source)
            continue
        out.add(
            case_id,
            "cjeu_case_number",
            value,
            normalized,
            source,
            primary_first and index == 0,
        )


def _collect_cjeu(cursor, out, where):
    clause, params = where("case_id")
    rows = _fetch(
        cursor,
        f"SELECT case_id, case_number FROM {SCHEMA}.cjeu_document "
        f"WHERE {clause} AND case_number IS NOT NULL AND case_number <> ''",
        params,
    )
    for case_id, text in rows:
        _add_case_numbers(out, case_id, text, "cjeu_document.case_number", True)


def _collect_joins(cursor, out, where):
    clause, params = where("cc.source_case_id")
    rows = _fetch(
        cursor,
        f"""
        SELECT cc.source_case_id, cc.target_case_id,
               COALESCE(cc.target_celex_raw, cc.target_ecli_raw), td.case_number
          FROM {SCHEMA}.case_citation cc
          LEFT JOIN {SCHEMA}.cjeu_document td ON td.case_id = cc.target_case_id
         WHERE {clause} AND cc.relation_type = 'joins'
        """,
        params,
    )
    pending = []  # (source_case_id, raw) needing a lookup by CELEX or dossier
    for source_case_id, target_case_id, raw, target_number in rows:
        if target_case_id is not None and target_number:
            _add_case_numbers(out, source_case_id, target_number, "cellar_joins", False)
        elif raw:
            pending.append((source_case_id, raw))
        else:
            out.unresolved("cjeu_case_number", source_case_id, None, "cellar_joins", "no target")
    if not pending:
        return
    celexes = sorted({normalize_celex(raw) for _, raw in pending if normalize_celex(raw)})
    uuids = sorted({cellar_uuid(raw) for _, raw in pending if cellar_uuid(raw)})
    by_celex = {}
    if celexes:
        for celex, number in _fetch(
            cursor,
            f"""
            SELECT k.celex_id, d.case_number FROM {SCHEMA}.cases k
              JOIN {SCHEMA}.cjeu_document d ON d.case_id = k.id
             WHERE k.celex_id = ANY(%(celexes)s) AND d.case_number IS NOT NULL
            """,
            {"celexes": celexes},
        ):
            by_celex[celex] = number
    by_dossier = defaultdict(set)
    if uuids:
        for uuid, number in _fetch(
            cursor,
            f"""
            SELECT lower(substring(d.dossier_uri FROM
                   '[0-9A-Fa-f]{{8}}-[0-9A-Fa-f]{{4}}-[0-9A-Fa-f]{{4}}-[0-9A-Fa-f]{{4}}-[0-9A-Fa-f]{{12}}')),
                   d.case_number
              FROM {SCHEMA}.cjeu_document d
             WHERE d.dossier_uri IS NOT NULL AND d.case_number IS NOT NULL
               AND lower(substring(d.dossier_uri FROM
                   '[0-9A-Fa-f]{{8}}-[0-9A-Fa-f]{{4}}-[0-9A-Fa-f]{{4}}-[0-9A-Fa-f]{{4}}-[0-9A-Fa-f]{{12}}'))
                   = ANY(%(uuids)s)
            """,
            {"uuids": uuids},
        ):
            by_dossier[uuid].add(number)
    for source_case_id, raw in pending:
        celex = normalize_celex(raw)
        uuid = cellar_uuid(raw)
        if celex:
            number = by_celex.get(celex) or case_number_from_celex(celex)
            if number:
                _add_case_numbers(out, source_case_id, number, "cellar_joins", False)
            else:
                out.unresolved(
                    "cjeu_case_number", source_case_id, raw, "cellar_joins", "CELEX not case law"
                )
        elif uuid and by_dossier.get(uuid):
            numbers = by_dossier[uuid]
            if len(numbers) > 1:
                # One dossier, documents filed under different numbers: take none.
                out.unresolved(
                    "cjeu_case_number",
                    source_case_id,
                    raw,
                    "cellar_joins",
                    f"dossier has several case numbers: {sorted(numbers)}",
                )
                continue
            _add_case_numbers(out, source_case_id, next(iter(numbers)), "cellar_joins", False)
        else:
            out.unresolved(
                "cjeu_case_number",
                source_case_id,
                raw,
                "cellar_joins",
                "dossier not in database" if uuid else "unrecognised target",
            )


def _collect_echr(cursor, out, where):
    clause, params = where("d.case_id")
    rows = _fetch(
        cursor,
        f"""
        SELECT DISTINCT d.case_id, a.appno, k.case_number
          FROM {SCHEMA}.echr_document d
          JOIN {SCHEMA}.echr_document_appno a
            ON a.item_id = d.item_id AND a.source = 'appno'
          JOIN {SCHEMA}.cases k ON k.id = d.case_id
         WHERE {clause}
         ORDER BY d.case_id, a.appno
        """,
        params,
    )
    for case_id, appno, case_number in rows:
        primary = normalize_echr_appno(case_number) if case_number else None
        for value in split_appnos(appno):
            normalized = normalize_echr_appno(value)
            if normalized is None:
                out.reject("echr_appno", case_id, value, "echr_document_appno")
                continue
            out.add(
                case_id,
                "echr_appno",
                value,
                normalized,
                "echr_document_appno",
                normalized == primary,
            )


def _collect_rs(cursor, out, where):
    clause, params = where("case_id")
    rows = _fetch(
        cursor,
        f"""
        SELECT case_id, zaaknummer, replaces_identifier FROM {SCHEMA}.rs_document
         WHERE {clause} AND (zaaknummer IS NOT NULL OR replaces_identifier IS NOT NULL)
        """,
        params,
    )
    for case_id, zaaknummer, replaces in rows:
        if zaaknummer and zaaknummer.strip():
            for piece in split_zaaknummers(zaaknummer):
                if not re.search(r"\d", piece):
                    out.reject("nl_zaaknummer", case_id, piece, "rs_document.zaaknummer")
                    continue
                for normalized in zaaknummer_variants(piece):
                    out.add(
                        case_id,
                        "nl_zaaknummer",
                        piece,
                        normalized,
                        "rs_document.zaaknummer",
                        False,
                    )
        if replaces and replaces.strip():
            ljns = split_ljns(replaces)
            if not ljns:
                out.reject("ljn", case_id, replaces, "rs_document.replaces_identifier")
            for value in ljns:
                normalized = normalize_ljn(value)
                if normalized is None:
                    out.reject("ljn", case_id, value, "rs_document.replaces_identifier")
                    continue
                out.add(case_id, "ljn", value, normalized, "rs_document.replaces_identifier", False)


_INSERT = f"""
    INSERT INTO {SCHEMA}.case_identifier
        (case_id, scheme, value, value_normalized, source, is_primary)
    VALUES %s
    ON CONFLICT (case_id, scheme, value_normalized) DO NOTHING
    RETURNING scheme
"""


def load_identifiers(conn, case_ids=None, id_range=None, commit=False):
    """Insert identifier rows for case_ids (iterable) or id_range ((low, high), inclusive).

    Returns {"schemes": {scheme: {candidates, inserted, already_present,
    rejected, unresolved, duplicate_in_batch}}, "examples": {...}} with
    zero counts left out. The caller owns the transaction unless commit=True.
    """
    from psycopg2.extras import execute_values

    if (case_ids is None) == (id_range is None):
        raise ValueError("pass exactly one of case_ids or id_range")
    if case_ids is not None:
        case_ids = [int(i) for i in case_ids if i is not None]
        if not case_ids:
            return {"schemes": {}, "examples": {}}

    def where(column):
        return _where(column, case_ids, id_range)

    out = _Collector()
    with conn.cursor() as cursor:
        # Order matters only for which source wins a duplicate within the batch.
        _collect_cases(cursor, out, where)
        _collect_cjeu(cursor, out, where)
        _collect_joins(cursor, out, where)
        _collect_echr(cursor, out, where)
        _collect_rs(cursor, out, where)
        rows = list(out.rows.values())
        inserted = Counter()
        if rows:
            returned = execute_values(cursor, _INSERT, rows, page_size=INSERT_PAGE_SIZE, fetch=True)
            inserted.update(scheme for (scheme,) in returned)
    if commit:
        conn.commit()

    schemes = {}
    for scheme in SCHEMES:
        c = out.counts[scheme]
        unique = sum(1 for key in out.rows if key[1] == scheme)
        c["inserted"] = inserted[scheme]
        c["already_present"] = unique - inserted[scheme]
        values = {k: v for k, v in sorted(c.items()) if v}
        if values:
            schemes[scheme] = values
    for key, examples in sorted(out.examples.items()):
        log.warning("case_identifier %s (%s): %s", key, len(examples), examples)
    log.info("case_identifier: %s", schemes)
    return {"schemes": schemes, "examples": dict(out.examples)}


def merge_counts(total, part):
    """Add one load_identifiers() result into a running total (in place)."""
    for scheme, counts in part["schemes"].items():
        bucket = total.setdefault("schemes", {}).setdefault(scheme, {})
        for name, value in counts.items():
            bucket[name] = bucket.get(name, 0) + value
    for key, examples in part["examples"].items():
        kept = total.setdefault("examples", {}).setdefault(key, [])
        kept.extend(examples[: MAX_EXAMPLES - len(kept)])
    return total


def backfill_range(conn, from_id, to_id, batch_size=DEFAULT_RANGE_BATCH, progress=None):
    """load_identifiers over [from_id, to_id] in id windows, one commit per window."""
    total = {"schemes": {}, "examples": {}}
    low = from_id
    while low <= to_id:
        high = min(low + batch_size - 1, to_id)
        try:
            part = load_identifiers(conn, id_range=(low, high), commit=True)
        except Exception:
            conn.rollback()
            raise
        merge_counts(total, part)
        if progress is not None:
            progress(low, high, part)
        low = high + 1
    return total


# ---------------------------------------------------------------------------
# weekly loaders
# ---------------------------------------------------------------------------

_KEY_COLUMNS = {"ecli": "ecli", "celex": "celex_id", "item_id": "item_id", "id": "id"}


def maintain_for_keys(client, key, values):
    """After a load batch: case_identifier rows for the cases named by values.

    key is 'ecli', 'celex', 'item_id' or 'id'. Does nothing unless
    CASE_IDENTIFIER_ENABLED is set. Runs in its own transaction right after the
    batch's, and never fails the load: an error is logged and the backfill
    (rerunnable, insert-only) fills the gap.
    """
    if not enabled():
        return None
    values = sorted({v for v in values if v})
    if not values:
        return None
    column = _KEY_COLUMNS[key]
    try:
        with client.transaction():
            conn = client._get_conn()
            if column == "id":
                case_ids = values
            else:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT id FROM {SCHEMA}.cases WHERE {column} = ANY(%s)", (values,)
                    )
                    case_ids = [row[0] for row in cursor.fetchall()]
            return load_identifiers(conn, case_ids=case_ids)
    except Exception:
        log.exception("case_identifier maintenance failed for %s %s values", len(values), key)
        return None


SQL_ECHR_OWNER_APPNO = f"""
INSERT INTO {SCHEMA}.echr_document_appno (item_id, appno, source)
SELECT DISTINCT v.item_id, v.appno, 'appno'
  FROM unnest(%s::text[], %s::text[]) AS v(item_id, appno)
  JOIN {SCHEMA}.echr_document d ON d.item_id = v.item_id
ON CONFLICT DO NOTHING"""


def record_echr_owner_appnos(client, pairs):
    """(item_id, HUDOC 'appno' field) -> echr_document_appno rows with source 'appno'.

    The weekly ECHR loader stores the owner numbers nowhere else (the
    migration copied them from legacy), so case_identifier could not see them.
    Insert-only; behind CASE_IDENTIFIER_ENABLED like the rest of this module.
    """
    if not enabled():
        return 0
    rows = sorted({(item_id, appno) for item_id, raw in pairs for appno in split_appnos(raw)})
    if not rows:
        return 0
    try:
        with client.transaction():
            return client.execute_arrays(
                SQL_ECHR_OWNER_APPNO, [[r[0] for r in rows], [r[1] for r in rows]]
            )
    except Exception:
        log.exception("echr_document_appno owner rows failed for %s items", len(pairs))
        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m data_loading.identifier_loader",
        description=(
            "Backfill cle_v2.case_identifier for a range of case ids; prints counts as JSON."
        ),
    )
    parser.add_argument(
        "--dsn-env", required=True, help="name of the environment variable holding the DSN"
    )
    parser.add_argument("--from-id", type=int, required=True)
    parser.add_argument("--to-id", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_RANGE_BATCH)
    args = parser.parse_args(argv)
    if args.to_id < args.from_id:
        parser.error("--to-id must not be below --from-id")
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f"environment variable {args.dsn_env} is not set")
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    import psycopg2

    conn = psycopg2.connect(dsn)
    try:
        total = backfill_range(conn, args.from_id, args.to_id, batch_size=args.batch_size)
    finally:
        conn.close()
    result = {"from_id": args.from_id, "to_id": args.to_id, **total}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
