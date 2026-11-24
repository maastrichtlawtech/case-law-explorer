"""
Cellar referral data -> links between Dutch decisions and CJEU rulings (R2.3).

Cellar's ``national_judgement`` notice (``cjeu_document.national_judgement_xml``)
lists the national decisions of the proceedings behind a CJEU ruling, one
``<p>`` per decision:

    <p>** AFFAIRE C-199/12 **</p>
    <p>*A9* Raad van State, afdeling bestuursrechtspraak, uitspraak van 18/04/2012
       (201012342/T1/V2)</p>
    <p>*P1* Raad van State, ..., uitspraak van 18/12/2013 (201012342/T1/V2)</p>

Line codes and the relation each one becomes:

    *A9*        the referring decision        -> preliminary_reference
    *A1*-*A8*   earlier national instances    -> earlier_instance
    *P1*, *P2*  decisions after the ruling    -> national_follow_up
    *I1*, ...   interim decisions             -> skipped (no relation type is
                                                 defined for them; counted)

Direction. Every link goes from the Dutch decision (source) to the CJEU
document that carries the notice (target), whatever the line code; the
relation type says what role the national decision played in the CJEU case.
So an earlier instance links to the ruling directly, not to the referring
decision: that keeps it independent of whether the *A9* line resolves, and
the Dutch court hierarchy is already linked by the RS formal relations.

Matching a line to a Rechtspraak decision, in order:

    1. an ECLI written in the line, or in the rechtspraak.nl link on the line
       right after it ("ECLI:NL:HR:2016:994", "(NL:CBB:2018:1)")
       -> match_method 'ecli' ('ecli/ecli_inconsistent' when the line's court
       does not fit the ECLI);
    2. an LJN written in the line ("LJN BU1290") on a decision of that date
       and court -> 'ljn';
    3. date + court + zaaknummer: decisions dated on the line's date, of a
       compatible court, whose zaaknummer (rs_document.zaaknummer and the
       case_identifier 'nl_zaaknummer' values) equals one of the line's
       numbers, in any of the forms of identifiers.zaaknummer_variants; then,
       only if no exact number matched, on the numeric core of the numbers
       ('10/719 WW' = '10/719 WW-P', '07/12617' = '07/12617bis', at least
       four digits); then on the leading case number
       ("201012342/T1/V2" = "201012342/1/V2": the Raad van State reuses the
       referral's number for the decision after the ruling) when it has at
       least six digits -> 'metadata';
    4. with REFERRAL_DATE_COURT_FALLBACK (off by default; precision not
       measured): the only decision of a compatible court on that date
       -> 'metadata' with confidence 0.6.

Rules:

  * Foreign courts. Only the court part of each line (before the date) is
    classified, never the whole line (parse_match.py L17 tested the whole
    line, so a Belgian court followed by a Dutch place, or a Dutch court
    after "Rechtbank van eerste aanleg", leaked through). A line is used only
    when its court part starts with a recognised Dutch court and, for the
    district courts and courts of appeal, names a Dutch court seat;
    anything Belgian-looking in the court part rejects it.
  * HR vs PHR. A line naming the Hoge Raad matches instance 'Hoge Raad' only,
    never the Parket's conclusions (same zaaknummer, often the same date),
    unless the line names the Procureur-Generaal / Advocaat-Generaal or a
    conclusie; then only the Parket.
  * Duplicate publications (decision D2). Decisions of one court on one date
    with the same zaaknummer are one decision published more than once
    (RVS:2012:BW3076 = RVS:2012:4057, and 4059 its English translation).
    They resolve to one canonical case: drop translations (rs_document.language
    other than Dutch) first, then take the ECLI with an LJN-style number (the
    original publication; numeric ECLIs for decisions before 2013 are
    re-publications), then the earliest date_published, then the lowest ECLI.
    Candidates that differ in instance or zaaknummer are different decisions:
    the line is ambiguous and skipped.
  * Dates. A referral or earlier instance after the ruling, or a follow-up
    before it, contradicts the notice: skipped and counted.
  * Never guess: a line with several distinct candidate decisions, or none,
    is counted and skipped. (The source side is the unknown one, so it cannot
    be written as an unresolved row.)

Artifact: source_dataset 'cellar_national_judgement', one record per
(Dutch decision, CJEU document, relation), with one mention per line
(text_field 'national_judgement_xml', raw_text the line with HTML entities
decoded, char_start/char_end the line's span in the stored XML, which is on
the target document; section the line code, e.g. 'A9'; context the
'AFFAIRE C-199/12' heading of joined cases).

CLI:
    python -m data_extraction.linking.cellar_referrals --dsn-env VAR \
        [--from-id N] [--to-id M] --out PATH [--date-court-fallback]
"""

