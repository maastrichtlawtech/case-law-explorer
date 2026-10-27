"""
Maps one CELLAR metadata row to the cle_v2 rows a CJEU case consists of.

This is the mapping production's CJEU data was loaded with (cjeu-migration's
50_load_cjeu.py, carried over unchanged into 62_load_new_cjeu_cases_via_runner.py
for the October 2026 Hugging Face load). Keeping Airflow on the same mapping
means a case loaded by this DAG is indistinguishable from the ~53k loaded by
the migration: same court, document type, case number, judges, parties,
domains, AG opinion, law references and citation provenance (cellar_sparql).

Rows are keyed by cellar-extractor's own column names. The processed CSV keeps
those names (MAP_CELLAR is a selection, not a rename), except ``ecli`` which
the transformer writes as ``ECLI``; extractor_row() undoes that.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

CDM_ROLE_COLUMNS = {
    "legal_resource": "legal_basis",
    "based_on_treaty": "based_on_treaty",
    "affecting_string": "affects",
    "case_law_amends_resource_legal": "amends",
    "case_law_amends_by_correction_resource_legal": "amends_by_correction",
    "case_law_confirms_resource_legal": "confirms",
    "case_law_declares_void_resource_legal": "declares_void",
    "case_law_declares_void_by_preliminary_ruling_resource_legal": "declares_void_by_preliminary_ruling",
    "case_law_incidentally_declares_void_resource_legal": "incidentally_declares_void",
    "case_law_declares_valid_resource_legal": "declares_valid",
    "case_law_declares_incidentally_valid_resource_legal": "declares_incidentally_valid",
    "case_law_states_failure_concerning_resource_legal": "states_failure",
    "case_law_suspends_application_of_resource_legal": "suspends_application",
    "case_law_immediately_enforces_resource_legal": "immediately_enforces",
    "resource_legal_incorporates_resource_legal": "incorporates",
    "resource_legal_corrects_resource_legal": "corrects",
}

CITE_COLUMNS = {
    "citing": "cites",
    "work_cites_work": "cites",
    "cited_by": "cited_by",
    "case_law_joins_case_court": "joins",
    "case_law_subject_to_appeal_in_case_court": "subject_to_appeal",
    "case_law_reexamined_by_case_court": "reexamined_by",
    "case_law_referred_to_for_preliminary_ruling_case_law": "referred_for_preliminary_ruling",
    "case_law_is_about_concept_case_law": "is_about_concept",
    "case_law_is_about_concept_new_case_law": "is_about_concept",
    "work_is_logical_successor_of_work": "logical_successor_of",
}

# ``keywords`` is deliberately absent: the migration skipped it (it duplicates
# ``eurovoc``), and production holds no cjeu_keyword domains.
DOMAIN_COLUMNS = {
    "subject_matter": "cjeu_subject_matter",
    "eurovoc": "eurovoc",
    "directory_codes": "cjeu_directory_code",
}

NATIONAL_COLUMNS = [
    ("case_law_delivered_by_court_national", "national_court_uri"),
    ("case_law_national_decision_internal_identifier", "national_decision_internal_id"),
    ("case_law_national_parties", "national_parties_raw"),
    ("case_law_national_keywords", "national_keywords"),
    ("case_law_national_reference_publication", "national_reference_publication"),
    ("case_law_national_reference_publication_conclusion", "national_reference_publication_conclusion"),
    ("case_law_national_follow_up", "national_follow_up"),
    ("case_law_national_judgement_reference", "national_judgement_reference"),
    ("case_law_national_act_reference_national", "national_act_reference_national"),
    ("case_law_national_act_reference_international", "national_act_reference_international"),
    ("case_law_national_act_reference_european", "national_act_reference_european"),
    ("case_law_national_based_on_resource_legal", "national_based_on_resource_legal"),
]
NATIONAL_TARGETS = [target for _, target in NATIONAL_COLUMNS]

AGENT_COLUMNS = (
    ("case_law_defended_by_agent", "defendant_agent"),
    ("case_law_requested_by_agent", "applicant_agent"),
    ("commented_by_agent", "commenting_agent"),
)

LANG_NAME_TO_ISO = {
    "english": "en", "french": "fr", "german": "de", "italian": "it",
    "spanish": "es", "dutch": "nl", "polish": "pl", "greek": "el",
    "portuguese": "pt", "romanian": "ro", "bulgarian": "bg", "swedish": "sv",
    "danish": "da", "finnish": "fi", "slovak": "sk", "slovenian": "sl",
    "croatian": "hr", "estonian": "et", "latvian": "lv", "lithuanian": "lt",
    "maltese": "mt", "irish": "ga", "hungarian": "hu", "czech": "cs",
}

FORMATION_WORDS = [
    ("GC", ("grand", "grande")), ("FC", ("full court", "plén", "assembl")),
    ("1C", ("first", "première")), ("2C", ("second", "deuxième")),
    ("3C", ("third", "troisième")), ("4C", ("fourth", "quatrième")),
    ("5C", ("fifth", "cinquième")), ("6C", ("sixth", "sixième")),
    ("7C", ("seventh", "septième")), ("8C", ("eighth", "huitième")),
    ("9C", ("ninth", "neuvième")), ("10C", ("tenth", "dixième")),
]

SCALAR_COLUMNS = [
    "ecli", "celex", "date_publication", "work_title", "language_procedure",
    "judicial_procedure_type", "delivered_by_court_formation", "sector",
    "type_procedure", "date_of_request", "references_journals",
    "case_law_published_in_erecueil", "local_identifier", "work_part_of_dossier",
    "citations_extra_info", "national_judgement",
    "case_law_is_about_case_law_subject_matter", "origin_country_or_role_qualifier",
    "judge_rapporteur", "case_law_delivered_by_judge", "origin_country",
    "advocate_general", "conclusions", "opinion_advocate_general_joined_to_case_court",
    "summary", "summary_source", "infocuria_celex",
]

# Every extractor column the mapping reads. MAP_CELLAR must keep all of them,
# or drop_columns() discards them before the transformer runs.
MAPPED_COLUMNS = list(dict.fromkeys(
    SCALAR_COLUMNS + list(DOMAIN_COLUMNS) + [c for c, _ in AGENT_COLUMNS]
    + list(CITE_COLUMNS) + list(CDM_ROLE_COLUMNS) + [c for c, _ in NATIONAL_COLUMNS]
))

DECISION_KINDS = {"judgment", "order", "opinion", "ruling", "decision", "other"}

CELEX_RE = re.compile(r"^\d{5}[A-Z]{1,2}\d{4}(\(\d{2}\))?$")


def _isna(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    return str(value).strip().lower() in {"", "nan", "none", "nat"}


def toks(value):
    if _isna(value):
        return []
    return [t.strip() for t in str(value).split(";") if t.strip()]


def first(value):
    tokens = toks(value)
    return tokens[0] if tokens else None


def whole(value):
    """Full cell, not ';'-tokenized (summaries contain semicolons)."""
    if _isna(value):
        return None
    return str(value).strip() or None


def raw(value):
    """Untokenized cell, passed through as the migration stored it."""
    return None if _isna(value) else str(value)


def celex_well_formed(celex) -> bool:
    return bool(celex) and bool(CELEX_RE.match(celex))


def norm_lang(value):
    word = (first(value) or "").lower()
    return LANG_NAME_TO_ISO.get(word, word if len(word) == 2 else None)


def norm_ecli(value):
    return None if _isna(value) else str(value).strip().upper()


def celex_kind(celex):
    """(court code, document type code, is AG opinion) from a CELEX descriptor."""
    match = re.match(r"^[68]\d{4}([A-Z])([A-Z])", celex or "")
    if not match:
        return None, "other", False
    court = {"C": "CJEU", "T": "EGC", "F": "CST"}.get(match.group(1))
    doctype = {"J": "judgment", "O": "order", "C": "opinion", "V": "ruling",
               "D": "decision"}.get(match.group(2), "other")
    return court, doctype, match.group(2) == "C"


def case_number(celex):
    match = re.match(r"^[68](\d{4})([A-Z])[A-Z](\d{4})", celex or "")
    if not match:
        return None
    court = {"C": "C", "T": "T", "F": "F"}.get(match.group(2), "C")
    return f"{court}-{int(match.group(3))}/{match.group(1)[2:]}"


def formation_code(raw_formation):
    lowered = (raw_formation or "").lower()
    for code, words in FORMATION_WORDS:
        if any(word in lowered for word in words):
            return code
    return None


def importance(raw_formation):
    code = formation_code(raw_formation)
    if code in ("GC", "FC"):
        return 1
    if code in ("1C", "2C", "3C", "4C", "5C"):
        return 2
    if code:
        return 3
    return 4 if raw_formation else None


def parse_date(value):
    """ISO date string, or None when absent or unparseable."""
    if _isna(value):
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def decision_date(date_publication):
    tokens = toks(date_publication)
    return parse_date(min(tokens)) if tokens else None


def document_kind(celex):
    """case_text.document_kind for the canonical CELLAR text of ``celex``."""
    _, doctype, _ = celex_kind(celex)
    return doctype if doctype in DECISION_KINDS else "other"


@dataclass
class CaseMapping:
    ecli: str
    celex: str | None
    case: dict
    document: dict
    ag: dict | None = None
    national: dict | None = None
    domains: set = field(default_factory=set)  # (scheme, name)
    judges: set = field(default_factory=set)  # (full_name, role)
    parties: set = field(default_factory=set)  # (canonical_name, role_class, role)
    lawrefs: set = field(default_factory=set)  # (raw_resource, role)
    citations: set = field(default_factory=set)  # (target_celex, relation_type)
    summary: dict | None = None  # case_text summary row


def extractor_row(processed_row: dict) -> dict:
    """A processed CSV row in cellar-extractor's column names."""
    row = dict(processed_row)
    if "ecli" not in row and "ECLI" in row:
        row["ecli"] = row["ECLI"]
    return row


