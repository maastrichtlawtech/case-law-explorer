"""
Case status (roadmap R5.2): struck out, referred to the Grand Chamber, final,
overturned on appeal. Only where the data says so; nothing is inferred from
the absence of data (a Chamber judgment with no Grand Chamber judgment is not
marked final: the database cannot tell a refused referral request from one
that was never made).

Three extractors, each run for a batch of "trigger" cases (the weekly batch,
or a cases.id range in the backfill). A trigger can give a status to an older
case outside the batch: a new Grand Chamber judgment marks the Chamber
judgment it reviewed, a new appeal marks the decision under appeal.

ECtHR, source_dataset 'echr_status' (extract_echr), from echr_document:

    struck_out                 a judgment or decision whose HUDOC conclusion
                               has an item "Struck out of the list"; date = the
                               judgment date. E.g. M.E. v. Sweden (71398/12),
                               struck out by the Grand Chamber on 8 April 2015.
    final                      on delivery, by the Convention: a Grand Chamber
                               judgment (art. 44(1)), a Committee judgment
                               (art. 28(2)), a decision declaring the
                               application inadmissible (overall outcome
                               'inadmissible'); date = the judgment date.
    referred_to_grand_chamber  a Chamber judgment followed by a Grand Chamber
                               judgment in the same application (owner
                               application number, echr_document_appno
                               source 'appno', never extractedappno), dated
                               after it; related = the Grand Chamber judgment;
                               status_date NULL (the referral date is not in
                               the data). E.g. M.E. v. Sweden, Chamber judgment
                               ECLI:CE:ECHR:2014:0626JUD007139812.

    Grand Chamber / Chamber / Committee from echr_document.doctype_branch
    (letters only, upper case: GRANDCHAMBER, CHAMBER, COMMITTEE), a docname
    with "[GC]" / "(GC)" also counting as Grand Chamber. The branch values
    are HUDOC's; check them on db-dev before switching the flag on.

CJEU, source_dataset 'cjeu_appeal_status' (extract_cjeu):

    overturned   the decision under appeal, when an appeal decision is linked
                 to it by a resolved case_citation row (appeal_of: appeal ->
                 decision under appeal, Phase 2 cellar_relation_resolved; or
                 Cellar's subject_to_appeal: decision under appeal -> appeal)
                 and the appeal's type_procedure is "Appeal - successful";
                 related = the appeal, date = its decision date, raw_value the
                 appeal's type_procedure. Cellar labels an appeal successful
                 when the judgment under appeal is set aside, also in part.

Rechtspraak, source_dataset 'rs_appeal_status' (extract_rs), only with
RS_DICTUM_ENABLED (it needs the dictum, see rs_dictum.py):

    overturned   the earlier of two RS decisions joined by a resolved formal
                 relation 'hogerberoep' or 'cassatie' (either direction; the
                 later decision, strictly later by date, is taken as the
                 appeal), when the appeal's dictum reads "quashed" and the
                 appeal has exactly one such earlier decision (several: not
                 guessed). related = the appeal.

CLI:
    python -m data_extraction.case_context.case_status {echr,cjeu,rs} \
        --dsn-env VAR [--from-id N] [--to-id M] --out PATH
"""

import json
import logging
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional

from data_extraction.case_context import cjeu_outcomes, common, echr_outcomes, rs_dictum
from data_extraction.case_context.artifact import StatusRecord, case_key
from data_extraction.linking.artifact import ArtifactWriter

log = logging.getLogger(__name__)

EXTRACTOR_VERSION = "case_status/1.0.0"
RS_EXTRACTOR_VERSION = "case_status/0.1.0"  # depends on the unvalidated dictum rules
ECHR_DATASET = "echr_status"
CJEU_DATASET = "cjeu_appeal_status"
RS_DATASET = "rs_appeal_status"

CONFIDENCE = {
    "struck_out": 0.95,
    "final_grand_chamber": 0.95,
    "final_committee": 0.9,
    "final_inadmissible": 0.9,
    "referred_to_grand_chamber": 0.85,
    "appeal_successful": 0.9,
    "rs_quashed_on_appeal": 0.8,
}
RS_APPEAL_RELATIONS = ("hogerberoep", "cassatie")
_GC_DOCNAME = re.compile(r"[\[(]\s*GC\s*[\])]", re.I)