import argparse
import html
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote

from data_extraction.linking import identifiers
from data_extraction.linking.artifact import (
    ArtifactWriter,
    CaseKey,
    LinkRecord,
    Mention,
    match_method,
)

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
SOURCE_DATASET = "cellar_national_judgement"
EXTRACTOR_VERSION = "cellar_referrals/1.0.0"
TEXT_FIELD = "national_judgement_xml"
BATCH_SIZE = 500

# Off by default: matching on date + court alone was not hand-checked.
REFERRAL_DATE_COURT_FALLBACK = os.environ.get("REFERRAL_DATE_COURT_FALLBACK", "").lower() in (
    "1",
    "true",
    "yes",
)

PRELIMINARY_REFERENCE = "preliminary_reference"
EARLIER_INSTANCE = "earlier_instance"
NATIONAL_FOLLOW_UP = "national_follow_up"

CONFIDENCE = {
    "ecli": 0.99,
    "ecli_inconsistent": 0.85,
    "ljn": 0.97,
    "zaaknummer": 0.95,
    "zaaknummer_core": 0.9,
    "zaaknummer_base": 0.9,
    "date_court": 0.6,
}
# Lowered when the decision is the canonical one of several publications.
DUPLICATE_PENALTY = 0.03

# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

_P_RE = re.compile(r"<p>(.*?)</p>", re.S)
_AFFAIRE_RE = re.compile(r"^\*\*\s*AFFAIRE\s+(.*?)\s*\*\*$")
_TAG_RE = re.compile(r"^\*([AIP])(\d*)\*\s*(.*)$", re.S)
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_ECLI_NL_RE = re.compile(r"(?<![A-Z])(?:ECLI:)?NL:[A-Z]{2,7}:\d{4}:[A-Z0-9]{1,25}", re.I)
_LJN_RE = re.compile(r"\bLJN\s*:?\s*([A-Z]{2}\d{4})\b", re.I)
_TOKEN_SPLIT_RE = re.compile(r";|,|\s+et\s+|\s+en\s+|\s+and\s+|\s+-\s+|\s+\+\s+", re.I)
_ALPHA_PREFIX_RE = re.compile(r"^([A-Z]{2,5})[-.]?(\d.*)$")
_CONCLUSION_RE = re.compile(r"procureur[- ]generaal|advocaat[- ]generaal|conclusie|parket", re.I)


@dataclass(frozen=True)
class ReferralLine:
    """One *A*/*P*/*I* line of a national_judgement notice."""

    letter: str  # A | P | I
    number: Optional[int]
    raw_text: str  # the line, HTML entities decoded
    char_start: int  # span of the line in the stored XML
    char_end: int
    affaire: Optional[str]
    decided: Optional[date]
    court: str  # the court part: everything before the date
    tokens: Tuple[str, ...] = ()  # zaaknummers in the brackets, normalised
    eclis: Tuple[str, ...] = ()
    ljns: Tuple[str, ...] = ()

    @property
    def code(self):
        return f"{self.letter}{self.number if self.number is not None else ''}"

    @property
    def relation_type(self):
        if self.letter == "A":
            return PRELIMINARY_REFERENCE if self.number == 9 else EARLIER_INSTANCE
        if self.letter == "P":
            return NATIONAL_FOLLOW_UP
        return None


def _parse_date(text):
    match = _DATE_RE.search(text)
    if not match:
        return None, None
    day, month, year = (int(g) for g in match.groups())
    try:
        return date(year, month, day), match
    except ValueError:
        return None, None


