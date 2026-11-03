"""
Fills the shared ``cases`` columns for Rechtspraak and ECHR cases.

Production's RS and ECHR cases (loaded by the one-off migration) carry court,
document type, procedure, case number, language and a ``sources`` label of
``RS`` / ``ECHR``. The row processors only wrote ECLI, title and date, so a
case loaded by Airflow could not be filtered by court or type. These
statements derive the missing columns from the detail rows the processors have
just written, with the rules production's rows follow (verified on 2026-10-27
against 5,000 RS and 2,664 ECHR rows):

- RS court: the court production uses for the ECLI's court code
  (``rs_court_codes.py``, built from production), else ``RS:<instance>``;
  document type Uitspraak -> judgment, Conclusie -> opinion; procedure,
  case number (zaaknummer), language and publication date from rs_document.
- ECHR: court ECTHR; document type from the canonical HUDOC document
  (JUD -> judgment, DEC -> decision, COM -> communicated, else other);
  importance from it; case number is its first application number.

Columns are only filled, never overwritten, and the superseded labels
``Rechtspraak`` / ``HUDOC`` are replaced by ``RS`` / ``ECHR``.
"""

from data_loading.clients.postgres import SCHEMA
from data_loading.rs_court_codes import RS_COURT_CODES

S = SCHEMA


def rs_court_code(ecli, instance):
    """Production's court code for a Rechtspraak case."""
    parts = str(ecli or "").split(":")
    if len(parts) > 2 and parts[2] in RS_COURT_CODES:
        return RS_COURT_CODES[parts[2]]
    name = str(instance or "").strip()
    if name and "://" not in name:
        return f"RS:{name}"
    return None


SQL_RS_JURISDICTION = f"""
INSERT INTO {S}.jurisdiction (iso_code, name, type) VALUES ('NL', 'Netherlands', 'country')
ON CONFLICT (iso_code) DO NOTHING"""

SQL_RS_COURTS = f"""
INSERT INTO {S}.court (code, name, jurisdiction_id)
SELECT DISTINCT v.code, substr(v.code, 4), (SELECT id FROM {S}.jurisdiction WHERE iso_code = 'NL')
FROM unnest(%s::text[]) AS v(code)
WHERE v.code IS NOT NULL
ON CONFLICT (code) DO NOTHING"""

SQL_RS_PROCEDURES = f"""
INSERT INTO {S}.procedure_type (code, name)
SELECT DISTINCT p, p
FROM {S}.cases k JOIN {S}.rs_document d ON d.case_id = k.id,
     LATERAL (SELECT NULLIF(btrim(d.procedure_type), '') AS p) x
WHERE k.ecli = ANY(%s::text[]) AND p IS NOT NULL
ON CONFLICT (code) DO NOTHING"""

SQL_RS_DOCUMENT_TYPES = f"""
INSERT INTO {S}.document_type (code, name)
SELECT v.code, v.name FROM (VALUES ('judgment', 'Judgment'), ('opinion', 'Opinion (AG / Conclusie)')) v(code, name)
WHERE NOT EXISTS (SELECT 1 FROM {S}.document_type t WHERE t.code = v.code)"""

SQL_RS_CASES = f"""
UPDATE {S}.cases k SET
    sources = CASE WHEN array_remove(k.sources, 'Rechtspraak') @> ARRAY['RS']
                   THEN array_remove(k.sources, 'Rechtspraak')
                   ELSE array_remove(k.sources, 'Rechtspraak') || ARRAY['RS'] END,
    court_id = COALESCE(k.court_id, c.id),
    document_type_id = COALESCE(k.document_type_id, dt.id),
    procedure_type_id = COALESCE(k.procedure_type_id, pt.id),
    case_number = COALESCE(k.case_number, NULLIF(btrim(d.zaaknummer), '')),
    language_iso = COALESCE(k.language_iso, lang.iso_code),
    date_published = COALESCE(k.date_published, d.date_published),
    updated_at = now()
FROM unnest(%s::text[], %s::text[]) AS v(ecli, court_code)
JOIN {S}.cases kk ON kk.ecli = v.ecli
JOIN {S}.rs_document d ON d.case_id = kk.id
LEFT JOIN {S}.court c ON c.code = v.court_code
LEFT JOIN {S}.document_type dt ON dt.code = CASE lower(btrim(d.document_type))
    WHEN 'uitspraak' THEN 'judgment' WHEN 'conclusie' THEN 'opinion' END
LEFT JOIN {S}.procedure_type pt ON pt.code = NULLIF(btrim(d.procedure_type), '')
LEFT JOIN {S}.language lang ON lang.iso_code = lower(NULLIF(btrim(d.language), ''))
WHERE k.id = kk.id"""


