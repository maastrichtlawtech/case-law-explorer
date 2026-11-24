"""
Resolve Cellar's procedural relations whose targets are raw URIs (R2.5).

The CJEU loader stores Cellar's relation columns as case_citation rows
(source_dataset 'cellar_sparql') with the target token in target_celex_raw,
joined to cases only on an exact CELEX (cjeu_loader.py SQL_CITE_OUT). Three
relation types carry targets that never match that way: a Cellar resource
URI (".../resource/cellar/<uuid>", the dossier of the other case), sometimes
an encoded case URI, a suffixed CELEX or a case number:

    subject_to_appeal                General Court / Civil Service Tribunal
                                     decision -> dossier of the appeal
    referred_for_preliminary_ruling  national decision (Cellar sector 8)
                                     -> the CJEU ruling (dossier or work)
    reexamined_by                    General Court appeal decision
                                     -> the review (RX) decision

This module writes NEW rows (the old ones are never touched), source_dataset
'cellar_relation_resolved':

    subject_to_appeal               -> appeal_of, REVERSED: source = the appeal
                                       decision, target = the decision under
                                       appeal (the old row's source). "A is the
                                       appeal of B"; the appeal court's decision
                                       points at the decision it reviews, like
                                       a citation.
    referred_for_preliminary_ruling -> preliminary_reference when the national
                                       decision is dated on or before the
                                       ruling, national_follow_up when after
                                       (Cellar files both under this relation:
                                       in the research rows most sector-8
                                       decisions postdate the ruling, e.g.
                                       82018AT0228(51) -> C-498/16 of
                                       2018-01-25); same direction (national
                                       decision -> CJEU ruling), as in
                                       cellar_referrals. Without both dates,
                                       or when the ruling is not in the
                                       database, the row is skipped.
    reexamined_by                   -> reexamined_by, same direction
                                       (reviewed decision -> review decision).

Resolving a target:

  * URL-decode; a Cellar URI or bare UUID -> the UUID (manifestation suffix
    '.0001' dropped) -> the dossier identifier ('C-288/21 P', 'case:T-1/12')
    from the UUID map, or a CELEX from the UUID -> CELEX map;
  * an ECLI or a CELEX (suffixes such as '_INF' or '(01)' dropped) -> the case
    with it;
  * a case number with its procedure suffix ('C-288/21 P', 'C-278/13 P(R)',
    'T-401/11 P-RENV-RX') -> case_identifier 'cjeu_case_number' candidates.
    The suffix decides which document is meant: for appeal_of it must be
    exactly 'P' (an appeal from the General Court goes to the Court of
    Justice, from the Civil Service Tribunal to the General Court, which is
    checked too); for preliminary_reference none or 'PPU'; for reexamined_by
    'RX...'. Candidates whose stored case number carries another suffix are
    left out. Any other suffix (P(R) interim orders, P-OST, P-DEP, REV, RENV,
    INTP) is resolved only to a candidate carrying exactly that suffix,
    otherwise skipped. Among the remaining candidates resolver.choose_cjeu
    takes the judgment (earliest of several, with lower confidence), else
    the only order (several orders and no judgment: skipped), never one
    dated before the old row's source.
  * A target must be a judgment or an order: an opinion (CC), the published
    request for a ruling (CN) and other CELEX types are skipped.
  * A target that resolves to no case: reexamined_by rows are written
    unresolved (target CELEX, or target_ref_raw = the case number) for late
    binding; appeal_of needs its source and preliminary_reference needs the
    ruling's date, so those are skipped and counted.

UUID maps. The research snapshot (cjeu-migration
migration/verify/research-2026-11-24/cjeu/uuid_dossier.json, uuid_map.json)
has the format {"<cellar URI>": ["<value>", ...]}. extract() takes the maps
as input and never calls Cellar. The weekly DAG keeps a cache file
(e.g. data/cellar/uuid_dossier.json next to the other Cellar state) and, as a
separate task before extraction, calls refresh_uuid_cache(), which lists the
UUIDs of unresolved rows missing from the cache, asks Cellar's public SPARQL
endpoint for cdm:dossier_identifier (and cdm:resource_legal_id_celex) in
batches of 100, and merges the answers into the file. It runs only when
called explicitly (CLI --refresh-uuid-cache); tests never call it.

Identifiers. With identifiers_out, every dossier UUID that resolved is also
written as a case_identifier candidate (scheme 'cellar_dossier_uuid', on the
decision it resolved to) in JSONL, for the identifier loader to insert.

CLI:
    python -m data_extraction.linking.cellar_relations --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH \
        [--uuid-dossier FILE] [--uuid-celex FILE] [--identifiers-out FILE]
    python -m data_extraction.linking.cellar_relations --dsn-env VAR \
        --refresh-uuid-cache --uuid-dossier FILE [--uuid-celex FILE]
"""

