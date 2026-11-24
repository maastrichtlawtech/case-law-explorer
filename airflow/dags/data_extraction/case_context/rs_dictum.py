"""
Dutch decisions: the outcome from the dictum (roadmap R5.1).

NOT VALIDATED ON REAL TEXT. The research files (cjeu-migration
migration/verify/research-2026-11-24) hold no Rechtspraak judgment text, so
the rules below are tested only on clearly labelled illustrative strings.
The weekly run and the backfill use this module only with RS_DICTUM_ENABLED
(default off), which stays off until a hand-checked db-dev sample exists.

Precision first: when the operative part cannot be found, or its phrases
disagree, nothing is written (counted as ``unknown`` / ``conflict``).

The operative part is the text after the LAST heading "Beslissing" /
"De beslissing" / "Dictum" (on a line of its own, optionally numbered:
"5. Beslissing", "6 De beslissing"), or, failing that, after the last line
"De Hoge Raad:"; it ends at the signature ("Dit arrest is gewezen door",
"Deze uitspraak is gedaan door", "Aldus gewezen", ...) or after 4,000
characters. In it:

    dismissed     "verwerpt het beroep" (cassation),
                  "verklaart het (hoger) beroep ongegrond",
                  "bekrachtigt / bevestigt het vonnis / de beschikking /
                  de (aangevallen) uitspraak / het arrest"
    upheld        "verklaart het (hoger) beroep gegrond"
    quashed       "vernietigt het (bestreden) vonnis / arrest / de beschikking /
                  de (aangevallen) uitspraak" (a court decision; "vernietigt
                  het bestreden besluit" annuls an administrative decision and
                  is not a quashed judgment)
    inadmissible  "verklaart het (hoger) beroep niet-ontvankelijk"

Allowed together: upheld + quashed (the Raad van State: "verklaart het hoger
beroep gegrond; vernietigt de aangevallen uitspraak"). Every other mix (a
partial quash next to "bekrachtigt ... voor het overige", dismissed next to
quashed) is a conflict and writes nothing. A quash limited by "voor zover"
in the same clause is partial and writes nothing either.

source_dataset 'rs_dictum', scope 'overall', raw_value the matched phrases
as written (' | '-separated), confidence per rule.

CLI:
    python -m data_extraction.case_context.rs_dictum --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH
"""

import logging
import os
import re
from collections import Counter
from typing import List, Optional, Tuple

from data_extraction.case_context import common
from data_extraction.case_context.artifact import OutcomeRecord, case_key
from data_extraction.linking.artifact import ArtifactWriter

log = logging.getLogger(__name__)

SOURCE_DATASET = "rs_dictum"
EXTRACTOR_VERSION = "rs_dictum/0.1.0"  # 0.x: not validated on real text
FLAG = "RS_DICTUM_ENABLED"
MAX_OPERATIVE = 4000

_HEADING = re.compile(
    r"(?im)^[ \t]*(?:\d+(?:\.\d+)*\.?[ \t]+)?(?:de[ \t]+)?(?:beslissing|dictum)[ \t]*:?[ \t]*$"
)
_HR_OPENING = re.compile(r"(?im)^[ \t]*de[ \t]+hoge[ \t]+raad[ \t]*:[ \t]*$")
_SIGNATURE = re.compile(
    r"(?i)\b(?:dit\s+arrest\s+is\s+gewezen|deze\s+uitspraak\s+is\s+gedaan"
    r"|dit\s+vonnis\s+is\s+gewezen|deze\s+beschikking\s+is\s+gegeven"
    r"|aldus\s+(?:gewezen|gedaan|vastgesteld|gegeven))"
)

_DECISION = (
    r"(?:(?:tussen|eind|deel)?"
    r"(?:vonnis(?:sen)?|arrest(?:en)?|beschikking(?:en)?|uitspra(?:ak|ken)))"
)
_QUALIFIER = r"(?:(?:in\s+cassatie\s+)?(?:bestreden|aangevallen|tussen\s+partijen\s+gewezen)\s+)?"

RULES = (
    # (outcome, rule, confidence, pattern)
    (
        "dismissed",
        "verwerpt_beroep",
        0.9,
        re.compile(r"\bverwerpt\s+het\s+(?:cassatie)?beroep\b", re.I),
    ),
    (
        "dismissed",
        "beroep_ongegrond",
        0.9,
        re.compile(
            r"\bverklaart\s+het\s+(?:hoger\s+|incidenteel\s+)?beroep"
            r"(?:\s+in\s+cassatie)?\s+ongegrond\b",
            re.I,
        ),
    ),
    (
        "dismissed",
        "bekrachtigt",
        0.85,
        re.compile(rf"\b(?:bekrachtigt|bevestigt)\s+(?:het|de)\s+{_QUALIFIER}{_DECISION}\b", re.I),
    ),
    (
        "upheld",
        "beroep_gegrond",
        0.9,
        re.compile(
            r"\bverklaart\s+het\s+(?:hoger\s+)?beroep(?:\s+in\s+cassatie)?\s+gegrond\b", re.I
        ),
    ),
    (
        "quashed",
        "vernietigt",
        0.9,
        re.compile(rf"\bvernietigt\s+(?:het|de)\s+{_QUALIFIER}{_DECISION}\b", re.I),
    ),
    (
        "inadmissible",
        "beroep_niet_ontvankelijk",
        0.85,
        re.compile(
            r"\bverklaart\s+het\s+(?:hoger\s+)?beroep(?:\s+in\s+cassatie)?"
            r"\s+niet[-\s]?ontvankelijk\b",
            re.I,
        ),
    ),
)
_ALLOWED = ({"dismissed"}, {"upheld"}, {"quashed"}, {"upheld", "quashed"}, {"inadmissible"})
_PARTIAL = re.compile(r"\bvoor\s+zover\b", re.I)