def _eclis(text):
    out = []
    for match in _ECLI_NL_RE.finditer(unquote(text)):
        ecli = identifiers.normalize_ecli(match.group(0))
        if ecli and ecli not in out:
            out.append(ecli)
    return tuple(out)


def _tokens(bracket):
    """Zaaknummers in the bracket after the date, normalised; ECLIs and LJNs
    are taken out first."""
    text = _ECLI_NL_RE.sub(" ", bracket)
    text = _LJN_RE.sub(" ", text)
    out = []
    for part in _TOKEN_SPLIT_RE.split(text):
        token = identifiers.normalize_zaaknummer(part)
        if token and len(token) >= 4 and re.search(r"\d", token) and token not in out:
            out.append(token)
    return tuple(out)


def parse_notice(xml: Optional[str]) -> List[ReferralLine]:
    """All *A*/*P*/*I* lines of one notice, in order."""
    if not xml:
        return []
    paragraphs = []
    for match in _P_RE.finditer(xml):
        inner = match.group(1)
        lead = len(inner) - len(inner.lstrip())
        text = html.unescape(inner).strip()
        start = match.start(1) + lead
        end = match.start(1) + len(inner.rstrip())
        paragraphs.append((text, start, end))

    lines = []
    affaire = None
    for index, (text, start, end) in enumerate(paragraphs):
        affaire_match = _AFFAIRE_RE.match(text)
        if affaire_match:
            affaire = affaire_match.group(1)
            continue
        tag = _TAG_RE.match(text)
        if not tag:
            continue
        letter, number, rest = tag.groups()
        decided, date_match = _parse_date(rest)
        cut, resume = (date_match.start(), date_match.end()) if date_match else (len(rest), None)
        court = rest[:cut]
        after = rest[resume:] if resume is not None else ""
        bracket = re.search(r"\((.*)\)", after, re.S)
        bracket_text = bracket.group(1) if bracket else ""
        eclis = list(_eclis(rest))
        # The notice often follows a line with its rechtspraak.nl link.
        if index + 1 < len(paragraphs):
            following = paragraphs[index + 1][0]
            if not _TAG_RE.match(following) and re.search(r"rechtspraak\.nl", following, re.I):
                for ecli in _eclis(following):
                    if ecli not in eclis:
                        eclis.append(ecli)
        ljns = tuple(dict.fromkeys(m.upper() for m in _LJN_RE.findall(rest)))
        lines.append(
            ReferralLine(
                letter=letter,
                number=int(number) if number else None,
                raw_text=text,
                char_start=start,
                char_end=end,
                affaire=affaire,
                decided=decided,
                court=court.strip(" ,"),
                tokens=_tokens(bracket_text),
                eclis=tuple(eclis),
                ljns=ljns,
            )
        )
    return lines


# ---------------------------------------------------------------------------
# courts
# ---------------------------------------------------------------------------

HR, PHR, RVS, CRVB, CBB, TC, BNL, GH, RB = (
    "Hoge Raad",
    "Parket bij de Hoge Raad",
    "Raad van State",
    "Centrale Raad van Beroep",
    "College van Beroep voor het bedrijfsleven",
    "Tariefcommissie",
    "Benelux Gerechtshof",
    "Gerechtshof",
    "Rechtbank",
)
NATIONAL_INSTANCES = (HR, PHR, RVS, CRVB, CBB, TC, BNL)

# Court seats as Rechtspraak spells them in rs_document.instance (lower case),
# with the spellings Cellar uses mapped onto them.
_SEAT_ALIASES = {
    "den haag": "den haag",
    "'s-gravenhage": "den haag",
    "s-gravenhage": "den haag",
    "'s gravenhage": "den haag",
    "den bosch": "'s-hertogenbosch",
    "'s-hertogenbosch": "'s-hertogenbosch",
    "s-hertogenbosch": "'s-hertogenbosch",
    "'s hertogenbosch": "'s-hertogenbosch",
}
_SEATS = (
    "alkmaar",
    "almelo",
    "amsterdam",
    "arnhem-leeuwarden",
    "arnhem",
    "assen",
    "breda",
    "dordrecht",
    "gelderland",
    "groningen",
    "haarlem",
    "leeuwarden",
    "limburg",
    "maastricht",
    "middelburg",
    "midden-nederland",
    "noord-holland",
    "noord-nederland",
    "oost-brabant",
    "oost-nederland",
    "overijssel",
    "roermond",
    "rotterdam",
    "utrecht",
    "zeeland-west-brabant",
    "zutphen",
    "zwolle-lelystad",
    "zwolle",
    "den haag",
    "'s-hertogenbosch",
)

