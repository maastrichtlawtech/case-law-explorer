"""
ECtHR outcomes per Convention article from HUDOC's fields (roadmap R5.1).

Read from ``echr_document`` (judgments and decisions: doctype containing JUD
or DEC, like the view echr_v_judgments_decisions), never changed:

    violation      HUDOC 'violation', articles found violated, ';'-separated
                   ('3;6-1;P1-1')
    nonviolation   HUDOC 'nonviolation', articles found not violated
    conclusion     HUDOC 'conclusion' (the loader maps it through the
                   'summary' name; same column), ';'-separated items such as
                   'Violation of Article 3 - Prohibition of torture (...)',
                   'No violation of Article 8 - ...', 'Violation of P1-1',
                   'Inadmissible', 'Struck out of the list', 'Remainder
                   inadmissible', 'Non-pecuniary damage - award'

and ``echr_document_article`` rows of kind violation / nonviolation (the
normalised form the migration copied from the legacy database).

Rows written (source_dataset 'echr_conclusion'):

    scope 'article', outcome violation | no_violation, article as the
    Convention article without its paragraph: '3', '6' (for '6-1', '6-3-c'),
    '14' (for '14+8', '14+P1-1' and "Article 14 taken in conjunction with
    Article 1 of Protocol No. 1": the lead article, the one before '+' or
    "(taken) in conjunction with"), 'P1-1' (Article 1 of Protocol No. 1;
    'P1-1-1' -> 'P1-1'). raw_value keeps every source piece as written,
    ' | '-separated, prefixed with its field.

    scope 'overall', outcome inadmissible when a conclusion item of a
    decision (not a judgment, as case_status reads it) is exactly
    "Inadmissible" (or starts with "Inadmissible (" / "Inadmissible:"), and
    struck_out when one starts with "Struck out of the list". "Remainder
    inadmissible", "Partly inadmissible" and the like are partial and are not
    an overall outcome. No overall row is written for a case with
    article-level findings (a merits judgment that declares part of the
    application inadmissible or strikes part of it out is not inadmissible or
    struck out as a whole); such items are counted ``overall_suppressed``.

Conclusion items are split on ';' outside parentheses. An item that names a
violation but whose article cannot be read is not guessed (counted
``unreadable_article``); an item in another language is not parsed.

The same article can carry both violation and no_violation (e.g. the
procedural and the substantive limb of Article 2): both rows are written.

CLI:
    python -m data_extraction.case_context.echr_outcomes --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from data_extraction.case_context import common
from data_extraction.case_context.artifact import OutcomeRecord, case_key
from data_extraction.linking.artifact import ArtifactWriter

log = logging.getLogger(__name__)

SOURCE_DATASET = "echr_conclusion"
EXTRACTOR_VERSION = "echr_outcomes/1.0.0"
CONFIDENCE_FIELD = 0.97  # HUDOC's structured violation/nonviolation lists
CONFIDENCE_CONCLUSION = 0.95  # read from the conclusion text only
CONFIDENCE_OVERALL = 0.95

_PROTOCOL_ARTICLE = re.compile(
    r"\bart(?:icle|\.)?\s*(\d+)(?:[-.\s]*(?:para(?:graph)?\.?\s*)?\d+)*\s+of\s+protocol"
    r"\s+(?:no\.?\s*)?(\d+)",
    re.I,
)
_P_CODE = re.compile(r"(?<![A-Za-z0-9])P\s*(\d+)\s*-\s*(\d+)", re.I)
_ARTICLE = re.compile(r"\bart(?:icle|\.)?\s*(\d+)", re.I)
_VIOLATION = re.compile(r"^(?P<neg>no|non)?[-\s]*violations?\s+of\s+(?P<rest>.+)$", re.I | re.S)
_INADMISSIBLE = re.compile(r"^inadmissible\s*(?:$|[(:])", re.I)
_STRUCK_OUT = re.compile(r"^struck\s+out\s+of\s+(?:the\s+)?list\b", re.I)
# What follows the lead article: "14+P1-1", "Article 14 taken in conjunction
# with Article 1 of Protocol No. 1".
_CONJUNCTION = re.compile(r"\+|\b(?:taken\s+)?in\s+conjunction\s+with\b", re.I)
_JUDGMENT = re.compile("JUD", re.I)
_FIELD_TOKEN = re.compile(r"^\s*(?:P\s*(\d+)\s*-\s*(\d+)|(\d+))")


def split_items(conclusion: Optional[str]) -> List[str]:
    """Split a HUDOC conclusion on ';' outside parentheses."""
    items, depth, current = [], 0, []
    for char in conclusion or "":
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        if char == ";" and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    items.append("".join(current))
    return [" ".join(i.split()) for i in items if i.strip()]


def _head(text: str) -> str:
    """The part naming the (lead) article: before ' - ' or the first '(',
    then before '+' or "(taken) in conjunction with"."""
    head = re.split(r"\s+-\s+|\(", text, maxsplit=1)[0]
    return _CONJUNCTION.split(head, maxsplit=1)[0]


def article_from_text(text: str) -> Optional[str]:
    """'Article 6 - Right to a fair trial' -> '6'; 'Art. 6-1' -> '6';
    'Article 1 of Protocol No. 1 - ...' -> 'P1-1'; 'P1-1' -> 'P1-1';
    'Article 14+8 - ...' -> '14', 'Article 14+P1-1' -> '14'. None when no
    article can be read."""
    head = _head(text)
    match = _PROTOCOL_ARTICLE.search(head)
    if match:
        return f"P{int(match.group(2))}-{int(match.group(1))}"
    match = _P_CODE.search(head)
    if match:
        return f"P{int(match.group(1))}-{int(match.group(2))}"
    match = _ARTICLE.search(head)
    if match:
        return str(int(match.group(1)))
    return None


def article_from_token(token: str) -> Optional[str]:
    """A token of HUDOC's violation/nonviolation list: '6-1' -> '6',
    'P1-1' -> 'P1-1', '14+8' -> '14'."""
    match = _FIELD_TOKEN.match(token or "")
    if not match:
        return None
    if match.group(1):
        return f"P{int(match.group(1))}-{int(match.group(2))}"
    return str(int(match.group(3)))


def parse_conclusion_item(item: str) -> Tuple[Optional[str], Optional[str], str]:
    """(outcome, article or None, reason) for one conclusion item."""
    if _STRUCK_OUT.match(item):
        return "struck_out", None, "ok"
    if _INADMISSIBLE.match(item):
        return "inadmissible", None, "ok"
    match = _VIOLATION.match(item)
    if not match:
        return None, None, "other_item"
    article = article_from_text(match.group("rest"))
    if article is None:
        return None, None, "unreadable_article"
    return ("no_violation" if match.group("neg") else "violation"), article, "ok"


class CaseOutcomes:
    """Collects the outcomes of one case from all its documents."""

    def __init__(self):
        # (scope, article, outcome) -> ({raw pieces}, from a structured field?)
        self.found: Dict[Tuple[str, Optional[str], str], Tuple[Set[str], List[bool]]] = {}

    def add(self, scope, article, outcome, raw, structured):
        raws, flags = self.found.setdefault((scope, article, outcome), (set(), []))
        raws.add(raw)
        flags.append(structured)

    def add_field(self, field: str, value: Optional[str], outcome: str, stats: Counter):
        for token in (value or "").split(";"):
            token = token.strip()
            if not token:
                continue
            article = article_from_token(token)
            if article is None:
                stats[f"unreadable_{field}_token"] += 1
                continue
            self.add("article", article, outcome, f"{field}: {token}", True)

    def add_conclusion(self, conclusion: Optional[str], stats: Counter, judgment: bool = False):
        for item in split_items(conclusion):
            outcome, article, reason = parse_conclusion_item(item)
            stats[f"item_{reason}"] += 1
            if outcome is None:
                continue
            if judgment and outcome == "inadmissible":
                stats["overall_suppressed"] += 1
                continue
            scope = "article" if article else "overall"
            self.add(scope, article, outcome, f"conclusion: {item}", False)

    def records(self, key, stats: Optional[Counter] = None) -> List[OutcomeRecord]:
        out = []
        has_articles = any(scope == "article" for scope, _a, _o in self.found)
        for (scope, article, outcome), (raws, flags) in sorted(
            self.found.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2])
        ):
            if scope == "overall" and has_articles:
                if stats is not None:
                    stats["overall_suppressed"] += 1
                continue
            if scope == "overall":
                confidence = CONFIDENCE_OVERALL
            else:
                confidence = CONFIDENCE_FIELD if any(flags) else CONFIDENCE_CONCLUSION
            out.append(
                OutcomeRecord(
                    case=key,
                    scope=scope,
                    article=article,
                    outcome=outcome,
                    raw_value=" | ".join(sorted(raws)),
                    confidence=confidence,
                    rule="hudoc_fields" if any(flags) else "hudoc_conclusion",
                    source_dataset=SOURCE_DATASET,
                    extractor_version=EXTRACTOR_VERSION,
                ).validate()
            )
        return out


def outcomes_for_documents(key, documents: Iterable[tuple], stats: Counter) -> List[OutcomeRecord]:
    """documents: (conclusion, violation, nonviolation, [(kind, article_code)]
    [, doctype]) of one case's judgments and decisions."""
    collected = CaseOutcomes()
    for document in documents:
        conclusion, violation, nonviolation, articles = document[:4]
        doctype = document[4] if len(document) > 4 else None
        collected.add_field("violation", violation, "violation", stats)
        collected.add_field("nonviolation", nonviolation, "no_violation", stats)
        for kind, code in articles or ():
            article = article_from_token(code or "")
            if article is None:
                stats["unreadable_article_row"] += 1
                continue
            outcome = "violation" if kind == "violation" else "no_violation"
            collected.add("article", article, outcome, f"echr_document_article: {code}", True)
        judgment = bool(_JUDGMENT.search(doctype or ""))
        collected.add_conclusion(conclusion, stats, judgment)
    return collected.records(key, stats)