def _date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    return value


# ---------------------------------------------------------------------------
# ECtHR
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EchrDocument:
    case_id: int
    ecli: Optional[str]
    case_item: Optional[str]
    item_id: str
    doctype: Optional[str]
    branch: Optional[str]
    docname: Optional[str]
    decided: Optional[date]
    conclusion: Optional[str]

    @property
    def key(self):
        return case_key(ecli=self.ecli, item_id=self.case_item)

    @property
    def is_judgment(self):
        return bool(re.search("JUD", self.doctype or "", re.I))

    @property
    def is_decision(self):
        return bool(re.search("DEC", self.doctype or "", re.I))

    @property
    def formation(self) -> Optional[str]:
        branch = re.sub(r"[^A-Z]", "", (self.branch or "").upper())
        if branch == "GRANDCHAMBER" or _GC_DOCNAME.search(self.docname or ""):
            return "grand_chamber"
        if branch == "CHAMBER":
            return "chamber"
        if branch == "COMMITTEE":
            return "committee"
        return None


def own_statuses(doc: EchrDocument, stats: Counter) -> List[StatusRecord]:
    """struck_out and final for one document of a trigger case."""
    key = doc.key
    if key is None:
        stats["no_natural_key"] += 1
        return []
    out = []
    items = echr_outcomes.split_items(doc.conclusion)
    struck = [i for i in items if echr_outcomes.parse_conclusion_item(i)[0] == "struck_out"]
    if struck and (doc.is_judgment or doc.is_decision):
        out.append(_echr(key, "struck_out", doc.decided, None, struck[0], "struck_out"))
    if doc.is_judgment and doc.formation == "grand_chamber":
        out.append(
            _echr(key, "final", doc.decided, None, "Grand Chamber judgment", "final_grand_chamber")
        )
    elif doc.is_judgment and doc.formation == "committee":
        out.append(_echr(key, "final", doc.decided, None, "Committee judgment", "final_committee"))
    elif doc.is_decision and not doc.is_judgment:
        inadmissible = [
            i for i in items if echr_outcomes.parse_conclusion_item(i)[0] == "inadmissible"
        ]
        if inadmissible:
            out.append(
                _echr(key, "final", doc.decided, None, inadmissible[0], "final_inadmissible")
            )
    return out


def _echr(key, status, status_date, related, raw, rule):
    return StatusRecord(
        case=key,
        status=status,
        status_date=status_date,
        related=related,
        raw_value=raw,
        confidence=CONFIDENCE[rule],
        rule=rule,
        source_dataset=ECHR_DATASET,
        extractor_version=EXTRACTOR_VERSION,
    ).validate()


def referral_statuses(
    grand_chamber: EchrDocument, chambers: List[EchrDocument], appnos: Dict[str, List[str]]
) -> List[StatusRecord]:
    """referred_to_grand_chamber for the Chamber judgments of the same
    application dated before the Grand Chamber judgment."""
    gc_key = grand_chamber.key
    out = []
    for chamber in chambers:
        if chamber.case_id == grand_chamber.case_id or chamber.key is None or gc_key is None:
            continue
        if not (chamber.is_judgment and chamber.formation == "chamber"):
            continue
        if chamber.decided is None or grand_chamber.decided is None:
            continue
        if chamber.decided >= grand_chamber.decided:
            continue
        shared = sorted(set(appnos.get(chamber.item_id, ())) & set(appnos[grand_chamber.item_id]))
        if not shared:
            continue
        raw = (
            f"Grand Chamber judgment {grand_chamber.ecli or grand_chamber.item_id} of "
            f"{grand_chamber.decided.isoformat()}, application {', '.join(shared)}"
        )
        out.append(
            _echr(
                chamber.key,
                "referred_to_grand_chamber",
                None,
                gc_key,
                raw,
                "referred_to_grand_chamber",
            )
        )
    return out


