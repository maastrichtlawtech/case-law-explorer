"""
Rechtspraak text extractor (roadmap R2.1).

Scans the stored texts of Rechtspraak decisions (case_text rows with source
'RECHTSPRAAK', both ``fulltext`` and ``summary``: art. 81 RO rulings such as
HR:2022:637 cite only in the summary) and writes link records in three
source datasets, all with relation 'cites':

  rs_text_ecli          full and short ECLIs of EU, ECtHR and Dutch decisions
                        ("ECLI:EU:C:2019:189", "EU:C:2019:189", "NL:HR:2020:593")
  rs_text_cjeu_casenum  CJEU, General Court and Civil Service Tribunal case
                        numbers ("C-221/17", "zaak 26/62", joined cases and
                        "tot en met" ranges)
  rs_text_echr_appno    ECtHR application numbers ("nr. 30979/96"), only in
                        texts that mention the ECtHR or the Convention

Rules (precision first; when unsure a reference is written unresolved or not
at all):

  * ECLIs resolve on cases.ecli, then case_identifier (scheme ecli); an ECLI
    this database does not hold is written with its ECLI as the target, so the
    loader stores it unresolved for late binding. Self-citations are skipped.
  * A case number needs a court letter followed by a hyphen of any kind
    ("C 199/12" with only a space needs a CJEU cue nearby), or, without a
    letter (cases before 1989), a "zaak"/"zaken"/"Case" cue right before it.
    The year must fit the court (C/T from 1989, F 2005-2016, no letter before
    1989) and not be later than the citing decision. Dutch case-number labels
    right before it ("zaaknummer", "rolnummer", "AWB", ...) reject it, and in
    a Caribbean context (Gemeenschappelijk Hof van Justitie, Caribbean court
    ECLIs) an explicit EU cue is required.
  * A case number is skipped only when an EU ECLI within 80 characters
    resolves to a case carrying the same case number (that ECLI is the
    citation); another case's ECLI nearby does not skip it (RBGEL:2026:1195).
  * Case numbers resolve through case_identifier with resolver.choose_cjeu:
    dated on or before the citing decision, judgments, then orders; an AG
    opinion only with a "conclusie van A-G"/"Opinion of Advocate General" cue
    in the same citation. Numbers nothing matches are written unresolved
    (target null, target_ref_raw normalised); numbers whose only candidates
    postdate the citing decision are dropped.
  * Application numbers need a number cue ("nr.", "no.", "klachtnummer",
    "application") and, for the generic "nr."/"no.", an ECtHR cue in the same
    citation; they resolve with resolver.choose_echr ("(dec.)" selects the
    decision; cited date, then cited year; "[GC]" is recorded).

One record per (source, target or reference, dataset), with every mention
(exact offsets into the stored text, the text as written, ~300 characters of
context). Reads only from the database it is given; never calls a remote
service.
"""

import argparse
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from data_extraction.linking import identifiers, resolver
from data_extraction.linking.artifact import CaseKey, LinkRecord, Mention, write_jsonl

log = logging.getLogger(__name__)

SCHEMA = resolver.SCHEMA
EXTRACTOR_VERSION = "rs_text/1.0.0"
TEXT_SOURCE = "RECHTSPRAAK"
RELATION = "cites"
DATASET_ECLI = "rs_text_ecli"
DATASET_CJEU = "rs_text_cjeu_casenum"
DATASET_ECHR = "rs_text_echr_appno"
TEXT_FIELDS = ("fulltext", "summary")

CONTEXT_CHARS = 150  # each side, so ~300 characters of context
NEAR_ECLI_CHARS = 80
MAX_RANGE = 50  # "C-1/90 tot en met C-60/90" is not a range we expand
BATCH_SIZE = 500

_HYPHEN = "[" + re.escape(identifiers.HYPHENS) + "]"
_SPACE = r"[    ]"

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Full or short ECLI of the three collections. Numbers are restricted per
# collection so trailing punctuation or text is never swallowed.
ECLI_RE = re.compile(
    r"(?<![A-Za-z0-9:])"
    r"(?:(?i:ecli)" + _SPACE + r"?:" + _SPACE + r"?)?"
    r"(?P<body>"
    r"EU:(?:C|T|F):\d{4}:\d{1,6}"
    r"|CE:ECHR:\d{4}:\d{4}[A-Z]{3}\d{9}"
    r"|NL:[A-Z]{2,7}:\d{4}:(?:[A-Z]{2}\d{4}|\d{1,6})"
    r")(?![A-Za-z0-9])"
)