def enabled() -> bool:
    value = (os.environ.get(FLAG) or "").strip().lower()
    return value in ("1", "true", "yes", "on")


def operative_part(text: Optional[str]) -> Optional[str]:
    """The dictum: after the last Beslissing/Dictum heading (else the last
    'De Hoge Raad:' line), up to the signature or MAX_OPERATIVE characters."""
    if not text:
        return None
    starts = [m.end() for m in _HEADING.finditer(text)]
    if not starts:
        starts = [m.end() for m in _HR_OPENING.finditer(text)]
    if not starts:
        return None
    part = text[starts[-1] :]
    signature = _SIGNATURE.search(part)
    if signature:
        part = part[: signature.start()]
    part = part[:MAX_OPERATIVE].strip()
    return part or None


def _clause(text: str, start: int, end: int) -> str:
    """The clause around a match: up to the previous and next ';' or line end."""
    left = max(text.rfind(";", 0, start), text.rfind("\n", 0, start)) + 1
    rights = [i for i in (text.find(";", end), text.find("\n", end)) if i != -1]
    return text[left : min(rights) if rights else len(text)]


def parse_dictum(text: Optional[str]) -> Tuple[List[Tuple[str, str, float, str]], str]:
    """([(outcome, rule, confidence, phrase)], reason) from a decision's text;
    reason is 'ok', 'no_operative_part', 'no_phrase', 'conflict' or
    'partial'. The list is empty unless reason is 'ok'."""
    part = operative_part(text)
    if part is None:
        return [], "no_operative_part"
    found = []
    for outcome, rule, confidence, pattern in RULES:
        for match in pattern.finditer(part):
            clause = _clause(part, match.start(), match.end())
            if outcome == "quashed" and _PARTIAL.search(clause):
                return [], "partial"
            found.append((outcome, rule, confidence, " ".join(match.group(0).split())))
    if not found:
        return [], "no_phrase"
    if {f[0] for f in found} not in _ALLOWED:
        return [], "conflict"
    return found, "ok"


def outcome_records(key, text, stats: Counter) -> List[OutcomeRecord]:
    found, reason = parse_dictum(text)
    stats[reason] += 1
    if not found:
        return []
    by_outcome = {}
    for outcome, rule, confidence, phrase in found:
        rules, conf, phrases = by_outcome.get(outcome, (set(), 0.0, set()))
        by_outcome[outcome] = (rules | {rule}, max(conf, confidence), phrases | {phrase})
    return [
        OutcomeRecord(
            case=key,
            outcome=outcome,
            raw_value=" | ".join(sorted(phrases)),
            confidence=conf,
            rule="+".join(sorted(rules)),
            source_dataset=SOURCE_DATASET,
            extractor_version=EXTRACTOR_VERSION,
        ).validate()
        for outcome, (rules, conf, phrases) in sorted(by_outcome.items())
    ]


# Rechtspraak decisions (not the Procureur-Generaal's conclusions) with Dutch
# text, through case_text_canonical (misfiled texts left out).
_ROWS = f"""
    SELECT c.id, c.ecli, t.fulltext
      FROM {common.SCHEMA}.cases c
      JOIN {common.SCHEMA}.rs_document d ON d.case_id = c.id
      JOIN {common.SCHEMA}.case_text_canonical t ON t.case_id = c.id AND t.language = 'nl'
     WHERE t.fulltext IS NOT NULL
       AND coalesce(d.document_type, '') !~* 'conclusie'
       {common.CASE_FILTER}
     ORDER BY c.id
     LIMIT %(limit)s
"""


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size=common.BATCH_SIZE):
    """Write the outcome artifact for the RS decisions selected by case_ids or
    id_range; returns (records written, stats)."""
    stats: Counter = Counter()
    with ArtifactWriter(out_path) as writer:
        for rows in common.iter_rows(conn, _ROWS, case_ids, id_range, batch_size):
            records = []
            for _case_id, ecli, text in rows:
                stats["decisions"] += 1
                key = case_key(ecli=ecli)
                if key is None:
                    stats["no_natural_key"] += 1
                    continue
                records.extend(outcome_records(key, text, stats))
            writer.write(records)
    stats["records"] = writer.count
    log.info("rs_dictum: %s", dict(sorted(stats.items())))
    return writer.count, stats


if __name__ == "__main__":
    raise SystemExit(common.cli(__doc__.split("\n\n")[0], extract))