_ECHR_DOC_COLUMNS = """
    c.id, c.ecli, c.item_id, d.item_id, d.doctype, d.doctype_branch, d.docname,
    d.judgement_date, d.conclusion
"""
_ECHR_CASES = f"""
    SELECT c.id
      FROM {common.SCHEMA}.cases c
     WHERE EXISTS (SELECT 1 FROM {common.SCHEMA}.echr_document d
                    WHERE d.case_id = c.id AND (d.doctype ~* 'JUD' OR d.doctype ~* 'DEC'))
       {common.CASE_FILTER}
     ORDER BY c.id
     LIMIT %(limit)s
"""
_ECHR_DOCS = f"""
    SELECT {_ECHR_DOC_COLUMNS}
      FROM {common.SCHEMA}.cases c
      JOIN {common.SCHEMA}.echr_document d ON d.case_id = c.id
     WHERE c.id = ANY(%(ids)s) AND (d.doctype ~* 'JUD' OR d.doctype ~* 'DEC')
     ORDER BY c.id, d.item_id
"""
# Judgments sharing an owner application number with the given documents.
_ECHR_SAME_APPNO = f"""
    SELECT DISTINCT {_ECHR_DOC_COLUMNS}
      FROM {common.SCHEMA}.echr_document_appno g
      JOIN {common.SCHEMA}.echr_document_appno o
        ON o.appno = g.appno AND o.source = 'appno' AND o.item_id <> g.item_id
      JOIN {common.SCHEMA}.echr_document d ON d.item_id = o.item_id
      JOIN {common.SCHEMA}.cases c ON c.id = d.case_id
     WHERE g.item_id = ANY(%(items)s) AND g.source = 'appno' AND d.doctype ~* 'JUD'
"""
_ECHR_APPNOS = f"""
    SELECT item_id, appno FROM {common.SCHEMA}.echr_document_appno
     WHERE item_id = ANY(%(items)s) AND source = 'appno'
"""


def _echr_doc(row) -> EchrDocument:
    values = list(row)
    values[7] = _date(values[7])
    return EchrDocument(*values)


def echr_records(cursor, ids, stats: Counter) -> List[StatusRecord]:
    cursor.execute(_ECHR_DOCS, {"ids": ids})
    docs = [_echr_doc(r) for r in cursor.fetchall()]
    records = []
    for doc in docs:
        stats["documents"] += 1
        records.extend(own_statuses(doc, stats))
    grand = [d for d in docs if d.is_judgment and d.formation == "grand_chamber"]
    if grand:
        items = [d.item_id for d in grand]
        cursor.execute(_ECHR_SAME_APPNO, {"items": items})
        others = [_echr_doc(r) for r in cursor.fetchall()]
        all_items = sorted(set(items) | {d.item_id for d in others})
        cursor.execute(_ECHR_APPNOS, {"items": all_items})
        appnos = defaultdict(list)
        for item_id, appno in cursor.fetchall():
            appnos[item_id].append(appno)
        for gc in grand:
            found = referral_statuses(gc, others, appnos)
            stats["referred_to_grand_chamber"] += len(found)
            records.extend(found)
    return _dedupe(records)


def _dedupe(records):
    """One record per (case, status, date, dataset): the first by sort order
    (language variants of a case repeat the same status)."""
    seen, out = set(), []
    for record in sorted(records, key=lambda r: json_key(r)):
        key = (record.case, record.status, record.status_date, record.source_dataset)
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def json_key(record):
    return json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=False)


def extract_echr(conn, case_ids=None, id_range=None, out_path=None, batch_size=common.BATCH_SIZE):
    """ECtHR statuses for the trigger cases; returns (records written, stats)."""
    return _extract(conn, _ECHR_CASES, echr_records, case_ids, id_range, out_path, batch_size)


# ---------------------------------------------------------------------------
# CJEU
# ---------------------------------------------------------------------------