# Anything in the court part that is Belgian (or otherwise not Dutch) rules
# the line out, even when a Dutch court word appears too.
_FOREIGN_RE = re.compile(
    r"belg|brussel|bruxelles|antwerpen|\bgent\b|li[eè]ge|leuven|brugge|mechelen|hasselt|"
    r"kortrijk|tongeren|turnhout|oudenaarde|dendermonde|ieper|veurne|nijvel|eupen|"
    r"cassatie|grondwettelijk|arbitragehof|arbeidshof|arbeidsrechtbank|"
    r"ondernemingsrechtbank|koophandel|correctionele|politierechtbank|vredegerecht|"
    r"hof van beroep|van (?:eerste|1e) aanleg|vreemdelingenbetwistingen|"
    r"nederlandstalige|franstalige|"
    r"aruba|cura[cç]ao|sint maarten|nederlandse antillen|gemeenschappelijk hof|"
    r"luxemb|conseil|tribunal|cour\b",
    re.I,
)
_ROLE_RE = re.compile(
    r"^(?:de\s+)?(?:president|voorzieningenrechter|kantonrechter|politierechter|"
    r"economische politierechter|meervoudige kamer|enkelvoudige kamer)\s+"
    r"(?:van|in|bij)\s+(?:de\s+|het\s+)?",
    re.I,
)


@dataclass(frozen=True)
class Court:
    kind: str  # one of HR, PHR, RVS, CRVB, CBB, TC, GH, RB
    seat: Optional[str] = None


def _seat(text):
    lowered = text.lower().replace("’", "'")
    for alias, seat in _SEAT_ALIASES.items():
        if re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", lowered):
            return seat
    for seat in _SEATS:
        if re.search(r"(?<![\w-])" + re.escape(seat) + r"(?![\w-])", lowered):
            return seat
    return None


def classify_court(court_part: str) -> Optional[Court]:
    """The Dutch court named at the start of a line's court part, or None
    when it is foreign or not recognised."""
    text = re.sub(r"\s+", " ", (court_part or "").replace("’", "'")).strip(" ,")
    head = _ROLE_RE.sub("", text)
    first = head.split(",", 1)[0].strip()
    # The Benelux Court of Justice is in the Rechtspraak corpus (ECLI:NL:XX).
    if re.match(
        r"(?:benelux gerechtshof|cour de justice benelux|cour de justice / gerechtshof)",
        first.lower(),
    ):
        return Court(BNL)
    # Only the court's name decides; chamber labels after it ("Eerste aanleg -
    # meervoudig") are Rechtspraak's own wording.
    if not first or _FOREIGN_RE.search(first):
        return None
    lowered = first.lower()
    if re.match(r"(?:parket bij de |procureur[- ]generaal bij de )hoge raad", lowered):
        return Court(PHR)
    if lowered.startswith("hoge raad"):
        return Court(PHR if _CONCLUSION_RE.search(text) else HR)
    if re.match(r"(?:afdeling bestuursrechtspraak van de |voorzitter .*?)?raad van state", lowered):
        return Court(RVS)
    if lowered.startswith("afdeling bestuursrechtspraak"):
        return Court(RVS)
    if lowered.startswith("centrale raad van beroep"):
        return Court(CRVB)
    if lowered.startswith("college van beroep voor het bedrijfsleven"):
        return Court(CBB)
    if lowered.startswith("tariefcommissie"):
        return Court(TC)
    if re.match(r"gerechtshof\b|hof\s", lowered):
        seat = _seat(first)
        return Court(GH, seat) if seat else None
    if re.match(r"(?:arrondissements)?rechtbank\b|kantongerecht\b", lowered):
        seat = _seat(first)
        return Court(RB, seat) if seat else None
    return None