import argparse
import json
import logging
import os
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import unquote

from data_extraction.linking import identifiers, resolver
from data_extraction.linking.artifact import CaseKey, LinkRecord, Mention, write_jsonl

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
SOURCE_DATASET = "cellar_relation_resolved"
EXTRACTOR_VERSION = "cellar_relations/1.0.0"
OLD_DATASET = "cellar_sparql"
BATCH_SIZE = 500
CELLAR_SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"

APPEAL_OF, PRELIMINARY_REFERENCE, NATIONAL_FOLLOW_UP, REEXAMINED_BY = (
    "appeal_of",
    "preliminary_reference",
    "national_follow_up",
    "reexamined_by",
)
# old relation type -> (new relation type, reversed?)
RELATIONS = {
    "subject_to_appeal": (APPEAL_OF, True),
    "referred_for_preliminary_ruling": (PRELIMINARY_REFERENCE, False),
    "reexamined_by": (REEXAMINED_BY, False),
}

# ---------------------------------------------------------------------------
# references
# ---------------------------------------------------------------------------

_ECLI_IN_RE = re.compile(r"ECLI:[A-Z]{2}:[A-Z0-9.]{1,7}:\d{4}:[A-Z0-9.]{1,25}", re.I)
_DOSSIER_RE = re.compile(
    r"^(?:case:)?\s*(?:(?P<court>[CTF])\s*-\s*)?(?P<number>\d{1,4})\s*/\s*(?P<year>\d{2})"
    r"(?P<suffix>(?:\s|-|\().*)?$",
    re.I,
)
_CASE_PREFIX_RE = re.compile(r"^(?:https?://[^ ]*/resource/case/|case:)", re.I)
_CELEX_PREFIX_RE = re.compile(r"^(?:https?://[^ ]*/resource/celex/|celex:)", re.I)


@dataclass(frozen=True)
class Reference:
    """A parsed target token."""

    kind: str  # uuid | ecli | celex | case_number | unknown
    value: Optional[str]  # uuid, normalised ECLI/CELEX/case number
    suffix: str = ""  # procedure suffix of a case number, upper case
    court: str = ""  # court letter of a case number


def parse_dossier(text) -> Optional[Reference]:
    """'C-288/21 P' -> Reference('case_number', 'C-288/21', 'P', 'C');
    'case:T-1/12' -> ('case_number', 'T-1/12', '', 'T')."""
    if not text:
        return None
    cleaned = unicodedata.normalize("NFKC", str(text))
    cleaned = re.sub("[" + re.escape(identifiers.HYPHENS) + "]", "-", cleaned).strip()
    match = _DOSSIER_RE.match(cleaned)
    if not match:
        return None
    court = (match.group("court") or "").upper()
    number = identifiers.normalize_cjeu_case_number(
        f"{court}-{int(match.group('number'))}/{match.group('year')}"
        if court
        else f"{int(match.group('number'))}/{match.group('year')}"
    )
    suffix = re.sub(r"\s+", " ", (match.group("suffix") or "").strip(" -")).upper()
    return Reference("case_number", number, suffix, court)


