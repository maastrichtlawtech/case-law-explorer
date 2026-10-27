"""
Writes mapped CJEU cases (cjeu_mapping.py) into cle_v2.

The statements are the migration's (cjeu-migration 62_load_new_cjeu_cases_via_runner.py),
schema-qualified and run once per batch with array parameters. Differences,
all needed for a recurring load rather than a one-off insert of new cases:

- an existing case is enriched: NULL columns of ``cases`` and ``cjeu_document``
  are filled and 'CJEU' is added to ``cases.sources``; nothing is overwritten;
- unresolved citations whose target is a case of this batch are linked
  (CELLAR rows by CELEX, Rechtspraak/ECHR rows by ECLI), so citations stored
  before their target arrived stop dangling.

Every statement is idempotent, so the promoter can replay a batch.
"""

import logging
from collections import defaultdict

from data_loading.clients.postgres import SCHEMA
from data_loading.cjeu_mapping import NATIONAL_TARGETS, celex_well_formed, map_row, extractor_row

S = SCHEMA

SQL_LANGUAGE = f"""
INSERT INTO {S}.language (iso_code, name)
SELECT DISTINCT v, v FROM unnest(%s::text[]) AS v
ON CONFLICT (iso_code) DO NOTHING"""

SQL_PROCEDURE = f"""
INSERT INTO {S}.procedure_type (code, name)
SELECT DISTINCT v, v FROM unnest(%s::text[]) AS v
ON CONFLICT (code) DO NOTHING"""

SQL_JUDGE = f"""
INSERT INTO {S}.judge (full_name)
SELECT DISTINCT v FROM unnest(%s::text[]) AS v
WHERE NOT EXISTS (SELECT 1 FROM {S}.judge j WHERE j.full_name = v)"""

SQL_PARTY = f"""
INSERT INTO {S}.party (canonical_name, role_class)
SELECT DISTINCT v.name, v.rc FROM unnest(%s::text[], %s::text[]) AS v(name, rc)
WHERE NOT EXISTS (SELECT 1 FROM {S}.party p
                  WHERE p.canonical_name = v.name AND p.role_class = v.rc)"""

SQL_DOMAIN = f"""
INSERT INTO {S}.domain (scheme, name)
SELECT DISTINCT v.scheme, v.name FROM unnest(%s::text[], %s::text[]) AS v(scheme, name)
WHERE NOT EXISTS (SELECT 1 FROM {S}.domain d WHERE d.scheme = v.scheme AND d.name = v.name)"""

CASE_FIELDS = ("ecli", "celex", "title", "date_decision", "court_code", "lang",
               "doctype", "proc", "case_number", "importance")
_CASE_VALUES = f"""
FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[], %s::text[],
            %s::text[], %s::text[], %s::text[], %s::text[], %s::smallint[])
     AS v(ecli, celex, title, date_decision, court_code, lang, doctype, proc,
          case_number, importance)
LEFT JOIN {S}.court c ON c.code = v.court_code
LEFT JOIN {S}.document_type dt ON dt.code = v.doctype
LEFT JOIN {S}.procedure_type pt ON pt.code = v.proc"""

SQL_CASES = f"""
INSERT INTO {S}.cases (ecli, celex_id, sources, title, date_decision, court_id,
                       language_iso, document_type_id, procedure_type_id,
                       case_number, importance)
SELECT v.ecli, v.celex, ARRAY['CJEU'], v.title, v.date_decision::date, c.id,
       v.lang, dt.id, pt.id, v.case_number, v.importance
{_CASE_VALUES}
ON CONFLICT DO NOTHING"""