# Cues before a letterless case number ("zaak 26/62", "Case 6/64").
_LETTERLESS_CUE_RE = re.compile(
    r"(?:\b(?:zaak|zaken|case|cases|affaire|affaires|aff\.|rechtssache|rechtssachen|rs\.)"
    r"|gevoegde zaken|joined cases)" + _SPACE + r"*$",
    re.I,
)
# Dutch case-number labels right before a match: not a CJEU number.
_DUTCH_NUMBER_LABEL_RE = re.compile(
    r"(?:zaaknummers?|zaaknrs?|rolnummers?|rolnrs?|parketnummers?|parketnrs?|"
    r"registratienummers?|procedurenummers?|kenmerk|ons kenmerk|uw kenmerk|dossiernummers?|"
    r"\bawb|\bbk|\bbrk)\.?:?" + _SPACE + r"*(?:nrs?\.?)?" + _SPACE + r"*$",
    re.I,
)
# Weak CJEU cue: enough for "C 199/12" written with a plain space.
_CJEU_CUE_RE = re.compile(
    r"Hof van Justitie|HvJ|Court of Justice|General Court|Gerecht|CJEU|\bECJ\b|CJUE|"
    r"Cour de justice|Tribunal|EU:[CTF]:|ECLI:EU|Jurispr|\bECR\b|Unie|\bzaak\b|\bzaken\b|"
    r"\bCase\b|\bCases\b|affaire|Rechtssache"
)
# Strong CJEU cue: needed in a Caribbean context, where "Hof van Justitie" is
# the Gemeenschappelijk Hof van Justitie of Aruba, Curacao, Sint Maarten and
# Bonaire, Sint Eustatius and Saba.
_STRONG_CJEU_CUE_RE = re.compile(
    r"Hof van Justitie van de Europese|Hof van Justitie EU|HvJ ?EU|HvJ ?EG|HvJEU|HvJEG|"
    r"Europese Unie|Europese Gemeenschap|Court of Justice of the European|CJEU|\bECJ\b|"
    r"EU:[CTF]:|ECLI:EU|Unierecht|EU-recht|EG-recht|Gerecht van de Europese|Gerecht EU"
)
_CARIBBEAN_TEXT_RE = re.compile(r"Gemeenschappelijk(?:e)? Hof", re.I)
_CARIBBEAN_COURTS = ("OGE", "OGH", "ORB")  # ECLI court codes of the Caribbean courts

# Connectors between case numbers.
_RANGE_RE = re.compile(r"^" + _SPACE + r"*(?:tot en met|t/m|t\.m\.|to|à|a|bis)" + _SPACE + r"*$")
_LIST_RE = re.compile(r"^" + _SPACE + r"*(?:,|en|and|et|und|e|y|&)" + _SPACE + r"*$")

# An AG opinion cue in the same citation.
_AG = (
    r"(?:A\.?" + _HYPHEN + r"?G\.?|AG|advoca(?:at|te)" + _HYPHEN + r"?" + _SPACE + r"?general|"
    r"advocaat" + _HYPHEN + r"generaal|advocate general|avocat général|avocate générale|"
    r"adv\.?" + _HYPHEN + r"?gen\.?|Generalanwalt|Generalanwältin)(?!\w)"
)
_OPINION_CUE_RE = re.compile(
    r"\b(?:conclusie|conclusies|opinion|conclusions|schlussanträge)\b"
    r"(?:\W+\w+){0,3}?\W+" + _AG + r"|\b" + _AG + r"\W+(?:\w+\W+){0,3}?"
    r"(?:conclusie|opinion|conclusions)\b",
    re.I,
)
# A judgment or order named in the citation after the opinion cue wins.
_JUDGMENT_CUE_RE = re.compile(
    r"\b(?:arrest|arresten|judgment|judgement|arrêt|urteil|beschikking|order|ordonnance|"
    r"beschluss)\b",
    re.I,
)