def court_matches(court: Court, instance: Optional[str]) -> bool:
    """Is rs_document.instance a decision of this court?"""
    if not instance:
        return False
    lowered = instance.lower().replace("’", "'")
    if court.kind in NATIONAL_INSTANCES:
        return lowered == court.kind.lower()
    if court.kind == GH:
        if not lowered.startswith("gerechtshof"):
            return False
    elif court.kind == RB:
        if not (lowered.startswith("rechtbank") or lowered.startswith("kantongerecht")):
            return False
    return _seat(lowered) == court.seat


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RsCandidate:
    """A Rechtspraak decision that a line may name."""

    ecli: str
    decided: Optional[date]
    instance: Optional[str]
    zaaknummer: Optional[str] = None  # rs_document.zaaknummer as stored
    language: Optional[str] = None
    published: Optional[date] = None
    identifiers: Tuple[str, ...] = ()  # case_identifier nl_zaaknummer values
    ljns: Tuple[str, ...] = ()

    def cores(self):
        out = set()
        for part in [self.zaaknummer or ""] + list(self.identifiers):
            out.update(number_cores(part))
        return out

    def numbers(self):
        """Every normalised form of every zaaknummer of this decision."""
        out = set()
        raw = [p for p in _TOKEN_SPLIT_RE.split(self.zaaknummer or "")] + list(self.identifiers)
        for part in raw:
            out.update(number_forms(part))
        return out


def number_forms(value) -> set:
    """A zaaknummer in all the forms it is matched under: normalised, with
    and without the Raad van State instance segment, and without a letter
    prefix such as 'AWB' or 'HAA'."""
    base = identifiers.normalize_zaaknummer(value)
    if not base:
        return set()
    forms = set(identifiers.zaaknummer_variants(base))
    prefixed = _ALPHA_PREFIX_RE.match(base)
    if prefixed:
        forms.update(identifiers.zaaknummer_variants(prefixed.group(2)))
    return {f for f in forms if len(f) >= 4}


_CORE_RE = re.compile(r"\d+(?:[./-]\d+)*")


def number_cores(value) -> set:
    """The numeric cores of a zaaknummer with at least four digits:
    'AWB 00/392A' -> {'00/392'}, '10/719 WW-P' -> {'10/719'},
    'C/09/450182 / HA ZA 13-999' -> {'09/450182', '13-999'}. Rechtspraak often
    adds letters to the number Cellar gives ('07/12617bis', 'AWB 04/866-II')."""
    text = identifiers.normalize_zaaknummer(value) or ""
    return {c for c in _CORE_RE.findall(text) if sum(ch.isdigit() for ch in c) >= 4}


def _base_number(value):
    """The leading case number when it has at least six digits
    ('201012342/T1/V2' -> '201012342'), else None."""
    head = (value or "").split("/", 1)[0]
    return head if re.fullmatch(r"\d{6,}", head) else None


def _is_translation(candidate):
    return (candidate.language or "nl").strip().lower() not in ("nl", "nld", "dut", "")


def _ljn_style(ecli):
    return bool(re.fullmatch(r"[A-Z]{2}\d{4}", (ecli or "").rsplit(":", 1)[-1]))


def canonical(candidates: Sequence[RsCandidate]) -> Tuple[Optional[RsCandidate], int]:
    """One decision from candidates that are publications of the same
    decision (decision D2), with the number of publications; (None, n) when
    they are different decisions."""
    unique = {c.ecli: c for c in candidates}
    pool = sorted(unique.values(), key=lambda c: c.ecli)
    if not pool:
        return None, 0
    if len(pool) == 1:
        return pool[0], 1
    first = pool[0]
    same_decision = all(
        (c.instance or "").lower() == (first.instance or "").lower()
        and c.decided == first.decided
        and c.numbers() == first.numbers()
        and c.numbers()
        for c in pool
    )
    if not same_decision:
        return None, len(pool)
    originals = [c for c in pool if not _is_translation(c)] or pool
    chosen = min(
        originals,
        key=lambda c: (not _ljn_style(c.ecli), c.published or date.max, c.ecli),
    )
    return chosen, len(pool)