def parse_reference(raw) -> Reference:
    if raw is None:
        return Reference("unknown", None)
    text = str(raw).strip()
    for _ in range(2):  # Cellar sometimes double-encodes
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    if "/resource/cellar/" in text.lower() or re.fullmatch(r"(?:cellar:)?[0-9a-fA-F-]{36}", text):
        uuid = identifiers.normalize_cellar_uuid(text)
        if uuid:
            return Reference("uuid", uuid)
    ecli = _ECLI_IN_RE.search(text)
    if ecli:
        return Reference("ecli", identifiers.normalize_ecli(ecli.group(0)))
    stripped = _CELEX_PREFIX_RE.sub("", text)
    celex = identifiers.normalize_celex(stripped)
    if celex and re.match(r"^[0-9CE]\d{4}[A-Z]{1,2}\d{4}", stripped.upper()):
        return Reference("celex", celex)
    dossier = parse_dossier(_CASE_PREFIX_RE.sub("", text))
    if dossier:
        return dossier
    return Reference("unknown", None)


def load_uuid_map(path) -> Dict[str, List[str]]:
    """{"<uri or uuid>": ["value", ...]} -> {uuid: [value, ...]}."""
    if not path:
        return {}
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    out: Dict[str, List[str]] = {}
    for key, values in raw.items():
        uuid = identifiers.normalize_cellar_uuid(key)
        if not uuid:
            continue
        if isinstance(values, str):
            values = [values]
        bucket = out.setdefault(uuid, [])
        for value in values or ():
            if value and value not in bucket:
                bucket.append(value)
    return out


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Document:
    case_id: Optional[int]
    ecli: Optional[str]
    celex: Optional[str]
    item_id: Optional[str]
    decided: Optional[date]

    def key(self):
        if self.ecli:
            return CaseKey(ecli=self.ecli)
        if self.celex:
            return CaseKey(celex=self.celex)
        if self.item_id:
            return CaseKey(item_id=self.item_id)
        return None


@dataclass(frozen=True)
class CellarRow:
    citation_id: int
    relation_type: str
    raw_target: Optional[str]
    source: Document
    target: Optional[Document] = None  # set when the old row is resolved


@dataclass(frozen=True)
class Lookups:
    """Everything resolution needs, fetched in bulk per batch."""

    uuid_dossier: Mapping[str, Sequence[str]]
    uuid_celex: Mapping[str, Sequence[str]]
    by_celex: Mapping[str, Document]
    by_ecli: Mapping[str, Document]
    by_case_number: Mapping[str, Sequence[resolver.Candidate]]


@dataclass(frozen=True)
class Resolved:
    target: Optional[Document]  # None: unresolved, see ref
    ref: Optional[Reference]
    method: str
    confidence: float
    rule: str
    dossier_uuid: Optional[str] = None
    relation: Optional[str] = None  # overrides the relation of RELATIONS


def _suffix_of(value) -> Optional[str]:
    parsed = parse_dossier(value)
    return parsed.suffix if parsed else None


def _main_suffix(relation, suffix):
    if relation == APPEAL_OF:
        return suffix == "P"
    if relation == PRELIMINARY_REFERENCE:
        return suffix in ("", "PPU")
    return suffix.startswith("RX")


def _expected_court(source: Document) -> Optional[str]:
    """Which court hears an appeal from the source decision."""
    celex = identifiers.normalize_celex(source.celex) or ""
    if celex.startswith("6") and len(celex) >= 7:
        return {"T": "C", "F": "T"}.get(celex[5])
    if source.ecli:
        court = source.ecli.split(":")[2] if source.ecli.count(":") >= 3 else ""
        return {"T": "C", "F": "T"}.get(court)
    return None


def _not_before(candidate_date, source: Document):
    return candidate_date is None or source.decided is None or candidate_date >= source.decided