# ECtHR: text-level cue, number cue, citation-level cues.
_ECHR_TEXT_RE = re.compile(
    r"EHRM|EVRM|ECHR|ECtHR|EHRC|Europees Hof voor de Rechten van de Mens|"
    r"European Court of Human Rights|Cour européenne des droits de l'homme|"
    r"Europese Commissie voor de Rechten van de Mens"
)
_APPNO_RE = re.compile(
    r"(?P<cue>\b(?:(?P<specific>klachtnummers?|klachtnrs?\.?|klacht" + _SPACE + r"nrs?\.?|"
    r"applications?" + _SPACE + r"(?:nos?|nrs?)\.?|application|appl\.|app\." + _SPACE + r"no\.?|"
    r"requêtes?" + _SPACE + r"(?:nos?|n°)\.?|verzoekschrift" + _SPACE + r"nrs?\.?)"
    r"|nrs?\.?|nos?\.|n°)" + _SPACE + r"?:?" + _SPACE + r"?)"
    r"(?P<num>\d{1,6}/\d{2})(?![\d/])",
    re.I,
)
_APPNO_NEXT_RE = re.compile(
    _SPACE + r"*(?:,|en|and|et|&)" + _SPACE + r"*(?P<num>\d{1,6}/\d{2})(?![\d/])"
)
# Citation-level ECtHR cues. Not "EVRM" (the Convention itself, cited in most
# Dutch decisions) and no bare "tegen" ("bezwaar tegen het besluit nr. 12/34").
_ECHR_CITATION_CUE_RE = re.compile(
    r"EHRM|ECHR|ECtHR|EHRC|Europees Hof|European Court|Cour européenne|ECRM|EComHR|"
    r"Commissie voor de Rechten|Commission of Human Rights|Commission européenne des droits|"
    r"\b(?:v|vs|t|c)\.\s+(?:the\s+|het\s+|la\s+|le\s+|l')?[A-Z]|"
    r"\b(?:tegen|versus|contre)\s+(?:the\s+|het\s+|de\s+|la\s+|le\s+|l')?[A-Z]|"
    r"\((?:dec|déc|ontv)\.\)|\[GC\]|Grote Kamer|Grand Chamber|Grande Chambre"
)
_NOT_ECHR_RE = re.compile(r"Kamerstukken|Stb\.|Stcrt\.|Trb\.|Handelingen|Bijl\.", re.I)
_DECISION_CUE_RE = re.compile(
    r"\((?:dec|déc|ontv)\.?\)|\(beslissing\)|ontvankelijkheidsbeslissing|"
    r"admissibility decision|decision as to the admissibility|décision sur la recevabilité",
    re.I,
)
_GC_CUE_RE = re.compile(r"\[GC\]|\(GC\)|Grote Kamer|Grand Chamber|Grande Chambre")
_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("januari", "january", "janvier"),
            ("februari", "february", "février", "fevrier"),
            ("maart", "march", "mars"),
            ("april", "avril"),
            ("mei", "may", "mai"),
            ("juni", "june", "juin"),
            ("juli", "july", "juillet"),
            ("augustus", "august", "août", "aout"),
            ("september", "septembre"),
            ("oktober", "october", "octobre"),
            ("november", "novembre"),
            ("december", "décembre", "decembre"),
        ),
        start=1,
    )
    for name in names
}
_DATE_RE = re.compile(
    r"\b(?P<day>\d{1,2})(?:e|er|st|nd|rd|th)?"
    + _SPACE
    + r"+(?P<month>"
    + "|".join(sorted(_MONTHS, key=len, reverse=True))
    + r")"
    + _SPACE
    + r"+(?P<year>\d{4})\b",
    re.I,
)
_YEAR_RE = re.compile(r"\b(?:ECHR|Reports)" + _SPACE + r"+(?P<year>(?:19|20)\d{2})\b")

# ---------------------------------------------------------------------------
# Scanning (pure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    """One reference found in one text."""

    scheme: str  # ecli | cjeu_case_number | echr_appno
    value: str  # normalised
    text_field: str
    language: Optional[str]
    start: int
    end: int
    raw_text: str
    context: str
    opinion_cue: bool = False
    decision_cue: bool = False
    grand_chamber: bool = False
    cited_date: Optional[date] = None
    cited_year: Optional[int] = None
    suffix: Optional[str] = None  # "R" in "C-204/21 R"
    implied: bool = False  # a range member not written out ("C-200/12" in "C-199/12 t/m C-201/12")


@dataclass
class SourceCase:
    """A citing decision and its texts: (text_field, language, text) triples."""

    ecli: Optional[str]
    decision_date: Optional[date] = None
    texts: List[Tuple[str, Optional[str], str]] = field(default_factory=list)
    celex: Optional[str] = None
    item_id: Optional[str] = None

    def key(self):
        return CaseKey(ecli=self.ecli, celex=self.celex, item_id=self.item_id)


def _context(text, start, end):
    snippet = text[max(0, start - CONTEXT_CHARS) : end + CONTEXT_CHARS]
    return re.sub(r"\s+", " ", snippet).strip()


def _hit(scheme, value, text_field, language, text, start, end, **cues):
    return Hit(
        scheme=scheme,
        value=value,
        text_field=text_field,
        language=language,
        start=start,
        end=end,
        raw_text=text[start:end],
        context=_context(text, start, end),
        **cues,
    )


def scan_eclis(text, text_field="fulltext", language=None):
    """Full and short EU, ECtHR and Dutch ECLIs, in text order."""
    hits = []
    for match in ECLI_RE.finditer(text):
        value = identifiers.normalize_ecli(match.group("body"))
        if value:
            hits.append(_hit("ecli", value, text_field, language, text, match.start(), match.end()))
    return hits