# All judgments and decisions of the given cases (a case's language
# variants share the case row).
_DOCS = f"""
    SELECT c.id, c.ecli, c.item_id, d.item_id, d.conclusion, d.violation, d.nonviolation,
           ARRAY(SELECT ARRAY[a.kind, a.article_code]
                   FROM {common.SCHEMA}.echr_document_article a
                  WHERE a.item_id = d.item_id AND a.kind IN ('violation', 'nonviolation')
                  ORDER BY a.kind, a.article_code),
           d.doctype
      FROM {common.SCHEMA}.cases c
      JOIN {common.SCHEMA}.echr_document d ON d.case_id = c.id
     WHERE (d.doctype ~* 'JUD' OR d.doctype ~* 'DEC')
       AND c.id = ANY(%(ids)s)
     ORDER BY c.id, d.item_id
"""

# Page over the case ids that have a judgment or decision.
_CASES = f"""
    SELECT c.id
      FROM {common.SCHEMA}.cases c
     WHERE EXISTS (SELECT 1 FROM {common.SCHEMA}.echr_document d
                    WHERE d.case_id = c.id AND (d.doctype ~* 'JUD' OR d.doctype ~* 'DEC'))
       {common.CASE_FILTER}
     ORDER BY c.id
     LIMIT %(limit)s
"""