def map_row(row: dict) -> CaseMapping:
    """Map one extractor row to the rows the migration produced for it."""
    get = row.get
    ecli = norm_ecli(get("ecli"))
    celex = first(get("celex"))
    # Documents known only to InfoCuria may carry no CELEX of their own; court,
    # document type and case number then follow from the procedure's CELEX.
    descriptive_celex = celex or first(get("infocuria_celex"))
    court, doctype, is_opinion = celex_kind(descriptive_celex)
    raw_formation = first(get("delivered_by_court_formation"))
    number = case_number(descriptive_celex)
    title = first(get("work_title"))
    sector = first(get("sector"))
    mapping = CaseMapping(
        ecli=ecli,
        celex=celex,
        case={
            "ecli": ecli,
            "celex": celex,
            "title": title or (f"Case {number}" if number else None),
            "date_decision": decision_date(get("date_publication")),
            "court_code": court or "CJEU",
            "lang": norm_lang(get("language_procedure")),
            "doctype": doctype,
            "proc": first(get("judicial_procedure_type")),
            "case_number": number,
            "importance": importance(raw_formation),
        },
        document={
            "ecli": ecli,
            "celex": celex,
            "sector": sector,
            "case_number": number,
            "formation_code": formation_code(raw_formation),
            "proc_type": first(get("type_procedure")),
            "date_lodged": parse_date(first(get("date_of_request"))),
            "journal_refs": first(get("references_journals")),
            "erecueil_ref": first(get("case_law_published_in_erecueil")),
            "local_identifier": first(get("local_identifier")),
            "dossier_uri": first(get("work_part_of_dossier")),
            "citations_extra_info": raw(get("citations_extra_info")),
            "national_judgement_xml": raw(get("national_judgement")),
        },
    )
    if is_opinion:
        mapping.ag = {
            "ecli": ecli,
            "ag": first(get("advocate_general")),
            "opinion_uri": first(get("conclusions")),
            "parent_raw": first(get("opinion_advocate_general_joined_to_case_court")),
        }
    summary = whole(get("summary"))
    if summary:
        mapping.summary = {
            "ecli": ecli,
            "lang": norm_lang(get("language_procedure")) or "en",
            "summary": summary,
            "summary_source": first(get("summary_source")),
        }
    if sector == "8":
        national = {target: first(get(column)) for column, target in NATIONAL_COLUMNS}
        if any(value is not None for value in national.values()):
            mapping.national = {"ecli": ecli, **national}

    for token in toks(get("case_law_is_about_case_law_subject_matter")):
        mapping.domains.add(("cjeu_is_about_subject", token))
    for column, scheme in DOMAIN_COLUMNS.items():
        for token in toks(get(column)):
            mapping.domains.add((scheme, token))

    rapporteur = first(get("judge_rapporteur"))
    if rapporteur:
        mapping.judges.add((rapporteur, "rapporteur"))
    for judge in toks(get("case_law_delivered_by_judge")):
        mapping.judges.add((judge, "judge"))

    # Agents and the referring state, as the migration represented them.
    for column, role in AGENT_COLUMNS:
        for party in toks(get(column)):
            mapping.parties.add((party, "agent", role))
    origin = first(get("origin_country"))
    if origin:
        mapping.parties.add((origin, "agent", "referring_state"))
    for token in toks(get("origin_country_or_role_qualifier")):
        mapping.parties.add((token, "state", "referring_state"))

    for column, relation in CITE_COLUMNS.items():
        for token in toks(get(column)):
            mapping.citations.add((token, relation))
    for column, role in CDM_ROLE_COLUMNS.items():
        for token in toks(get(column)):
            mapping.lawrefs.add((token, role))
    return mapping