def _year_ok(court, year2, max_year):
    """Does a two-digit year fit the court's numbering, and not postdate the citation?"""
    y = int(year2)
    if court:
        full = 1900 + y if y >= 50 else 2000 + y
        if court == "F" and not 2005 <= full <= 2016:
            return False
        if court in ("C", "T") and full < 1989:
            return False
    else:
        if not 53 <= y <= 88:
            return False
        full = 1900 + y
    return max_year is None or full <= max_year


def _clause_before(text, start, limit=120, stops=()):
    """Text before start, back to a newline, ';' or one of stops (offsets)."""
    lo = max(0, start - limit)
    for stop in stops:
        if lo < stop <= start:
            lo = stop
    window = text[lo:start]
    cut = max(window.rfind("\n"), window.rfind(";"))
    return window[cut + 1 :] if cut >= 0 else window


def _clause_after(text, end, limit=60, stops=()):
    hi = min(len(text), end + limit)
    for stop in stops:
        if end <= stop < hi:
            hi = stop
    window = text[end:hi]
    cuts = [i for i in (window.find("\n"), window.find(";")) if i >= 0]
    sentence = re.search(r"\.\s+[A-Z]", window)
    if sentence:
        cuts.append(sentence.start())
    return window[: min(cuts)] if cuts else window


def _has_opinion_cue(before, after):
    """An AG opinion cue in this citation, not overridden by a judgment/order cue
    between it and the case number ("conclusie van A-G X bij het arrest ..., C-1/20")."""
    cues = list(_OPINION_CUE_RE.finditer(before))
    if cues:
        return not _JUDGMENT_CUE_RE.search(before[cues[-1].end() :])
    cue = _OPINION_CUE_RE.search(after)
    return bool(cue) and not _JUDGMENT_CUE_RE.search(after[: cue.start()])


def scan_cjeu_case_numbers(
    text, text_field="fulltext", language=None, source_ecli=None, max_year=None
):
    """CJEU case numbers in text order, joined members and ranges expanded.

    max_year: the citing decision's year; later case numbers are not CJEU
    citations (or are typos) and are left out.
    """
    caribbean = bool(_CARIBBEAN_TEXT_RE.search(text)) or bool(
        source_ecli
        and len(source_ecli.split(":")) > 2
        and source_ecli.split(":")[2].startswith(_CARIBBEAN_COURTS)
    )
    raw = []  # (start, end, court, number, year2, has_hyphen)
    for match in identifiers.CJEU_CASE_NUMBER_RE.finditer(text):
        court = match.group("court") or ""
        if court:
            separator = text[match.start() + 1 : match.start("number")]
            if not separator:
                continue  # "C221/17": not a citation form
            has_hyphen = bool(re.search(_HYPHEN, separator))
        else:
            has_hyphen = False
            if match.start() > 0 and re.match(_HYPHEN + r"|\w", text[match.start() - 1]):
                continue  # "BC-12/13" falls back to "12/13": reject
        raw.append(
            (
                match.start(),
                match.end(),
                court,
                int(match.group("number")),
                match.group("year"),
                has_hyphen,
                match.group("suffix"),
            )
        )

    accepted = []  # (start, end, court, number, year2, suffix)
    previous = None
    for start, end, court, number, year2, has_hyphen, suffix in raw:
        before = text[max(0, start - 40) : start]
        between = text[previous[1] : start] if previous else None
        continues_list = previous is not None and bool(
            _LIST_RE.match(between) or _RANGE_RE.match(between)
        )
        if _DUTCH_NUMBER_LABEL_RE.search(before) and not continues_list:
            continue
        window = text[max(0, start - 150) : end + 150]
        if not court:
            if continues_list and previous[2]:
                court = previous[2]  # "C-6/90 en 9/90"
            elif not (_LETTERLESS_CUE_RE.search(before) or continues_list):
                continue
        elif not has_hyphen and not (continues_list or _CJEU_CUE_RE.search(window)):
            continue
        if not _year_ok(court, year2, max_year):
            continue
        if caribbean and not _STRONG_CJEU_CUE_RE.search(window):
            continue
        current = (start, end, court, number, year2, suffix)
        accepted.append(current)
        previous = current

    hits = []
    stops = [a[1] for a in accepted]
    for index, (start, end, court, number, year2, suffix) in enumerate(accepted):
        before = _clause_before(text, start, stops=[s for s in stops if s <= start])
        after = _clause_after(text, end, stops=[a[0] for a in accepted if a[0] >= end])
        opinion = _has_opinion_cue(before, after)
        value = identifiers.normalize_cjeu_case_number(
            f"{court}-{number}/{year2}" if court else f"{number}/{year2}"
        )
        hits.append(
            _hit(
                "cjeu_case_number",
                value,
                text_field,
                language,
                text,
                start,
                end,
                opinion_cue=opinion,
                suffix=suffix,
            )
        )
        # Range: "C-199/12 tot en met C-201/12" -> C-200/12, mention spans the range.
        if index + 1 < len(accepted):
            n_start, n_end, n_court, n_number, n_year2, _n_suffix = accepted[index + 1]
            if (
                n_court == court
                and n_year2 == year2
                and 0 < n_number - number <= MAX_RANGE
                and _RANGE_RE.match(text[end:n_start])
            ):
                for middle in range(number + 1, n_number):
                    value = identifiers.normalize_cjeu_case_number(
                        f"{court}-{middle}/{year2}" if court else f"{middle}/{year2}"
                    )
                    hits.append(
                        _hit(
                            "cjeu_case_number",
                            value,
                            text_field,
                            language,
                            text,
                            start,
                            n_end,
                            opinion_cue=opinion,
                            implied=True,
                        )
                    )
    return hits


