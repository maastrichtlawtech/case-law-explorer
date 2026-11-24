"""
Choosing the target of a reference among the cases that carry its identifier.

A CJEU case number names the judgment, its orders and the Advocate General's
opinion; an ECtHR application number names the judgment, the admissibility
decision and sometimes several judgments (merits, just satisfaction,
revision). Every extractor resolves through these functions so they all pick
the same way, and each choice comes back with the rule that made it and a
confidence for case_citation.match_method / confidence.

Rules (roadmap R2.1, R2.2, R2.6; research README, rs/ and echr/ sections):

CJEU case numbers
  * never a document dated after the citing decision;
  * an opinion only when the text says so ("conclusie", "Opinion",
    "conclusions"); otherwise a judgment, falling back to an order when the
    case number has no judgment (4,864 numbers have only orders);
  * among several of the chosen kind, the earliest (the principal decision;
    later ones are rectifications, interpretations, costs) - with lower
    confidence, because the choice is a rule rather than the text.

ECtHR application numbers (owner numbers only: case_identifier holds the
'appno' field of echr_document_appno, never 'extractedappno')
  * never a document dated after the citing decision; never a communicated case;
  * a decision only when the citation says "(dec.)"/"(déc.)", or when there is
    no judgment;
  * among several judgments: the exact cited date, then the cited year, then
    the earliest.
"""

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional, Sequence

from data_extraction.linking import identifiers

SCHEMA = "cle_v2"

CJEU_JUDGMENT, CJEU_ORDER, CJEU_OPINION, OTHER = "judgment", "order", "opinion", "other"
ECHR_JUDGMENT, ECHR_DECISION, ECHR_COMMUNICATED = "judgment", "decision", "communicated"


@dataclass(frozen=True)
class Candidate:
    case_id: int
    ecli: Optional[str]
    celex: Optional[str]
    item_id: Optional[str]
    date: Optional[date]
    kind: str
    value: str  # the identifier as stored on this case (keeps CJEU suffixes)

    def key(self):
        """Natural key for the link artifact."""
        out = {}
        if self.ecli:
            out["ecli"] = self.ecli
        elif self.celex:
            out["celex"] = self.celex
        elif self.item_id:
            out["item_id"] = self.item_id
        return out


@dataclass(frozen=True)
class Choice:
    candidate: Candidate
    rule: str
    confidence: float


def cjeu_kind(celex):
    """Document kind from a CELEX number's type letters (62017CJ0221 -> judgment)."""
    normalized = identifiers.normalize_celex(celex)
    if not normalized or not normalized.startswith("6"):
        return OTHER
    letters = normalized[5:7]
    if letters in ("CJ", "TJ", "FJ"):
        return CJEU_JUDGMENT
    if letters in ("CO", "TO", "FO"):
        return CJEU_ORDER
    if letters in ("CC", "TC"):
        return CJEU_OPINION
    return OTHER


def echr_kind(doctype):
    """HUDOC doctype -> judgment | decision | communicated | other."""
    code = (doctype or "").upper()
    if code in ("HEJUD", "HFJUD", "HJUD"):
        return ECHR_JUDGMENT
    if code in ("HEDEC", "HFDEC", "HDEC"):
        return ECHR_DECISION
    if code in ("HECOM", "HFCOM", "HCOM"):
        return ECHR_COMMUNICATED
    return OTHER


def _not_later(candidates, source_date):
    if source_date is None:
        return list(candidates)
    return [c for c in candidates if c.date is None or c.date <= source_date]


def choose_cjeu(
    candidates: Iterable[Candidate], source_date: Optional[date], opinion_cue: bool = False
) -> Optional[Choice]:
    pool = _not_later(candidates, source_date)
    order = (
        (CJEU_OPINION, CJEU_JUDGMENT, CJEU_ORDER) if opinion_cue else (CJEU_JUDGMENT, CJEU_ORDER)
    )
    for kind in order:
        same = sorted(
            (c for c in pool if c.kind == kind),
            key=lambda c: (c.date or date.max, c.celex or "", c.case_id),
        )
        if not same:
            continue
        rule = f"cjeu_{kind}" + (
            "_after_opinion_cue" if opinion_cue and kind != CJEU_OPINION else ""
        )
        confidence = 0.95 if kind == CJEU_JUDGMENT else 0.85
        if opinion_cue and kind == CJEU_OPINION:
            confidence = 0.9
        if len(same) > 1:
            rule += "_earliest_of_several"
            confidence -= 0.15
        return Choice(same[0], rule, round(confidence, 2))
    return None


def choose_echr(
    candidates: Iterable[Candidate],
    source_date: Optional[date],
    decision_cue: bool = False,
    cited_date: Optional[date] = None,
    cited_year: Optional[int] = None,
) -> Optional[Choice]:
    pool = [c for c in _not_later(candidates, source_date) if c.kind != ECHR_COMMUNICATED]
    judgments = [c for c in pool if c.kind == ECHR_JUDGMENT]
    decisions = [c for c in pool if c.kind == ECHR_DECISION]
    if decision_cue and decisions:
        kind_pool, base_rule, confidence = decisions, "echr_decision_cue", 0.95
    elif judgments:
        kind_pool, base_rule, confidence = judgments, "echr_judgment", 0.95
    elif decisions:
        kind_pool, base_rule, confidence = decisions, "echr_decision_no_judgment", 0.85
    else:
        return None
    kind_pool = sorted(kind_pool, key=lambda c: (c.date or date.max, c.item_id or "", c.case_id))
    if len(kind_pool) == 1:
        return Choice(kind_pool[0], base_rule, confidence)
    if cited_date is not None:
        exact = [c for c in kind_pool if c.date == cited_date]
        if exact:
            return Choice(exact[0], base_rule + "_cited_date", confidence)
    if cited_year is not None:
        same_year = [c for c in kind_pool if c.date is not None and c.date.year == cited_year]
        if same_year:
            return Choice(same_year[0], base_rule + "_cited_year", round(confidence - 0.05, 2))
    return Choice(kind_pool[0], base_rule + "_earliest_of_several", round(confidence - 0.2, 2))


_FETCH = f"""
    SELECT ci.value_normalized, ci.value, c.id, c.ecli, c.celex_id, c.item_id, c.date_decision,
           (SELECT d.doctype FROM {SCHEMA}.echr_document d
             WHERE d.case_id = c.id ORDER BY d.item_id LIMIT 1) AS doctype
      FROM {SCHEMA}.case_identifier ci
      JOIN {SCHEMA}.cases c ON c.id = ci.case_id
     WHERE ci.scheme = %s AND ci.value_normalized = ANY(%s)
"""


def fetch_candidates(cursor, scheme: str, values: Sequence[str]):
    """{normalized value: [Candidate, ...]} for one scheme, in one query."""
    values = sorted({v for v in values if v})
    if not values:
        return {}
    cursor.execute(_FETCH, (scheme, values))
    out = {}
    for (
        value_normalized,
        value,
        case_id,
        ecli,
        celex,
        item_id,
        decided,
        doctype,
    ) in cursor.fetchall():
        if scheme == "echr_appno":
            kind = echr_kind(doctype)
        else:
            kind = cjeu_kind(celex)
        out.setdefault(value_normalized, []).append(
            Candidate(case_id, ecli, celex, item_id, decided, kind, value)
        )
    return out