def _by_case(rows):
    grouped = defaultdict(list)
    keys = {}
    for row in rows:
        case_id, ecli, case_item, _item, conclusion, violation, nonviolation, articles = row[:8]
        doctype = row[8] if len(row) > 8 else None
        keys[case_id] = case_key(ecli=ecli, item_id=case_item)
        grouped[case_id].append(
            (conclusion, violation, nonviolation, [tuple(a) for a in articles], doctype)
        )
    return keys, grouped


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size=common.BATCH_SIZE):
    """Write the outcome artifact for the ECtHR cases selected by case_ids or
    id_range; returns (records written, stats). Pages over case ids, so a
    case's documents are always read together."""
    stats: Counter = Counter()
    with ArtifactWriter(out_path) as writer:
        for rows in common.iter_rows(conn, _CASES, case_ids, id_range, batch_size):
            ids = [r[0] for r in rows]
            with conn.cursor() as cursor:
                cursor.execute(_DOCS, {"ids": ids})
                docs = cursor.fetchall()
            conn.rollback()
            keys, grouped = _by_case(docs)
            records = []
            for case_id in ids:
                if case_id not in grouped:
                    continue
                stats["cases"] += 1
                key = keys[case_id]
                if key is None:
                    stats["no_natural_key"] += 1
                    continue
                records.extend(outcomes_for_documents(key, grouped[case_id], stats))
            writer.write(records)
    stats["records"] = writer.count
    log.info("echr_outcomes: %s", dict(sorted(stats.items())))
    return writer.count, stats


if __name__ == "__main__":
    raise SystemExit(common.cli(__doc__.split("\n\n")[0], extract))