def _cited_date(before, after):
    dates = list(_DATE_RE.finditer(before))
    match = dates[-1] if dates else _DATE_RE.search(after)
    if not match:
        return None
    try:
        return date(
            int(match.group("year")), _MONTHS[match.group("month").lower()], int(match.group("day"))
        )
    except ValueError:
        return None


def scan_echr_appnos(text, text_field="fulltext", language=None):
    """ECtHR application numbers, only in texts that mention the ECtHR or the ECHR."""
    if not _ECHR_TEXT_RE.search(text):
        return []
    found = {}  # start -> (start, end, specific cue)
    for match in _APPNO_RE.finditer(text):
        specific = bool(match.group("specific"))
        found.setdefault(match.start("num"), (match.start("num"), match.end("num"), specific))
        position = match.end("num")
        while True:  # "nrs. 30562/04 en 30566/04"
            follow = _APPNO_NEXT_RE.match(text, position)
            if not follow:
                break
            found.setdefault(
                follow.start("num"), (follow.start("num"), follow.end("num"), specific)
            )
            position = follow.end("num")
    found = [found[k] for k in sorted(found)]

    hits = []
    starts = [f[0] for f in found]
    ends = [f[1] for f in found]
    for start, end, specific in found:
        value = identifiers.normalize_echr_appno(text[start:end])
        if value is None:
            continue
        near_before = text[max(0, start - 60) : start]
        if _NOT_ECHR_RE.search(near_before):
            continue
        citation_before = text[max(0, start - 200) : start]
        citation_after = text[end : end + 100]
        if not specific and not (
            _ECHR_CITATION_CUE_RE.search(citation_before)
            or _ECHR_CITATION_CUE_RE.search(citation_after)
        ):
            continue
        # Cues of this citation only: back to the previous application number's
        # citation boundary, forward to the next number.
        before = _clause_before(text, start, limit=150, stops=[e for e in ends if e <= start])
        after = _clause_after(text, end, limit=80, stops=[s for s in starts if s > start])
        cited = _cited_date(before, after)
        year = _YEAR_RE.search(before + " " + after)
        hits.append(
            _hit(
                "echr_appno",
                value,
                text_field,
                language,
                text,
                start,
                end,
                decision_cue=bool(
                    _DECISION_CUE_RE.search(before) or _DECISION_CUE_RE.search(after)
                ),
                grand_chamber=bool(_GC_CUE_RE.search(before) or _GC_CUE_RE.search(after)),
                cited_date=cited,
                cited_year=int(year.group("year")) if year else (cited.year if cited else None),
            )
        )
    return hits


def scan_case(source: SourceCase) -> List[Hit]:
    """Every reference in every text of one citing decision (no resolution)."""
    max_year = source.decision_date.year if source.decision_date else None
    hits = []
    for text_field, language, text in source.texts:
        if not text or text_field not in TEXT_FIELDS:
            continue
        hits.extend(scan_eclis(text, text_field, language))
        hits.extend(
            scan_cjeu_case_numbers(text, text_field, language, source.ecli, max_year=max_year)
        )
        hits.extend(scan_echr_appnos(text, text_field, language))
    return hits


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


class StaticLookup:
    """In-memory lookup for unit tests and the evaluation run.

    eclis: {normalised ECLI: Candidate}; cjeu / echr: {normalised value: [Candidate]}.
    """

    def __init__(self, eclis=None, cjeu=None, echr=None):
        self._eclis = dict(eclis or {})
        self._by_scheme = {"cjeu_case_number": dict(cjeu or {}), "echr_appno": dict(echr or {})}

    def prefetch(self, hits):
        pass

    def ecli(self, value):
        return self._eclis.get(value)

    def candidates(self, scheme, value):
        return list(self._by_scheme[scheme].get(value, ()))


