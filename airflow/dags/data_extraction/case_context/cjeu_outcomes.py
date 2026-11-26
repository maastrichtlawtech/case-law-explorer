"""
CJEU outcomes from Cellar's type_procedure (roadmap R5.1, case-law-explorer
issue #83).

Where the raw value lives: the CJEU loader writes Cellar's ``type_procedure``
unchanged to ``cjeu_document.proc_type`` (cjeu_mapping.py,
``"proc_type": first(get("type_procedure"))``) and never fills
``cjeu_document.procedure_result``, which is NULL on every row (caselaw-coolify
db/docs/DATA_QUALITY.md: "the parse from type_procedure is not written; the
raw value is preserved in proc_type"). This module does not touch
cjeu_document: it reads proc_type and writes NEW case_outcome rows, with the
whole proc_type value untouched in raw_value.

The outcome is the part after the last " - " (issue #83, 3,552 cases sampled
from the live API, 43 distinct values):

    Action for annulment - unfounded                 unfounded
    Action for failure to fulfil obligations - successful
                                                     successful
    Reference for a preliminary ruling - inadmissible
                                                     inadmissible
    Action for annulment - decision unnecessary      decision_unnecessary
    Staff cases - amicable settlement made between the parties
                                                     amicable_settlement
    Request for an Opinion - agreement compatible    agreement_compatible
    Action for annulment - interlocutory judgment    interlocutory
    Preliminary reference - urgent procedure         (no outcome: a procedure variant)
    Reference for a preliminary ruling               (no suffix: no outcome)

A suffix outside the known set is not guessed: no row, counted as
``unrecognised_suffix`` and logged with its value so the set can be extended.

Only the decision documents carry an outcome row: CELEX type CJ/TJ/FJ
(judgments), CO/TO/FO (orders), CV (Opinions of the Court under art. 218(11)
TFEU) and CD (decisions). An Advocate General's opinion (CC) or a published
request (CN) shares its case's type_procedure but decides nothing.

Known limit: ``first(get("type_procedure"))`` keeps only the first value
Cellar returns. Whether Cellar ever returns several (issue #83, point 1)
needs a db-dev/Cellar check; a lost second value cannot be recovered here.

source_dataset 'cjeu_proc_type', scope 'overall'.

CLI:
    python -m data_extraction.case_context.cjeu_outcomes --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH
"""

import logging
import re
from collections import Counter
from typing import Optional, Tuple

from data_extraction.case_context import common
from data_extraction.case_context.artifact import OutcomeRecord, case_key
from data_extraction.linking.artifact import ArtifactWriter

log = logging.getLogger(__name__)

SOURCE_DATASET = "cjeu_proc_type"
EXTRACTOR_VERSION = "cjeu_outcomes/1.0.0"
CONFIDENCE = 0.98  # Cellar's own label, parsed by an exact suffix match

# Lower-cased suffix -> outcome. Prefix matches are listed separately.
SUFFIXES = {
    "successful": "successful",
    "unfounded": "unfounded",
    "inadmissible": "inadmissible",
    "decision unnecessary": "decision_unnecessary",
    "agreement compatible": "agreement_compatible",
    "agreement incompatible": "agreement_incompatible",
    "agreement not compatible": "agreement_incompatible",
    "interlocutory judgment": "interlocutory",
}
PREFIXES = (("amicable settlement", "amicable_settlement"),)
# Suffixes that are procedure variants, not outcomes (issue #83).
NOT_OUTCOMES = ("urgent procedure",)

DECISION_CELEX = re.compile(r"^6\d{4}(CJ|TJ|FJ|CO|TO|FO|CV|CD)\d{4}")
_SEP = re.compile(r"\s+[-‐-―]\s+")


def split_proc_type(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """'Action for annulment - unfounded' -> ('Action for annulment',
    'unfounded'); no ' - ' -> (value, None). Splits on the LAST separator."""
    text = " ".join((value or "").split())
    if not text:
        return None, None
    parts = _SEP.split(text)
    if len(parts) < 2:
        return text, None
    return " - ".join(parts[:-1]), parts[-1]


def parse_proc_type(value: Optional[str]) -> Tuple[Optional[str], str]:
    """(outcome or None, reason). reason is 'ok', 'empty', 'no_suffix',
    'procedure_variant' or 'unrecognised_suffix'."""
    procedure, suffix = split_proc_type(value)
    if procedure is None:
        return None, "empty"
    if suffix is None:
        return None, "no_suffix"
    key = suffix.lower().rstrip(".")
    if key in NOT_OUTCOMES:
        return None, "procedure_variant"
    if key in SUFFIXES:
        return SUFFIXES[key], "ok"
    for prefix, outcome in PREFIXES:
        if key.startswith(prefix):
            return outcome, "ok"
    return None, "unrecognised_suffix"


def is_decision_celex(celex: Optional[str]) -> bool:
    return bool(DECISION_CELEX.match((celex or "").strip().upper()))


def outcome_record(ecli, celex, proc_type, stats: Counter) -> Optional[OutcomeRecord]:
    if not is_decision_celex(celex):
        stats["not_a_decision"] += 1
        return None
    outcome, reason = parse_proc_type(proc_type)
    stats[reason] += 1
    if outcome is None:
        if reason == "unrecognised_suffix":
            log.info("cjeu_outcomes: unrecognised type_procedure %r (%s)", proc_type, celex)
        return None
    key = case_key(ecli=ecli, celex=celex)
    if key is None:
        stats["no_natural_key"] += 1
        return None
    return OutcomeRecord(
        case=key,
        outcome=outcome,
        raw_value=proc_type,
        confidence=CONFIDENCE,
        rule="proc_type_suffix",
        source_dataset=SOURCE_DATASET,
        extractor_version=EXTRACTOR_VERSION,
    ).validate()


_ROWS = f"""
    SELECT c.id, c.ecli, coalesce(d.celex_id, c.celex_id), d.proc_type
      FROM {common.SCHEMA}.cjeu_document d
      JOIN {common.SCHEMA}.cases c ON c.id = d.case_id
     WHERE d.proc_type IS NOT NULL AND btrim(d.proc_type) <> ''
       {common.CASE_FILTER}
     ORDER BY c.id
     LIMIT %(limit)s
"""


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size=common.BATCH_SIZE):
    """Write the outcome artifact for the CJEU cases selected by case_ids or
    id_range; returns (records written, stats)."""
    stats: Counter = Counter()
    with ArtifactWriter(out_path) as writer:
        for rows in common.iter_rows(conn, _ROWS, case_ids, id_range, batch_size):
            records = []
            for _case_id, ecli, celex, proc_type in rows:
                stats["documents"] += 1
                record = outcome_record(ecli, celex, proc_type, stats)
                if record is not None:
                    records.append(record)
            writer.write(records)
    stats["records"] = writer.count
    log.info("cjeu_outcomes: %s", dict(sorted(stats.items())))
    return writer.count, stats


if __name__ == "__main__":
    raise SystemExit(common.cli(__doc__.split("\n\n")[0], extract))