def _resolve_case_number(
    ref: Reference, relation: str, source: Document, lookups: Lookups
) -> Tuple[Optional[Resolved], str]:
    if relation == APPEAL_OF:
        if not ref.suffix.startswith("P"):
            return None, "appeal_without_p_suffix"
        expected = _expected_court(source)
        if expected is None or ref.court != expected:
            return None, "appeal_court_mismatch"
    main = _main_suffix(relation, ref.suffix)
    pool = []
    for candidate in lookups.by_case_number.get(ref.value, ()):
        stored = _suffix_of(candidate.value)
        if stored == ref.suffix or (main and stored == ""):
            if candidate.case_id != source.case_id and (
                relation == PRELIMINARY_REFERENCE or _not_before(candidate.date, source)
            ):
                pool.append(candidate)
    choice = resolver.choose_cjeu(pool, None)
    if choice is None:
        if lookups.by_case_number.get(ref.value):
            return None, "no_candidate_after_source" if main else "no_candidate_with_suffix"
        if main and relation != APPEAL_OF:
            # Not loaded (yet): written unresolved for late binding.
            return Resolved(None, ref, "case_number", 0.9, "case_number_unresolved"), "unresolved"
        return None, "no_case_with_case_number"
    if choice.candidate.kind == resolver.CJEU_ORDER and choice.rule.endswith("_of_several"):
        # Several orders and no judgment: the earliest is as likely a procedural
        # order (intervention, costs) as the one that disposed of the case.
        return None, "several_orders"
    c = choice.candidate
    target = Document(c.case_id, c.ecli, c.celex, c.item_id, c.date)
    return Resolved(target, ref, "case_number", choice.confidence, choice.rule), "ok"


def _is_decision(celex):
    """A judgment or an order (not an opinion, a published request 'CN',
    a summary...); True when the CELEX is unknown (the target was named by
    ECLI only)."""
    if not celex:
        return True
    return resolver.cjeu_kind(celex) in (resolver.CJEU_JUDGMENT, resolver.CJEU_ORDER)


def _resolve_document(doc, ref, method, confidence, rule, relation, source):
    named = doc.celex if doc is not None else (ref.value if ref and ref.kind == "celex" else None)
    if not _is_decision(named):
        return None, "target_not_a_decision"
    if doc is None:
        if relation == APPEAL_OF:
            return None, "target_not_in_database"
        return Resolved(None, ref, method, confidence, rule + "_unresolved"), "unresolved"
    if doc.case_id == source.case_id:
        return None, "self_link"
    if relation != PRELIMINARY_REFERENCE and not _not_before(doc.decided, source):
        return None, "dated_before_source"
    return Resolved(doc, ref, method, confidence, rule), "ok"


def resolve_row(row: CellarRow, lookups: Lookups) -> Tuple[Optional[Resolved], str]:
    """Resolve the old row's target; returns (Resolved, 'ok'|'unresolved')
    or (None, reason)."""
    resolved, reason = _resolve_target(row, lookups)
    if resolved is None or RELATIONS[row.relation_type][0] != PRELIMINARY_REFERENCE:
        return resolved, reason
    # Cellar files national decisions taken after the ruling under the same
    # relation; only the dates tell a referral from a follow-up.
    if resolved.target is None:
        return None, "ruling_not_in_database"
    national, ruling = row.source.decided, resolved.target.decided
    if national is None or ruling is None:
        return None, "no_dates"
    if national <= ruling:
        return replace(resolved, relation=PRELIMINARY_REFERENCE), "ok"
    return replace(resolved, relation=NATIONAL_FOLLOW_UP), "ok"