@dataclass(frozen=True)
class Match:
    ecli: str
    method: str  # artifact match_method: ecli | ljn | metadata
    rule: str  # key of CONFIDENCE
    confidence: float


def _ecli_court_consistent(ecli, court, decided):
    parts = ecli.split(":")
    code, year = parts[2], parts[3]
    if decided is not None and str(decided.year) != year:
        return False
    if court is None:
        return False
    expected = {
        HR: ("HR",),
        PHR: ("PHR",),
        RVS: ("RVS",),
        CRVB: ("CRVB",),
        CBB: ("CBB",),
        TC: ("DETARCO", "TC"),
        BNL: ("XX",),
    }.get(court.kind)
    if expected:
        return code in expected
    if court.kind == GH:
        return code.startswith("GH")
    return code.startswith("RB") or code.startswith("KG")


def match_line(
    line: ReferralLine,
    candidates: Iterable[RsCandidate],
    date_court_fallback: bool = False,
) -> Tuple[Optional[Match], str]:
    """Resolve one line to one Rechtspraak decision.

    candidates are the decisions dated on the line's date (any court; the
    court is checked here). Returns (Match, 'ok') or (None, reason).
    """
    court = classify_court(line.court)
    if line.eclis:
        if len(line.eclis) > 1:
            return None, "several_eclis"
        ecli = line.eclis[0]
        if _ecli_court_consistent(ecli, court, line.decided):
            return Match(ecli, "ecli", "ecli", CONFIDENCE["ecli"]), "ok"
        if court is None and _FOREIGN_RE.search((line.court or "").split(",", 1)[0]):
            return None, "foreign_or_unknown_court"
        return Match(ecli, "ecli", "ecli_inconsistent", CONFIDENCE["ecli_inconsistent"]), "ok"
    if court is None:
        return None, "foreign_or_unknown_court"
    if line.decided is None:
        return None, "no_date"
    pool = [c for c in candidates if c.decided == line.decided and court_matches(court, c.instance)]
    if not pool:
        return None, "no_decision_that_day"

    if line.ljns:
        wanted = set(line.ljns)
        hits = [
            c
            for c in pool
            if wanted
            & (set(c.ljns) | ({c.ecli.rsplit(":", 1)[-1]} if _ljn_style(c.ecli) else set()))
        ]
        chosen, n = canonical(hits)
        if chosen is not None:
            return _match(chosen, "ljn", "ljn", n), "ok"
        if hits:
            return None, "ambiguous"

    tokens = set()
    for token in line.tokens:
        tokens.update(number_forms(token))
    if tokens:
        hits = [c for c in pool if tokens & c.numbers()]
        rule = "zaaknummer"
        if not hits:
            cores = set()
            for token in line.tokens:
                cores.update(number_cores(token))
            hits = [c for c in pool if cores & c.cores()]
            rule = "zaaknummer_core"
        if not hits:
            bases = {_base_number(t) for t in line.tokens} - {None}
            hits = [c for c in pool if bases & {_base_number(n) for n in c.numbers()}]
            rule = "zaaknummer_base"
        if hits:
            chosen, n = canonical(hits)
            if chosen is None:
                return None, "ambiguous"
            return _match(chosen, "metadata", rule, n), "ok"

    if date_court_fallback:
        chosen, n = canonical(pool)
        if chosen is not None:
            return _match(chosen, "metadata", "date_court", n), "ok"
        return None, "ambiguous_date_court"
    return None, "no_zaaknummer_match" if line.tokens else "no_zaaknummer"


def _match(candidate, method, rule, publications):
    confidence = CONFIDENCE[rule] - (DUPLICATE_PENALTY if publications > 1 else 0)
    return Match(candidate.ecli, method, rule, round(confidence, 2))


@dataclass(frozen=True)
class CjeuDocument:
    """The CJEU document whose notice is parsed (the link target)."""

    ecli: Optional[str]
    celex: Optional[str]
    decided: Optional[date]
    xml: Optional[str]

    def key(self):
        return CaseKey(ecli=self.ecli) if self.ecli else CaseKey(celex=self.celex)