_FETCH_ECLI = f"""
    SELECT c.ecli AS value, 0 AS via_identifier, c.id, c.ecli, c.celex_id, c.item_id,
           c.date_decision
      FROM {SCHEMA}.cases c
     WHERE c.ecli = ANY(%s)
    UNION ALL
    SELECT ci.value_normalized, 1, c.id, c.ecli, c.celex_id, c.item_id, c.date_decision
      FROM {SCHEMA}.case_identifier ci
      JOIN {SCHEMA}.cases c ON c.id = ci.case_id
     WHERE ci.scheme = 'ecli' AND ci.value_normalized = ANY(%s)
     ORDER BY 1, 2, 3
"""


class DbLookup:
    """Lookups against the database the extractor is pointed at, one query per
    scheme per batch (prefetch)."""

    def __init__(self, cursor):
        self.cursor = cursor
        self._eclis = {}
        self._by_scheme = {"cjeu_case_number": {}, "echr_appno": {}}

    def prefetch(self, hits):
        eclis = sorted({h.value for h in hits if h.scheme == "ecli"})
        self._eclis = {}
        if eclis:
            self.cursor.execute(_FETCH_ECLI, (eclis, eclis))
            for value, _via, case_id, ecli, celex, item_id, decided in self.cursor.fetchall():
                # Ordered so a direct cases.ecli match wins over an alias.
                self._eclis.setdefault(
                    value,
                    resolver.Candidate(case_id, ecli, celex, item_id, decided, "case", value),
                )
        for scheme in self._by_scheme:
            values = sorted({h.value for h in hits if h.scheme == scheme})
            self._by_scheme[scheme] = resolver.fetch_candidates(self.cursor, scheme, values)

    def ecli(self, value):
        return self._eclis.get(value)

    def candidates(self, scheme, value):
        return list(self._by_scheme[scheme].get(value, ()))


# ---------------------------------------------------------------------------
# Resolution (pure, given a lookup)
# ---------------------------------------------------------------------------


@dataclass
class _Pending:
    dataset: str
    target: Optional[CaseKey]
    ref_raw: Optional[str]
    ref_scheme: Optional[str]
    match_method: str
    confidence: Optional[float]
    mentions: list = field(default_factory=list)
    first: Tuple = ()


def _mention(hit: Hit):
    return Mention(
        text_field=hit.text_field,
        raw_text=hit.raw_text,
        language=hit.language,
        text_source=TEXT_SOURCE,
        char_start=hit.start,
        char_end=hit.end,
        context=hit.context,
    )


def _is_source(candidate, source: SourceCase):
    key = candidate.key()
    return bool(key) and CaseKey(**key) == source.key()


# Suffixes that name a separate document of the case (interim relief, costs,
# rectification, interpretation, revision, third-party proceedings, legal aid,
# default judgments): never taken for the judgment, and only chosen when cited.
SEPARATE_SUFFIXES = frozenset(("R", "RX", "REC", "DEP", "AJ", "TO", "INT", "REV", "OP", "SA"))


def _suffix_of(candidate):
    parts = identifiers.parse_cjeu_case_number(candidate.value)
    return parts[3] if parts else None


def _suffix_pool(candidates, cited_suffix):
    """Candidates matching the cited suffix: "C-204/21 R" -> the R order only;
    a plain or "P"/"PPU" number -> the documents without a separate suffix,
    or every candidate when the number has nothing else."""
    if cited_suffix in SEPARATE_SUFFIXES:
        return [c for c in candidates if _suffix_of(c) == cited_suffix]
    plain = [c for c in candidates if _suffix_of(c) not in SEPARATE_SUFFIXES]
    return plain or list(candidates)