def _resolve_target(row: CellarRow, lookups: Lookups) -> Tuple[Optional[Resolved], str]:
    relation, _reverse = RELATIONS[row.relation_type]
    if row.target is not None:
        return _resolve_document(
            row.target, None, "celex", 0.98, "already_resolved", relation, row.source
        )
    ref = parse_reference(row.raw_target)
    if ref.kind == "uuid":
        dossiers = {
            (p.value, p.suffix, p.court)
            for p in (parse_dossier(v) for v in lookups.uuid_dossier.get(ref.value, ()))
            if p is not None
        }
        celexes = {
            identifiers.normalize_celex(v) for v in lookups.uuid_celex.get(ref.value, ())
        } - {None}
        if len(dossiers) > 1 or len(celexes) > 1:
            return None, "uuid_ambiguous"
        if dossiers:
            value, suffix, court = dossiers.pop()
            resolved, reason = _resolve_case_number(
                Reference("case_number", value, suffix, court), relation, row.source, lookups
            )
            if resolved is not None:
                resolved = replace(
                    resolved, rule="uuid_dossier_" + resolved.rule, dossier_uuid=ref.value
                )
            return resolved, reason
        if celexes:
            celex = celexes.pop()
            return _resolve_document(
                lookups.by_celex.get(celex),
                Reference("celex", celex),
                "celex",
                0.95,
                "uuid_celex",
                relation,
                row.source,
            )
        return None, "uuid_unmapped"
    if ref.kind == "ecli":
        return _resolve_document(
            lookups.by_ecli.get(ref.value), ref, "ecli", 0.98, "ecli", relation, row.source
        )
    if ref.kind == "celex":
        return _resolve_document(
            lookups.by_celex.get(ref.value), ref, "celex", 0.95, "celex", relation, row.source
        )
    if ref.kind == "case_number":
        return _resolve_case_number(ref, relation, row.source, lookups)
    return None, "unparsed_target"


def record_for(row: CellarRow, resolved: Resolved) -> Optional[LinkRecord]:
    relation, reverse = RELATIONS[row.relation_type]
    relation = resolved.relation or relation
    source_key = row.source.key()
    if resolved.target is not None:
        target_key = resolved.target.key()
        target_ref_raw = target_ref_scheme = None
    elif resolved.ref is not None and resolved.ref.kind in ("celex", "ecli"):
        target_key = CaseKey(**{resolved.ref.kind: resolved.ref.value})
        target_ref_raw = target_ref_scheme = None
    elif resolved.ref is not None and resolved.ref.kind == "case_number":
        target_key = None
        target_ref_raw, target_ref_scheme = resolved.ref.value, "cjeu_case_number"
    else:
        return None
    if reverse:
        if target_key is None:
            return None
        source_key, target_key = target_key, source_key
    if source_key is None or (target_key is None and target_ref_raw is None):
        return None
    if target_key is not None and target_key == source_key:
        return None
    return LinkRecord(
        source=source_key,
        target=target_key,
        target_ref_raw=target_ref_raw,
        target_ref_scheme=target_ref_scheme,
        relation_type=relation,
        source_dataset=SOURCE_DATASET,
        extractor_version=EXTRACTOR_VERSION,
        match_method=resolved.method,
        confidence=round(resolved.confidence, 2),
        mentions=(
            (
                Mention(
                    text_field="metadata",
                    raw_text=row.raw_target or "",
                    context=f"{OLD_DATASET} {row.relation_type}",
                ),
            )
            if row.raw_target
            else ()
        ),
    )