def _dates_consistent(line, target_date):
    if target_date is None or line.decided is None:
        return True
    if line.letter == "A":
        return line.decided <= target_date
    if line.letter == "P":
        return line.decided >= target_date
    return True


def links_for_document(
    document: CjeuDocument,
    candidates: Iterable[RsCandidate],
    stats: Optional[Counter] = None,
    date_court_fallback: bool = False,
) -> List[LinkRecord]:
    """LinkRecords for one CJEU document; reasons for skipped lines are
    counted in stats."""
    stats = stats if stats is not None else Counter()
    if not (document.ecli or document.celex):
        stats["document_without_key"] += 1
        return []
    candidates = list(candidates)
    merged: Dict[Tuple[str, str], dict] = {}
    for line in parse_notice(document.xml):
        stats["lines"] += 1
        relation = line.relation_type
        if relation is None:
            stats["interim_skipped"] += 1
            continue
        match, reason = match_line(line, candidates, date_court_fallback)
        if match is None:
            stats[reason] += 1
            continue
        if not _dates_consistent(line, document.decided):
            stats["date_inconsistent"] += 1
            continue
        stats[f"matched_{match.rule}"] += 1
        mention = Mention(
            text_field=TEXT_FIELD,
            raw_text=line.raw_text,
            char_start=line.char_start,
            char_end=line.char_end,
            context=f"AFFAIRE {line.affaire}" if line.affaire else None,
            section=line.code,
        )
        slot = merged.setdefault((match.ecli, relation), {"match": match, "mentions": []})
        if match.confidence > slot["match"].confidence:
            slot["match"] = match
        if mention not in slot["mentions"]:
            slot["mentions"].append(mention)

    records = []
    target = document.key()
    for (ecli, relation), slot in sorted(merged.items()):
        source = CaseKey(ecli=ecli)
        if source == target:
            continue
        records.append(
            LinkRecord(
                source=source,
                target=target,
                relation_type=relation,
                source_dataset=SOURCE_DATASET,
                extractor_version=EXTRACTOR_VERSION,
                match_method=match_method(slot["match"].method, slot["match"].rule),
                confidence=slot["match"].confidence,
                mentions=tuple(slot["mentions"]),
            )
        )
    return records


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------

_DOCUMENTS = f"""
    SELECT c.id, c.ecli, coalesce(d.celex_id, c.celex_id), c.date_decision,
           d.national_judgement_xml
      FROM {SCHEMA}.cjeu_document d
      JOIN {SCHEMA}.cases c ON c.id = d.case_id
     WHERE d.national_judgement_xml IS NOT NULL
       AND c.id > %(after)s
       AND (%(from_id)s::bigint IS NULL OR c.id >= %(from_id)s)
       AND (%(to_id)s::bigint IS NULL OR c.id <= %(to_id)s)
       AND (%(case_ids)s::bigint[] IS NULL OR c.id = ANY(%(case_ids)s))
     ORDER BY c.id
     LIMIT %(limit)s
"""

_CANDIDATES = f"""
    SELECT c.ecli, r.date_decision, r.instance, r.zaaknummer, r.language, r.date_published,
           ARRAY(SELECT ci.value_normalized FROM {SCHEMA}.case_identifier ci
                  WHERE ci.case_id = c.id AND ci.scheme = 'nl_zaaknummer'),
           ARRAY(SELECT ci.value_normalized FROM {SCHEMA}.case_identifier ci
                  WHERE ci.case_id = c.id AND ci.scheme = 'ljn'),
           r.replaces_identifier
      FROM {SCHEMA}.rs_document r
      JOIN {SCHEMA}.cases c ON c.id = r.case_id
     WHERE r.date_decision = ANY(%(dates)s::date[])
       AND c.ecli IS NOT NULL
       AND (r.instance = ANY(%(instances)s) OR r.instance LIKE 'Gerechtshof%%'
            OR r.instance LIKE 'Rechtbank%%' OR r.instance LIKE 'Kantongerecht%%')
"""