# Existing rows (an earlier run, or a Rechtspraak case sharing the ECLI) only
# gain what they lack. celex_id is filled only when no other case holds it.
SQL_CASES_ENRICH = f"""
UPDATE {S}.cases k SET
    celex_id = COALESCE(k.celex_id, CASE WHEN NOT EXISTS (
        SELECT 1 FROM {S}.cases o WHERE o.celex_id = v.celex) THEN v.celex END),
    sources = CASE WHEN k.sources @> ARRAY['CJEU'] THEN k.sources
                   ELSE k.sources || ARRAY['CJEU'] END,
    title = COALESCE(k.title, v.title),
    date_decision = COALESCE(k.date_decision, v.date_decision::date),
    court_id = COALESCE(k.court_id, c.id),
    language_iso = COALESCE(k.language_iso, v.lang),
    document_type_id = COALESCE(k.document_type_id, dt.id),
    procedure_type_id = COALESCE(k.procedure_type_id, pt.id),
    case_number = COALESCE(k.case_number, v.case_number),
    importance = COALESCE(k.importance, v.importance),
    updated_at = now()
{_CASE_VALUES}
WHERE k.ecli = v.ecli
  AND (k.celex_id IS NULL OR NOT k.sources @> ARRAY['CJEU'] OR k.title IS NULL
       OR k.date_decision IS NULL OR k.court_id IS NULL OR k.language_iso IS NULL
       OR k.document_type_id IS NULL OR k.procedure_type_id IS NULL
       OR k.case_number IS NULL OR k.importance IS NULL)"""

DOCUMENT_FIELDS = ("ecli", "celex", "sector", "case_number", "formation_code",
                   "proc_type", "date_lodged", "journal_refs", "erecueil_ref",
                   "local_identifier", "dossier_uri", "citations_extra_info",
                   "national_judgement_xml")
_DOCUMENT_FILL = ("sector", "case_number", "formation_id", "proc_type", "date_lodged",
                  "journal_refs", "erecueil_ref", "local_identifier", "dossier_uri",
                  "citations_extra_info", "national_judgement_xml")
SQL_DOCUMENT = f"""
INSERT INTO {S}.cjeu_document (case_id, celex_id, ecli, sector, case_number,
    formation_id, proc_type, date_lodged, journal_refs, erecueil_ref,
    local_identifier, dossier_uri, citations_extra_info, national_judgement_xml)
SELECT k.id, v.celex, v.ecli, v.sector, v.case_number, f.id, v.proc_type,
       v.date_lodged::date, v.journal_refs, v.erecueil_ref, v.local_identifier,
       v.dossier_uri, v.citations_extra_info, v.national_judgement_xml
FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[], %s::text[],
            %s::text[], %s::text[], %s::text[], %s::text[], %s::text[],
            %s::text[], %s::text[], %s::text[])
     AS v(ecli, celex, sector, case_number, formation_code, proc_type,
          date_lodged, journal_refs, erecueil_ref, local_identifier,
          dossier_uri, citations_extra_info, national_judgement_xml)
JOIN {S}.cases k ON k.ecli = v.ecli
LEFT JOIN {S}.court_formation f ON f.code = v.formation_code
ON CONFLICT (case_id) DO UPDATE SET
    {", ".join(f"{c} = COALESCE({S}.cjeu_document.{c}, EXCLUDED.{c})" for c in _DOCUMENT_FILL)}"""

AG_FIELDS = ("ecli", "ag", "opinion_uri", "parent_raw")
SQL_AG = f"""
INSERT INTO {S}.cjeu_ag_opinion (case_id, parent_case_id, advocate_general,
                                 opinion_uri, delivered_date)
SELECT k.id, p.id, v.ag, v.opinion_uri, k.date_decision
FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[])
     AS v(ecli, ag, opinion_uri, parent_raw)
JOIN {S}.cases k ON k.ecli = v.ecli
LEFT JOIN LATERAL (
    SELECT c2.id FROM {S}.cases c2
    WHERE c2.sources @> '{{CJEU}}'
      AND c2.case_number = replace((regexp_match(coalesce(v.parent_raw, ''),
          '(?:case/)([CTF]-[0-9]+%%2F[0-9]+|[CTF]-[0-9]+/[0-9]+)'))[1], '%%2F', '/')
    ORDER BY c2.id LIMIT 1
) p ON true
ON CONFLICT (case_id) DO NOTHING"""