def links_for_rows(
    rows: Iterable[CellarRow], lookups: Lookups, stats: Optional[Counter] = None
) -> Tuple[List[LinkRecord], List[dict]]:
    """(records, case_identifier rows for resolved dossier UUIDs)."""
    stats = stats if stats is not None else Counter()
    merged: Dict[tuple, LinkRecord] = {}
    idents: Dict[tuple, dict] = {}
    for row in rows:
        stats[f"rows_{row.relation_type}"] += 1
        resolved, reason = resolve_row(row, lookups)
        if resolved is None:
            stats[f"{row.relation_type}:{reason}"] += 1
            continue
        record = record_for(row, resolved)
        if record is None:
            stats[f"{row.relation_type}:no_natural_key"] += 1
            continue
        stats[f"{record.relation_type}:{resolved.rule}"] += 1
        key = (
            json.dumps(record.source.to_dict(), sort_keys=True),
            json.dumps(record.target.to_dict() if record.target else None, sort_keys=True),
            record.target_ref_raw,
            record.relation_type,
        )
        if key in merged:
            old = merged[key]
            mentions = old.mentions + tuple(m for m in record.mentions if m not in old.mentions)
            best = record if (record.confidence or 0) > (old.confidence or 0) else old
            merged[key] = replace(best, mentions=mentions)
        else:
            merged[key] = record
        if resolved.dossier_uuid and resolved.target is not None and resolved.target.key():
            ident_key = (resolved.dossier_uuid, json.dumps(resolved.target.key().to_dict()))
            idents[ident_key] = {
                "case": resolved.target.key().to_dict(),
                "scheme": "cellar_dossier_uuid",
                "value": row.raw_target,
                "value_normalized": resolved.dossier_uuid,
                "source": "cellar_sparql.dossier_identifier",
            }
    return list(merged.values()), [idents[k] for k in sorted(idents)]


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------

_ROWS = f"""
    SELECT cc.source_case_id, cc.id, cc.relation_type,
           coalesce(cc.target_celex_raw, cc.target_ecli_raw),
           s.ecli, s.celex_id, s.item_id, s.date_decision,
           t.id, t.ecli, t.celex_id, t.item_id, t.date_decision
      FROM {SCHEMA}.case_citation cc
      JOIN {SCHEMA}.cases s ON s.id = cc.source_case_id
      LEFT JOIN {SCHEMA}.cases t ON t.id = cc.target_case_id
     WHERE cc.source_dataset = '{OLD_DATASET}'
       AND cc.relation_type = ANY(%(types)s)
       AND (cc.source_case_id, cc.id) > (%(after_case)s, %(after_id)s)
       AND (%(from_id)s::bigint IS NULL OR cc.source_case_id >= %(from_id)s)
       AND (%(to_id)s::bigint IS NULL OR cc.source_case_id <= %(to_id)s)
       AND (%(case_ids)s::bigint[] IS NULL OR cc.source_case_id = ANY(%(case_ids)s))
     ORDER BY cc.source_case_id, cc.id
     LIMIT %(limit)s
"""
_DOCS_BY = f"""
    SELECT id, ecli, celex_id, item_id, date_decision FROM {SCHEMA}.cases
     WHERE celex_id = ANY(%s) OR ecli = ANY(%s)
"""


def iter_rows(conn, case_ids=None, id_range=None, batch_size=BATCH_SIZE):
    from_id, to_id = id_range if id_range else (None, None)
    after = (0, 0)
    while True:
        with conn.cursor() as cursor:
            cursor.execute(
                _ROWS,
                {
                    "types": sorted(RELATIONS),
                    "after_case": after[0],
                    "after_id": after[1],
                    "from_id": from_id,
                    "to_id": to_id,
                    "case_ids": list(case_ids) if case_ids is not None else None,
                    "limit": batch_size,
                },
            )
            rows = cursor.fetchall()
        if not rows:
            return
        after = (rows[-1][0], rows[-1][1])
        batch = []
        for (
            source_id,
            citation_id,
            relation_type,
            raw,
            s_ecli,
            s_celex,
            s_item,
            s_date,
            t_id,
            t_ecli,
            t_celex,
            t_item,
            t_date,
        ) in rows:
            target = Document(t_id, t_ecli, t_celex, t_item, t_date) if t_id else None
            batch.append(
                CellarRow(
                    citation_id,
                    relation_type,
                    raw,
                    Document(source_id, s_ecli, s_celex, s_item, s_date),
                    target,
                )
            )
        yield batch