def fetch_candidates(cursor, dates: Iterable[date]) -> Dict[date, List[RsCandidate]]:
    dates = sorted({d for d in dates if d is not None})
    if not dates:
        return {}
    cursor.execute(_CANDIDATES, {"dates": dates, "instances": list(NATIONAL_INSTANCES)})
    out: Dict[date, List[RsCandidate]] = {}
    for (
        ecli,
        decided,
        instance,
        zaaknummer,
        language,
        published,
        zk,
        ljns,
        replaces,
    ) in cursor.fetchall():
        ljn_values = set(ljns or ())
        for part in re.split(r"[,;\s]+", replaces or ""):
            ljn = identifiers.normalize_ljn(part)
            if ljn:
                ljn_values.add(ljn)
        out.setdefault(decided, []).append(
            RsCandidate(
                ecli=ecli,
                decided=decided,
                instance=instance,
                zaaknummer=zaaknummer,
                language=language,
                published=published,
                identifiers=tuple(zk or ()),
                ljns=tuple(sorted(ljn_values)),
            )
        )
    return out


def _needed_dates(lines):
    return {
        line.decided
        for line in lines
        if line.relation_type and not line.eclis and line.decided and classify_court(line.court)
    }


def iter_documents(conn, case_ids=None, id_range=None, batch_size=BATCH_SIZE):
    """Batches of CjeuDocument by keyset on cases.id."""
    from_id, to_id = id_range if id_range else (None, None)
    after = 0
    while True:
        with conn.cursor() as cursor:
            cursor.execute(
                _DOCUMENTS,
                {
                    "after": after,
                    "from_id": from_id,
                    "to_id": to_id,
                    "case_ids": list(case_ids) if case_ids is not None else None,
                    "limit": batch_size,
                },
            )
            rows = cursor.fetchall()
        if not rows:
            return
        after = rows[-1][0]
        yield [CjeuDocument(ecli, celex, decided, xml) for _id, ecli, celex, decided, xml in rows]


def extract(
    conn,
    case_ids=None,
    id_range=None,
    out_path=None,
    date_court_fallback: Optional[bool] = None,
    batch_size: int = BATCH_SIZE,
):
    """Write the artifact for the CJEU documents selected by case_ids or
    id_range (cases.id, inclusive); returns (records written, stats)."""
    if date_court_fallback is None:
        date_court_fallback = REFERRAL_DATE_COURT_FALLBACK
    stats: Counter = Counter()
    with ArtifactWriter(out_path) as writer:
        for batch in iter_documents(conn, case_ids, id_range, batch_size):
            parsed = [(document, parse_notice(document.xml)) for document in batch]
            dates = set()
            for _document, lines in parsed:
                dates |= _needed_dates(lines)
            with conn.cursor() as cursor:
                by_date = fetch_candidates(cursor, dates)
            conn.rollback()  # read-only; end the snapshot between batches
            records: List[LinkRecord] = []
            for document, lines in parsed:
                stats["documents"] += 1
                candidates = [c for line in lines for c in by_date.get(line.decided, ())]
                records.extend(links_for_document(document, candidates, stats, date_court_fallback))
            writer.write(records)
    written = writer.count
    stats["records"] = written
    log.info("cellar_referrals: %s", dict(sorted(stats.items())))
    return written, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("--from-id", type=int)
    parser.add_argument("--to-id", type=int)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--date-court-fallback",
        action="store_true",
        default=REFERRAL_DATE_COURT_FALLBACK,
        help="also match on date + court alone (precision not measured)",
    )
    args = parser.parse_args(argv)
    import psycopg2

    logging.basicConfig(level=logging.INFO)
    conn = psycopg2.connect(os.environ[args.dsn_env])
    try:
        conn.set_session(readonly=True)
        id_range = None
        if args.from_id is not None or args.to_id is not None:
            id_range = (args.from_id, args.to_id)
        written, stats = extract(
            conn, id_range=id_range, out_path=args.out, date_court_fallback=args.date_court_fallback
        )
    finally:
        conn.close()
    print(f"{written} records -> {args.out}; {dict(sorted(stats.items()))}")


if __name__ == "__main__":
    main()