def enrich_rs(client, pairs):
    """Fill cases columns for (ecli, instance) pairs whose rs_document rows exist."""
    pairs = [(ecli, instance) for ecli, instance in pairs if ecli]
    if not pairs:
        return 0
    eclis = [ecli for ecli, _ in pairs]
    courts = [rs_court_code(ecli, instance) for ecli, instance in pairs]
    client.execute_arrays(SQL_RS_JURISDICTION, [])
    client.execute_arrays(SQL_RS_COURTS, [sorted({c for c in courts if c})])
    client.execute_arrays(SQL_RS_PROCEDURES, [eclis])
    client.execute_arrays(SQL_RS_DOCUMENT_TYPES, [])
    return client.execute_arrays(SQL_RS_CASES, [eclis, courts])


def echr_document_type(doctype):
    value = str(doctype or "").upper()
    if "JUD" in value:
        return "judgment"
    if "DEC" in value:
        return "decision"
    if "COM" in value:
        return "communicated"
    return "other"


def echr_case_number(appno):
    tokens = [t.strip() for t in str(appno or "").split(";") if t.strip()]
    return tokens[0] if tokens else None


def echr_importance(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 4 else None


SQL_ECHR_LOOKUPS = f"""
WITH j AS (
    INSERT INTO {S}.jurisdiction (iso_code, name, type) VALUES ('CE', 'Council of Europe', 'international')
    ON CONFLICT (iso_code) DO NOTHING RETURNING id
)
INSERT INTO {S}.court (code, name, level, jurisdiction_id)
SELECT 'ECTHR', 'European Court of Human Rights', 'international',
       COALESCE((SELECT id FROM j), (SELECT id FROM {S}.jurisdiction WHERE iso_code = 'CE'))
ON CONFLICT (code) DO NOTHING"""

SQL_ECHR_DOCUMENT_TYPES = f"""
INSERT INTO {S}.document_type (code, name)
SELECT v.code, v.name FROM (VALUES ('judgment', 'Judgment'), ('decision', 'Decision'),
    ('communicated', 'Communicated case'), ('other', 'Other')) v(code, name)
WHERE NOT EXISTS (SELECT 1 FROM {S}.document_type t WHERE t.code = v.code)"""

SQL_ECHR_CASE = f"""
UPDATE {S}.cases k SET
    sources = CASE WHEN array_remove(k.sources, 'HUDOC') @> ARRAY['ECHR']
                   THEN array_remove(k.sources, 'HUDOC')
                   ELSE array_remove(k.sources, 'HUDOC') || ARRAY['ECHR'] END,
    court_id = COALESCE(k.court_id, (SELECT id FROM {S}.court WHERE code = 'ECTHR')),
    document_type_id = COALESCE(k.document_type_id,
        (SELECT id FROM {S}.document_type WHERE code = %s)),
    case_number = COALESCE(k.case_number, %s),
    importance = COALESCE(k.importance, %s::smallint),
    updated_at = now()
WHERE k.id = %s"""


def ensure_echr_lookups(client):
    client.execute_arrays(SQL_ECHR_LOOKUPS, [])
    client.execute_arrays(SQL_ECHR_DOCUMENT_TYPES, [])


def enrich_echr(client, case_id, doctype, appno, importance):
    """Fill cases columns for one ECHR case from its canonical document."""
    return client.execute_arrays(
        SQL_ECHR_CASE,
        [echr_document_type(doctype), echr_case_number(appno), echr_importance(importance), case_id],
    )