def build_lookups(cursor, rows: Sequence[CellarRow], uuid_dossier, uuid_celex) -> Lookups:
    numbers, celexes, eclis = set(), set(), set()
    for row in rows:
        if row.target is not None:
            continue
        ref = parse_reference(row.raw_target)
        if ref.kind == "uuid":
            for value in uuid_dossier.get(ref.value, ()):
                parsed = parse_dossier(value)
                if parsed:
                    numbers.add(parsed.value)
            for value in uuid_celex.get(ref.value, ()):
                celex = identifiers.normalize_celex(value)
                if celex:
                    celexes.add(celex)
        elif ref.kind == "case_number":
            numbers.add(ref.value)
        elif ref.kind == "celex":
            celexes.add(ref.value)
        elif ref.kind == "ecli":
            eclis.add(ref.value)
    by_celex, by_ecli = {}, {}
    if celexes or eclis:
        cursor.execute(_DOCS_BY, (sorted(celexes), sorted(eclis)))
        for case_id, ecli, celex, item_id, decided in cursor.fetchall():
            doc = Document(case_id, ecli, celex, item_id, decided)
            if celex in celexes:
                by_celex[celex] = doc
            if ecli in eclis:
                by_ecli[ecli] = doc
    by_number = resolver.fetch_candidates(cursor, "cjeu_case_number", sorted(numbers))
    return Lookups(uuid_dossier, uuid_celex, by_celex, by_ecli, by_number)