def resolve_case(source: SourceCase, hits: Sequence[Hit], lookup, stats=None) -> List[LinkRecord]:
    """Turn one decision's hits into link records (one per target or reference)."""
    stats = stats if stats is not None else Counter()
    pending: Dict[tuple, _Pending] = {}
    source_key = source.key()

    def add(dataset, target, ref_raw, ref_scheme, method, confidence, hit):
        key = (
            dataset,
            tuple(sorted(target.to_dict().items())) if target else (ref_scheme, ref_raw),
        )
        order = (hit.text_field, hit.start)
        entry = pending.get(key)
        if entry is None:
            entry = pending[key] = _Pending(
                dataset, target, ref_raw, ref_scheme, method, confidence, first=order
            )
        else:
            if (confidence or 0) > (entry.confidence or 0):
                entry.match_method, entry.confidence = method, confidence
            if order < entry.first:
                entry.first = order
                if ref_raw is not None:
                    entry.ref_raw = ref_raw
        entry.mentions.append(_mention(hit))

    # ECLIs (and the case each EU ECLI resolves to, for the nearby-ECLI rule).
    eu_ecli_cases = []  # (text_field, language, start, end, case_id)
    for hit in (h for h in hits if h.scheme == "ecli"):
        if source.ecli and hit.value == source.ecli:
            stats["ecli_self"] += 1
            continue
        candidate = lookup.ecli(hit.value)
        if candidate is None:
            target, method, confidence = CaseKey(ecli=hit.value), "ecli", 1.0
            stats["ecli_not_in_db"] += 1
        else:
            if _is_source(candidate, source):
                stats["ecli_self"] += 1
                continue
            target = CaseKey(**candidate.key())
            method = "ecli" if candidate.ecli == hit.value else "ecli_identifier"
            confidence = 1.0
            if hit.value.startswith("ECLI:EU:"):
                eu_ecli_cases.append(
                    (hit.text_field, hit.language, hit.start, hit.end, candidate.case_id)
                )
            stats["ecli_resolved"] += 1
        add(DATASET_ECLI, target, None, None, method, confidence, hit)

    def near_same_case(hit, candidates):
        ids = {c.case_id for c in candidates}
        for text_field, language, start, end, case_id in eu_ecli_cases:
            if (text_field, language) != (hit.text_field, hit.language) or case_id not in ids:
                continue
            gap = max(start - hit.end, hit.start - end, 0)
            if gap <= NEAR_ECLI_CHARS:
                return True
        return False

    for hit in (h for h in hits if h.scheme == "cjeu_case_number"):
        candidates = lookup.candidates("cjeu_case_number", hit.value)
        if candidates and near_same_case(hit, candidates):
            stats["cjeu_skipped_near_ecli"] += 1
            continue
        pool = _suffix_pool(candidates, hit.suffix)
        if candidates and not pool:
            stats["cjeu_suffix_not_found"] += 1
            continue
        choice = resolver.choose_cjeu(pool, source.decision_date, opinion_cue=hit.opinion_cue)
        if choice is None:
            if candidates:
                stats["cjeu_only_later_candidates"] += 1
                continue
            if hit.implied:
                stats["cjeu_range_member_unresolved"] += 1
                continue
            stats["cjeu_unresolved"] += 1
            add(DATASET_CJEU, None, hit.value, "cjeu_case_number", "case_number", None, hit)
            continue
        if _is_source(choice.candidate, source):
            continue
        stats["cjeu_resolved"] += 1
        add(
            DATASET_CJEU,
            CaseKey(**choice.candidate.key()),
            hit.value,
            "cjeu_case_number",
            choice.rule,
            choice.confidence,
            hit,
        )

    for hit in (h for h in hits if h.scheme == "echr_appno"):
        candidates = lookup.candidates("echr_appno", hit.value)
        choice = resolver.choose_echr(
            candidates,
            source.decision_date,
            decision_cue=hit.decision_cue,
            cited_date=hit.cited_date,
            cited_year=hit.cited_year,
        )
        if choice is None:
            if any(c.kind != resolver.ECHR_COMMUNICATED for c in candidates):
                stats["echr_only_later_candidates"] += 1
                continue
            stats["echr_unresolved"] += 1
            add(DATASET_ECHR, None, hit.value, "echr_appno", "appno", None, hit)
            continue
        if _is_source(choice.candidate, source):
            continue
        rule, confidence = choice.rule, choice.confidence
        if hit.grand_chamber and rule.endswith("_earliest_of_several"):
            # "[GC]" with several judgments and no date: the earliest may be the
            # Chamber judgment the Grand Chamber reviewed. Keep it, but say so.
            rule, confidence = rule + "_gc_cited", round(confidence - 0.1, 2)
        stats["echr_resolved"] += 1
        add(
            DATASET_ECHR,
            CaseKey(**choice.candidate.key()),
            hit.value,
            "echr_appno",
            rule,
            confidence,
            hit,
        )

    records = []
    for entry in pending.values():
        mentions = sorted(
            entry.mentions, key=lambda m: (m.text_field, m.language or "", m.char_start)
        )
        unique = []
        for mention in mentions:
            if not unique or mention != unique[-1]:
                unique.append(mention)
        record = LinkRecord(
            source=source_key,
            relation_type=RELATION,
            source_dataset=entry.dataset,
            extractor_version=EXTRACTOR_VERSION,
            target=entry.target,
            target_ref_raw=entry.ref_raw,
            target_ref_scheme=entry.ref_scheme if entry.ref_raw else None,
            match_method=entry.match_method,
            confidence=entry.confidence,
            mentions=tuple(unique),
        )
        record.validate()
        records.append(record)
    return records