NATIONAL_FIELDS = ("ecli", *NATIONAL_TARGETS)
SQL_NATIONAL = f"""
INSERT INTO {S}.cjeu_national_document (case_id, {", ".join(NATIONAL_TARGETS)})
SELECT k.id, {", ".join("v." + t for t in NATIONAL_TARGETS)}
FROM unnest({", ".join(["%s::text[]"] * (len(NATIONAL_TARGETS) + 1))})
     AS v(ecli, {", ".join(NATIONAL_TARGETS)})
JOIN {S}.cases k ON k.ecli = v.ecli
ON CONFLICT (case_id) DO NOTHING"""

SQL_CASE_DOMAIN = f"""
INSERT INTO {S}.case_domain (case_id, domain_id)
SELECT DISTINCT k.id, d.id
FROM unnest(%s::text[], %s::text[], %s::text[]) AS v(ecli, scheme, name)
JOIN {S}.cases k ON k.ecli = v.ecli
JOIN {S}.domain d ON d.scheme = v.scheme AND d.name = v.name
ON CONFLICT (case_id, domain_id) DO NOTHING"""

SQL_CASE_JUDGE = f"""
INSERT INTO {S}.case_judge (case_id, judge_id, role)
SELECT DISTINCT k.id, j.id, v.role
FROM unnest(%s::text[], %s::text[], %s::text[]) AS v(ecli, name, role)
JOIN {S}.cases k ON k.ecli = v.ecli
JOIN {S}.judge j ON j.full_name = v.name
ON CONFLICT (case_id, judge_id, role) DO NOTHING"""

SQL_CASE_PARTY = f"""
INSERT INTO {S}.case_party (case_id, party_id, role)
SELECT DISTINCT k.id, p.id, v.role
FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[]) AS v(ecli, name, rc, role)
JOIN {S}.cases k ON k.ecli = v.ecli
JOIN {S}.party p ON p.canonical_name = v.name AND p.role_class = v.rc
ON CONFLICT (case_id, party_id, role, ordinal) DO NOTHING"""

SQL_LAWREF = f"""
INSERT INTO {S}.case_law_reference (case_id, raw_scheme, raw_resource, role, source_dataset)
SELECT DISTINCT k.id, 'celex', v.res, v.role, 'cellar_sparql'
FROM unnest(%s::text[], %s::text[], %s::text[]) AS v(ecli, res, role)
JOIN {S}.cases k ON k.ecli = v.ecli
ON CONFLICT DO NOTHING"""

# Target resolved by CELEX; target_celex_raw is always kept, as the migration
# did. A resolved edge is skipped while its unresolved twin still exists: the
# link step below turns that row resolved instead.
SQL_CITE_OUT = f"""
INSERT INTO {S}.case_citation (source_case_id, target_case_id, target_celex_raw,
    relation_type, source_dataset, is_cross_jurisdiction)
SELECT DISTINCT k.id, t.id, v.target, v.rel, 'cellar_sparql', false
FROM unnest(%s::text[], %s::text[], %s::text[]) AS v(ecli, target, rel)
JOIN {S}.cases k ON k.ecli = v.ecli
LEFT JOIN {S}.cases t ON t.celex_id = v.target
WHERE t.id IS NULL OR NOT EXISTS (
    SELECT 1 FROM {S}.case_citation cc
    WHERE cc.source_case_id = k.id AND cc.target_case_id IS NULL
      AND cc.target_celex_raw = v.target AND cc.relation_type = v.rel
      AND cc.source_dataset = 'cellar_sparql')
ON CONFLICT DO NOTHING"""