def extract(
    conn,
    case_ids=None,
    id_range=None,
    out_path=None,
    uuid_dossier: Optional[Mapping[str, Sequence[str]]] = None,
    uuid_celex: Optional[Mapping[str, Sequence[str]]] = None,
    identifiers_out=None,
    batch_size: int = BATCH_SIZE,
):
    """Write the artifact for the cellar_sparql rows whose source case is
    selected by case_ids or id_range (cases.id, inclusive). uuid_dossier /
    uuid_celex map UUID -> values (load_uuid_map); returns (records, stats)."""
    uuid_dossier = uuid_dossier or {}
    uuid_celex = uuid_celex or {}
    stats: Counter = Counter()
    records: List[LinkRecord] = []
    idents: List[dict] = []
    for batch in iter_rows(conn, case_ids, id_range, batch_size):
        with conn.cursor() as cursor:
            lookups = build_lookups(cursor, batch, uuid_dossier, uuid_celex)
        batch_records, batch_idents = links_for_rows(batch, lookups, stats)
        records.extend(batch_records)
        idents.extend(batch_idents)
    written = write_jsonl(records, out_path) if out_path else len(records)
    if identifiers_out:
        lines = sorted({json.dumps(i, sort_keys=True, ensure_ascii=False) for i in idents})
        with open(identifiers_out, "w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    stats["records"] = written
    stats["dossier_identifiers"] = len({(i["value_normalized"], str(i["case"])) for i in idents})
    log.info("cellar_relations: %s", dict(sorted(stats.items())))
    return written, stats


# ---------------------------------------------------------------------------
# cache refresh (network; never called by extract or by the tests)
# ---------------------------------------------------------------------------

SPARQL_PREDICATES = {
    "dossier": "cdm:dossier_identifier",
    "celex": "cdm:resource_legal_id_celex",
}


def fetch_uuid_values(
    uris: Sequence[str],
    predicate: str = "dossier",
    endpoint: str = CELLAR_SPARQL,
    batch_size: int = 100,
    pause: float = 0.3,
    urlopen=None,
) -> Dict[str, List[str]]:
    """Ask Cellar's SPARQL endpoint for one predicate of each URI.
    {uri: [value, ...]}; URIs Cellar has no value for are absent. Network:
    only for the weekly cache refresh, never in extraction or tests (pass
    urlopen to test it offline)."""
    from urllib.parse import urlencode
    from urllib.request import Request
    from urllib.request import urlopen as default_urlopen

    urlopen = urlopen or default_urlopen
    prop = SPARQL_PREDICATES[predicate]
    out: Dict[str, List[str]] = {}
    uris = sorted(set(uris))
    for start in range(0, len(uris), batch_size):
        stop = start + batch_size
        chunk = uris[start:stop]
        values = " ".join(f"<{u}>" for u in chunk)
        query = (
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
            f"SELECT ?w ?v WHERE {{ VALUES ?w {{ {values} }} ?w {prop} ?v }}"
        )
        request = Request(
            endpoint,
            data=urlencode({"query": query}).encode(),
            headers={"Accept": "application/sparql-results+json"},
        )
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
        for binding in result.get("results", {}).get("bindings", []):
            uri, value = binding["w"]["value"], binding["v"]["value"]
            bucket = out.setdefault(uri, [])
            if value not in bucket:
                bucket.append(value)
        if pause and start + batch_size < len(uris):
            time.sleep(pause)
    return out


_UNMAPPED_URIS = f"""
    SELECT DISTINCT coalesce(cc.target_celex_raw, cc.target_ecli_raw)
      FROM {SCHEMA}.case_citation cc
     WHERE cc.source_dataset = '{OLD_DATASET}'
       AND cc.relation_type = ANY(%s)
       AND cc.target_case_id IS NULL
"""


def refresh_uuid_cache(conn, cache_path, predicate="dossier", urlopen=None) -> int:
    """Fetch the values of the UUIDs of unresolved rows that the cache file
    lacks and merge them into it; returns how many URIs were added. The
    weekly DAG's step before extract(); network."""
    cache = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as handle:
            cache = json.load(handle)
    known = {identifiers.normalize_cellar_uuid(k) for k in cache}
    with conn.cursor() as cursor:
        cursor.execute(_UNMAPPED_URIS, (sorted(RELATIONS),))
        raws = [r[0] for r in cursor.fetchall()]
    missing = {}
    for raw in raws:
        ref = parse_reference(raw)
        if ref.kind == "uuid" and ref.value not in known:
            missing[ref.value] = f"http://publications.europa.eu/resource/cellar/{ref.value}"
    fetched = fetch_uuid_values(sorted(missing.values()), predicate, urlopen=urlopen)
    cache.update(fetched)
    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(dict(sorted(cache.items())), handle, ensure_ascii=False, indent=0)
    return len(fetched)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("--from-id", type=int)
    parser.add_argument("--to-id", type=int)
    parser.add_argument("--out")
    parser.add_argument("--uuid-dossier", help="JSON {cellar URI: [dossier identifier]}")
    parser.add_argument("--uuid-celex", help="JSON {cellar URI: [CELEX]}")
    parser.add_argument("--identifiers-out", help="JSONL of cellar_dossier_uuid identifiers")
    parser.add_argument(
        "--refresh-uuid-cache",
        action="store_true",
        help="query Cellar SPARQL for uncached UUIDs and update the map files (network)",
    )
    args = parser.parse_args(argv)
    import psycopg2

    logging.basicConfig(level=logging.INFO)
    conn = psycopg2.connect(os.environ[args.dsn_env])
    try:
        conn.set_session(readonly=True)
        if args.refresh_uuid_cache:
            if not args.uuid_dossier:
                parser.error("--refresh-uuid-cache needs --uuid-dossier")
            added = refresh_uuid_cache(conn, args.uuid_dossier, "dossier")
            if args.uuid_celex:
                added += refresh_uuid_cache(conn, args.uuid_celex, "celex")
            print(f"{added} URIs added to the UUID cache")
            return
        if not args.out:
            parser.error("--out is required")
        id_range = (args.from_id, args.to_id) if args.from_id or args.to_id else None
        written, stats = extract(
            conn,
            id_range=id_range,
            out_path=args.out,
            uuid_dossier=load_uuid_map(args.uuid_dossier),
            uuid_celex=load_uuid_map(args.uuid_celex),
            identifiers_out=args.identifiers_out,
        )
    finally:
        conn.close()
    print(f"{written} records -> {args.out}; {dict(sorted(stats.items()))}")


if __name__ == "__main__":
    main()