# (appeal case, decision under appeal) pairs whose appeal is a trigger case.
_CJEU_APPEALS = f"""
    SELECT a.id, a.ecli, coalesce(ad.celex_id, a.celex_id), a.date_decision, ad.proc_type,
           u.id, u.ecli, u.celex_id
      FROM {common.SCHEMA}.case_citation cc
      JOIN {common.SCHEMA}.cases a
        ON a.id = CASE cc.relation_type WHEN 'appeal_of' THEN cc.source_case_id
                                        ELSE cc.target_case_id END
      JOIN {common.SCHEMA}.cases u
        ON u.id = CASE cc.relation_type WHEN 'appeal_of' THEN cc.target_case_id
                                        ELSE cc.source_case_id END
      JOIN {common.SCHEMA}.cjeu_document ad ON ad.case_id = a.id
     WHERE cc.relation_type IN ('appeal_of', 'subject_to_appeal')
       AND cc.target_case_id IS NOT NULL
       AND cc.source_case_id <> cc.target_case_id
       AND a.id = ANY(%(ids)s)
     ORDER BY a.id, u.id
"""
_CJEU_CASES = f"""
    SELECT c.id
      FROM {common.SCHEMA}.cases c
      JOIN {common.SCHEMA}.cjeu_document d ON d.case_id = c.id
     WHERE d.proc_type IS NOT NULL
       {common.CASE_FILTER}
     ORDER BY c.id
     LIMIT %(limit)s
"""


def appeal_status(appeal, under_appeal, stats: Counter) -> Optional[StatusRecord]:
    """appeal: (ecli, celex, decided, proc_type); under_appeal: (ecli, celex)."""
    ecli, celex, decided, proc_type = appeal
    if not cjeu_outcomes.is_decision_celex(celex):
        stats["appeal_not_a_decision"] += 1
        return None
    procedure, _ = cjeu_outcomes.split_proc_type(proc_type)
    outcome, _ = cjeu_outcomes.parse_proc_type(proc_type)
    if not (procedure or "").lower().startswith("appeal"):
        stats["not_an_appeal_procedure"] += 1
        return None
    if outcome != "successful":
        stats[f"appeal_{outcome or 'no_outcome'}"] += 1
        return None
    target, related = case_key(*under_appeal), case_key(ecli=ecli, celex=celex)
    if target is None or related is None or target == related:
        stats["no_natural_key"] += 1
        return None
    stats["overturned"] += 1
    return StatusRecord(
        case=target,
        status="overturned",
        status_date=_date(decided),
        related=related,
        raw_value=proc_type,
        confidence=CONFIDENCE["appeal_successful"],
        rule="appeal_successful",
        source_dataset=CJEU_DATASET,
        extractor_version=EXTRACTOR_VERSION,
    ).validate()


def cjeu_records(cursor, ids, stats: Counter) -> List[StatusRecord]:
    cursor.execute(_CJEU_APPEALS, {"ids": ids})
    records = []
    for row in cursor.fetchall():
        _a, a_ecli, a_celex, a_date, proc_type, _u, u_ecli, u_celex = row
        stats["appeal_links"] += 1
        record = appeal_status((a_ecli, a_celex, a_date, proc_type), (u_ecli, u_celex), stats)
        if record is not None:
            records.append(record)
    return _dedupe(records)


def extract_cjeu(conn, case_ids=None, id_range=None, out_path=None, batch_size=common.BATCH_SIZE):
    """CJEU 'overturned' statuses caused by the trigger cases (appeals)."""
    return _extract(conn, _CJEU_CASES, cjeu_records, case_ids, id_range, out_path, batch_size)


# ---------------------------------------------------------------------------
# Rechtspraak
# ---------------------------------------------------------------------------