SUMMARY_FIELDS = ("ecli", "lang", "summary", "summary_source")
SQL_SUMMARY = f"""
INSERT INTO {S}.case_text (case_id, language, summary, summary_source, source)
SELECT k.id, v.lang, v.summary, v.summary_source, 'CELLAR_ITEM'
FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[])
     AS v(ecli, lang, summary, summary_source)
JOIN {S}.cases k ON k.ecli = v.ecli
WHERE NOT EXISTS (SELECT 1 FROM {S}.case_text ct
                  WHERE ct.case_id = k.id AND ct.language = v.lang
                    AND ct.source <> 'RECHTSPRAAK')
ON CONFLICT (case_id, language, source) DO NOTHING"""

_LINK_TWIN_GUARD = f"""
   AND NOT EXISTS (SELECT 1 FROM {S}.case_citation r
                   WHERE r.source_case_id = cc.source_case_id AND r.target_case_id = t.id
                     AND r.relation_type IS NOT DISTINCT FROM cc.relation_type
                     AND r.source_dataset = cc.source_dataset)"""

SQL_LINK_CELEX = f"""
UPDATE {S}.case_citation cc
   SET target_case_id = t.id
  FROM {S}.cases t
 WHERE cc.target_case_id IS NULL
   AND cc.source_dataset = 'cellar_sparql'
   AND cc.target_celex_raw = ANY(%s::text[])
   AND t.celex_id = cc.target_celex_raw""" + _LINK_TWIN_GUARD

SQL_LINK_ECLI = f"""
UPDATE {S}.case_citation cc
   SET target_case_id = t.id,
       target_ecli_raw = NULL,
       is_cross_jurisdiction = CASE WHEN cc.source_dataset = 'echr_edge' THEN false
                                    ELSE NOT (t.sources @> '{{RS}}') END
  FROM {S}.cases t
 WHERE cc.target_case_id IS NULL
   AND (left(cc.source_dataset, 3) = 'rs_' OR cc.source_dataset = 'echr_edge')
   AND cc.target_ecli_raw = ANY(%s::text[])
   AND t.ecli = cc.target_ecli_raw""" + _LINK_TWIN_GUARD

SQL_CELEX_OWNERS = f"SELECT celex_id, ecli FROM {S}.cases WHERE celex_id = ANY(%s::text[])"


def _columns(rows, fields):
    return [[row[f] for row in rows] for f in fields]


def _tuples(rows, width):
    return [[row[i] for row in rows] for i in range(width)]


def _drop_celex(mapping, reason):
    """Keep the case but without a CELEX of its own, as the migration loaded
    ambiguous identities (court, type and case number still come from it)."""
    logging.warning("%s: %s; loading it without a CELEX", mapping.ecli, reason)
    mapping.celex = mapping.case["celex"] = mapping.document["celex"] = None


def validate(client, mappings):
    """Split mappings into loadable ones and (key, reason) failures.

    cases.celex_id is unique. A CELEX already held by another ECLI, or shared
    by several ECLIs of this batch, is ambiguous: such cases are loaded
    without a CELEX, matching how production stores them, rather than
    rejected (a rejected row blocks the month's promotion).
    """
    failures = []
    by_celex = defaultdict(list)
    for m in mappings:
        if m.celex:
            by_celex[m.celex].append(m.ecli)
    owners = dict(client.fetch_rows(SQL_CELEX_OWNERS, [sorted(by_celex)])) if by_celex else {}
    valid = []
    for m in mappings:
        if not m.ecli:
            failures.append((m.celex, "no ECLI"))
            continue
        if m.celex and not celex_well_formed(m.celex):
            failures.append((m.ecli, f"malformed CELEX {m.celex!r}"))
            continue
        if m.celex and owners.get(m.celex) not in (None, m.ecli):
            _drop_celex(m, f"CELEX {m.celex} belongs to {owners[m.celex]}")
        elif m.celex and len(by_celex[m.celex]) > 1:
            _drop_celex(m, f"CELEX {m.celex} is shared with {by_celex[m.celex]}")
        valid.append(m)
    return valid, failures