def extract_records(source: SourceCase, lookup, stats=None) -> List[LinkRecord]:
    """Pure entry point: one decision's texts and metadata -> link records."""
    hits = scan_case(source)
    lookup.prefetch(hits)
    return resolve_case(source, hits, lookup, stats)


# ---------------------------------------------------------------------------
# Database entry point
# ---------------------------------------------------------------------------

_CASE_PAGE = f"""
    SELECT DISTINCT ct.case_id
      FROM {SCHEMA}.case_text ct
     WHERE ct.source = %(text_source)s
       AND (ct.fulltext IS NOT NULL OR ct.summary IS NOT NULL)
       AND ct.case_id > %(after)s
       AND (%(to_id)s::bigint IS NULL OR ct.case_id <= %(to_id)s::bigint)
       AND (%(case_ids)s::bigint[] IS NULL OR ct.case_id = ANY(%(case_ids)s::bigint[]))
     ORDER BY ct.case_id
     LIMIT %(limit)s
"""
_CASE_TEXTS = f"""
    SELECT c.id, c.ecli, c.celex_id, c.item_id, c.date_decision,
           ct.language, ct.fulltext, ct.summary
      FROM {SCHEMA}.case_text ct
      JOIN {SCHEMA}.cases c ON c.id = ct.case_id
     WHERE ct.source = %(text_source)s AND ct.case_id = ANY(%(ids)s)
     ORDER BY c.id, ct.language, ct.id
"""


def _sources(rows):
    cases = {}
    for case_id, ecli, celex, item_id, decided, language, fulltext, summary in rows:
        source = cases.get(case_id)
        if source is None:
            source = cases[case_id] = SourceCase(ecli, decided, [], celex, item_id)
        if fulltext:
            source.texts.append(("fulltext", language, fulltext))
        if summary:
            source.texts.append(("summary", language, summary))
    return list(cases.values())


def iter_batches(conn, case_ids=None, id_range=None, batch_size=BATCH_SIZE):
    """Yield lists of SourceCase, keyset-paged on case_id (~batch_size cases)."""
    after, to_id = -1, None
    if id_range is not None:
        from_id, to_id = id_range
        after = (from_id - 1) if from_id is not None else -1
    ids = sorted({int(i) for i in case_ids}) if case_ids is not None else None
    with conn.cursor() as cursor:
        while True:
            cursor.execute(
                _CASE_PAGE,
                {
                    "text_source": TEXT_SOURCE,
                    "after": after,
                    "to_id": to_id,
                    "case_ids": ids,
                    "limit": batch_size,
                },
            )
            page = [row[0] for row in cursor.fetchall()]
            if not page:
                return
            cursor.execute(_CASE_TEXTS, {"text_source": TEXT_SOURCE, "ids": page})
            yield _sources(cursor.fetchall())
            after = page[-1]


def extract(conn, case_ids=None, id_range=None, out_path=None, batch_size=BATCH_SIZE):
    """Scan the RS texts of the given cases (all when both are None) and write
    the link artifact to out_path. Returns (records written, stats Counter)."""
    stats = Counter()
    records = []
    for batch in iter_batches(conn, case_ids, id_range, batch_size):
        scanned = [(source, scan_case(source)) for source in batch if source.ecli]
        stats["sources"] += len(batch)
        stats["sources_without_ecli"] += len(batch) - len(scanned)
        with conn.cursor() as cursor:
            lookup = DbLookup(cursor)
            lookup.prefetch([hit for _source, hits in scanned for hit in hits])
            for source, hits in scanned:
                records.extend(resolve_case(source, hits, lookup, stats))
        conn.rollback()  # read-only; end the snapshot between batches
    for record in records:
        stats["records_" + record.source_dataset] += 1
        stats["mentions_" + record.source_dataset] += len(record.mentions)
    written = write_jsonl(records, out_path) if out_path else len(records)
    log.info("rs_text: %d records; %s", written, dict(sorted(stats.items())))
    return written, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dsn-env", required=True, help="environment variable holding the DSN")
    parser.add_argument("--from-id", type=int, default=None, help="first cases.id (inclusive)")
    parser.add_argument("--to-id", type=int, default=None, help="last cases.id (inclusive)")
    parser.add_argument("--out", required=True, help="JSONL artifact to write")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args(argv)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f"environment variable {args.dsn_env} is not set")
    import psycopg2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = psycopg2.connect(dsn)
    try:
        conn.set_session(readonly=True)
        id_range = None
        if args.from_id is not None or args.to_id is not None:
            id_range = (args.from_id, args.to_id)
        written, stats = extract(
            conn, id_range=id_range, out_path=args.out, batch_size=args.batch_size
        )
    finally:
        conn.close()
    print(f"{written} records -> {args.out}")
    for key, value in sorted(stats.items()):
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