_RS_CASES = f"""
    SELECT c.id
      FROM {common.SCHEMA}.cases c
      JOIN {common.SCHEMA}.rs_document d ON d.case_id = c.id
     WHERE true
       {common.CASE_FILTER}
     ORDER BY c.id
     LIMIT %(limit)s
"""
# Earlier RS decisions joined to a trigger decision by an appeal relation,
# in either direction, with the trigger's text.
_RS_APPEALS = f"""
    SELECT a.id, a.ecli, a.date_decision, t.fulltext, u.id, u.ecli, u.date_decision,
           cc.relation_type
      FROM {common.SCHEMA}.cases a
      JOIN {common.SCHEMA}.case_citation cc
        ON (cc.source_case_id = a.id OR cc.target_case_id = a.id)
      JOIN {common.SCHEMA}.cases u
        ON u.id = CASE WHEN cc.source_case_id = a.id THEN cc.target_case_id
                       ELSE cc.source_case_id END
      JOIN {common.SCHEMA}.rs_document ud ON ud.case_id = u.id
      LEFT JOIN {common.SCHEMA}.case_text_canonical t ON t.case_id = a.id AND t.language = 'nl'
     WHERE a.id = ANY(%(ids)s)
       AND cc.source_dataset LIKE 'rs_formal_relation%%'
       AND cc.relation_type = ANY(%(relations)s)
       AND cc.target_case_id IS NOT NULL
       AND cc.source_case_id <> cc.target_case_id
       AND u.date_decision < a.date_decision
     ORDER BY a.id, u.id
"""


def rs_records(cursor, ids, stats: Counter) -> List[StatusRecord]:
    cursor.execute(_RS_APPEALS, {"ids": ids, "relations": list(RS_APPEAL_RELATIONS)})
    by_appeal = defaultdict(list)
    for row in cursor.fetchall():
        by_appeal[row[0]].append(row)
    records = []
    for rows in by_appeal.values():
        a_ecli, a_date, text = rows[0][1], rows[0][2], rows[0][3]
        earlier = {r[4]: r for r in rows}
        stats["appeals"] += 1
        if len(earlier) != 1:
            stats["several_earlier_decisions"] += 1
            continue
        found, reason = rs_dictum.parse_dictum(text)
        stats[f"dictum_{reason}"] += 1
        quashed = [f for f in found if f[0] == "quashed"]
        if not quashed:
            continue
        _a, _ae, _ad, _t, _u, u_ecli, _ud, relation = next(iter(earlier.values()))
        target, related = case_key(ecli=u_ecli), case_key(ecli=a_ecli)
        if target is None or related is None:
            stats["no_natural_key"] += 1
            continue
        stats["overturned"] += 1
        records.append(
            StatusRecord(
                case=target,
                status="overturned",
                status_date=_date(a_date),
                related=related,
                raw_value=f"{relation}: {quashed[0][3]}",
                confidence=CONFIDENCE["rs_quashed_on_appeal"],
                rule="rs_quashed_on_appeal",
                source_dataset=RS_DATASET,
                extractor_version=RS_EXTRACTOR_VERSION,
            ).validate()
        )
    return _dedupe(records)


def extract_rs(conn, case_ids=None, id_range=None, out_path=None, batch_size=common.BATCH_SIZE):
    """RS 'overturned' statuses caused by the trigger decisions (needs the
    dictum rules; the caller checks RS_DICTUM_ENABLED)."""
    return _extract(conn, _RS_CASES, rs_records, case_ids, id_range, out_path, batch_size)


# ---------------------------------------------------------------------------


def _extract(conn, cases_sql, records_for, case_ids, id_range, out_path, batch_size):
    stats: Counter = Counter()
    with ArtifactWriter(out_path) as writer:
        for rows in common.iter_rows(conn, cases_sql, case_ids, id_range, batch_size):
            ids = [r[0] for r in rows]
            stats["trigger_cases"] += len(ids)
            with conn.cursor() as cursor:
                records = records_for(cursor, ids, stats)
            conn.rollback()
            writer.write(records)
    stats["records"] = writer.count
    log.info("case_status: %s", dict(sorted(stats.items())))
    return writer.count, stats


EXTRACTORS = {"echr": extract_echr, "cjeu": extract_cjeu, "rs": extract_rs}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which not in EXTRACTORS:
        raise SystemExit(f"usage: case_status {{{','.join(EXTRACTORS)}}} --dsn-env VAR ...")
    raise SystemExit(common.cli(__doc__.split("\n\n")[0], EXTRACTORS[which], sys.argv[2:]))