def write(client, mappings) -> dict:
    """Write validated mappings in one transaction; returns rows touched per statement."""
    counts = {}

    def run(label, sql, params, nonempty=True):
        if nonempty:
            counts[label] = client.execute_arrays(sql, params)

    new = mappings
    with client.transaction():
        langs = {m.case["lang"] for m in new if m.case["lang"]}
        langs |= {m.summary["lang"] for m in new if m.summary}
        run("language", SQL_LANGUAGE, [sorted(langs)], bool(langs))
        procs = sorted({m.case["proc"] for m in new if m.case["proc"]})
        run("procedure_type", SQL_PROCEDURE, [procs], bool(procs))
        judges = sorted({n for m in new for n, _ in m.judges})
        run("judge", SQL_JUDGE, [judges], bool(judges))
        parties = sorted({(n, rc) for m in new for n, rc, _ in m.parties})
        run("party", SQL_PARTY, _tuples(parties, 2), bool(parties))
        domains = sorted({d for m in new for d in m.domains})
        run("domain", SQL_DOMAIN, _tuples(domains, 2), bool(domains))

        cases = [m.case for m in new]
        run("cases", SQL_CASES, _columns(cases, CASE_FIELDS))
        run("cases (enriched)", SQL_CASES_ENRICH, _columns(cases, CASE_FIELDS))

        ags = [m.ag for m in new if m.ag]
        run("cjeu_ag_opinion", SQL_AG, _columns(ags, AG_FIELDS), bool(ags))
        nationals = [m.national for m in new if m.national]
        run("cjeu_national_document", SQL_NATIONAL, _columns(nationals, NATIONAL_FIELDS),
            bool(nationals))
        rows = [(m.ecli, s, n) for m in new for s, n in sorted(m.domains)]
        run("case_domain", SQL_CASE_DOMAIN, _tuples(rows, 3), bool(rows))
        rows = [(m.ecli, n, r) for m in new for n, r in sorted(m.judges)]
        run("case_judge", SQL_CASE_JUDGE, _tuples(rows, 3), bool(rows))
        rows = [(m.ecli, n, rc, r) for m in new for n, rc, r in sorted(m.parties)]
        run("case_party", SQL_CASE_PARTY, _tuples(rows, 4), bool(rows))
        rows = [(m.ecli, t, r) for m in new for t, r in sorted(m.lawrefs)]
        run("case_law_reference", SQL_LAWREF, _tuples(rows, 3), bool(rows))
        rows = [(m.ecli, t, r) for m in new for t, r in sorted(m.citations)]
        run("case_citation", SQL_CITE_OUT, _tuples(rows, 3), bool(rows))
        summaries = [m.summary for m in new if m.summary]
        run("case_text (summary)", SQL_SUMMARY, _columns(summaries, SUMMARY_FIELDS),
            bool(summaries))
        celexes = sorted({m.celex for m in new if m.celex})
        run("case_citation link (celex)", SQL_LINK_CELEX, [celexes], bool(celexes))
        run("case_citation link (ecli)", SQL_LINK_ECLI, [sorted({m.ecli for m in new})])
        # Last, so a case's cjeu_document marks it complete.
        run("cjeu_document", SQL_DOCUMENT, _columns([m.document for m in new], DOCUMENT_FIELDS))
    return counts


def load_rows(client, rows, log_failure) -> int:
    """Map, validate and write processed CELLAR rows; returns cases loaded.

    A failing batch is retried case by case, so one bad row is reported
    through ``log_failure(key, error)`` without discarding the rest.
    """
    mappings = [map_row(extractor_row(row)) for row in rows]
    valid, failures = validate(client, mappings)
    for key, reason in failures:
        log_failure(key, reason)
    if not valid:
        return 0
    try:
        counts = write(client, valid)
        logging.info("CJEU batch of %s cases: %s", len(valid), counts)
        return len(valid)
    except Exception:
        logging.exception("CJEU batch of %s cases failed; retrying case by case", len(valid))
    loaded = 0
    for mapping in valid:
        try:
            write(client, [mapping])
            loaded += 1
        except Exception as exc:
            log_failure(mapping.ecli, exc)
    return loaded
