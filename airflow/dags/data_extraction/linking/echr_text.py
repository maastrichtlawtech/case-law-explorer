"""
ECtHR text -> CJEU and Rechtspraak links (roadmap R2.2).

Scans HUDOC texts (case_text with source 'HUDOC', and the other HUDOC
variants of the same case in echr_document_secondary_text) and writes two
link datasets:

echr_text_cjeu
    CJEU, General Court and Civil Service Tribunal case numbers ("C-199/12",
    "C 199/12", "C‑199/12" with U+2011, "T-254/17", "Case 26/62"), joined
    cases and ranges ("C-199/12 to C-201/12": the lead case; another listed
    member only when it resolves to a judgment of its own), and EU ECLIs, with
    or without the "ECLI:" prefix. An EU ECLI written in the same citation as
    case numbers wins over the case-number guess (the research hand check's
    misses: an AG opinion or a judgment chosen where the ECLI named the right
    document). Case numbers resolve through case_identifier with
    resolver.choose_cjeu; an AG opinion is chosen only when "Opinion" /
    "conclusions" is written just before the citation.
echr_text_rs
    Dutch ECLIs and LJNs ("LJN BR0132", "LJN: BJ3435"). LJNs resolve through
    case_identifier scheme 'ljn' (filled from rs_document.replaces_identifier);
    an LJN shared by the Hoge Raad and its Advocate General (HR / PHR) goes to
    the court's decision unless "conclusie"/"conclusion"/"opinion" is written
    before it; anything still ambiguous is written unresolved.

Decision D4 (references inside the domestic-law parts of a judgment). Every
mention records the section of the judgment it was found in (mention.section):
'procedure', 'facts', 'domestic_law', 'legal_framework', 'eu_international_law',
'law', 'operative', 'separate_opinion' or None when unknown. Sections come
from echr_extractor_segments when the database has segments for the
document, refined by the judgment's own headings ("THE LAW", "RELEVANT
DOMESTIC LAW", "RELEVANT LEGAL FRAMEWORK", "EN DROIT", ...). With the flag
ECHR_DOMESTIC_LAW_RELATION on (the default), links found only in the facts
(where the ECtHR reports the domestic courts' reasoning) or in the domestic
legal framework get relation_type 'cites_in_domestic_law', so they stay out of
the default citation counts; a target that is also cited elsewhere in the
judgment gets a 'cites' row as well. With the flag off every link is 'cites'.

Pure entry point: ``extract_text(unit, source, lookup)`` for one text.
Database entry point: ``extract(conn, case_ids=None, id_range=None, out_path=...)``.
CLI: ``python -m data_extraction.linking.echr_text --dsn-env VAR --from-id N
--to-id M --out PATH`` (PATH a directory -> one file per source_dataset).
"""

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from data_extraction.linking import identifiers, resolver
from data_extraction.linking.artifact import CaseKey, LinkRecord, match_method
from data_extraction.linking.text_common import (
    CandidateLookup,
    PendingLink,
    Source,
    TextUnit,
    build_records,
    cli_args,
    connect,
    env_flag,
    iter_case_batches,
    mention,
    write_artifact,
)

log = logging.getLogger(__name__)

EXTRACTOR_VERSION = "echr_text/1.0.0"
DATASET_CJEU = "echr_text_cjeu"
DATASET_RS = "echr_text_rs"
DATASETS = (DATASET_CJEU, DATASET_RS)
RELATION = "cites"
RELATION_DOMESTIC = "cites_in_domestic_law"
DOMESTIC_FLAG = "ECHR_DOMESTIC_LAW_RELATION"
SCHEMA = resolver.SCHEMA
HUDOC = "HUDOC"
HUDOC_SECONDARY = "HUDOC_SECONDARY"

CONF_ECLI = 0.99
CONF_ECLI_CONFLICT = 0.8

DOMESTIC_SECTIONS = ("facts", "domestic_law", "legal_framework")

_H = "[" + re.escape(identifiers.HYPHENS) + "]"
_S = r"[    ]"

# ---------------------------------------------------------------------------
# CJEU case numbers and EU ECLIs
# ---------------------------------------------------------------------------

EU_ECLI_RE = re.compile(r"(?<![\w:])(?:ECLI:)?EU:[CTF]:\d{4}:\d{1,6}(?![\w:])")
# Keyword that lets a case number without a court letter ("Case 26/62") count.
_CASE_WORD_RE = re.compile(
    r"(?:\b(?:Cases?|Joined Cases|affaires?|aff\.|Rechtssachen?|Rs\.|zaak|zaken|causa|"
    r"cause|asunto|asuntos|sprawa|sprawie)\s*)$",
    re.I,
)
_APPNO_MARK_RE = re.compile(r"(?:\b(?:nos?|n°|nº|Nr|application|requête)\.?\s*)$", re.I)
# What may stand between two case numbers of one citation (a list or a range).
_LIST_SEP_RE = re.compile(
    r"^[\s,]*(?:(?P<word>and|et|und|en|e|y|i|a|to|à|au|bis|tot en met|t/m)\b[\s,]*)?"
    r"(?:(?:Joined\s+)?Cases?\s+|affaires?\s+|Rechtssachen?\s+)?$",
    re.I,
)
_RANGE_WORDS = {"to", "à", "au", "bis", "tot en met", "t/m", "a"}
# An EU ECLI right after the case numbers belongs to the same citation.
_FOLLOWING_ECLI_RE = re.compile(
    r"[\s,;:(\[]{0,6}(?P<ecli>(?:ECLI:)?EU:[CTF]:\d{4}:\d{1,6})(?![\w:])"
)
_SENTENCE_END_RE = re.compile(r"(?:[.;!?][\"”’)]?\s+(?=[A-Z0-9“\"(«])|\n)")
_OPINION_CUE_RE = re.compile(
    r"\bOpinion\b|\bopinion\s+of\s+(?:the\s+)?Advocate[\s-]General\b|\bconclusions\b|"
    r"\bSchlussanträgen?\b|\bconclusie\b|\bconclusioni\b|\bconclusiones\b|\bopinii\b",
)
_JUDGMENT_WORD_RE = re.compile(
    r"\b(?:judgments?|judgements?|ruling|order|arrêts?|ordonnance|Urteils?|Beschlusses|"
    r"Beschluss|arrest|uitspraak|beschikking|sentenza|ordinanza|sentencia|auto|wyrok|"
    r"postanowienie)\b",
    re.I,
)


@dataclass
class NumberMention:
    start: int
    end: int
    normalized: str
    suffix: Optional[str]
    written: bool = True  # False for a member implied by a range ("to")


@dataclass
class CjeuCitation:
    numbers: List[NumberMention]
    ecli: Optional[Tuple[int, int, str]] = None  # start, end, normalized
    opinion_cue: bool = False


@dataclass
class Scan:
    citations: List[CjeuCitation] = field(default_factory=list)
    eu_eclis: List[Tuple[int, int, str]] = field(default_factory=list)  # not in a citation
    nl_eclis: List[Tuple[int, int, str]] = field(default_factory=list)
    ljns: List[Tuple[int, int, str, bool]] = field(default_factory=list)  # +opinion cue

    def case_numbers(self):
        return {n.normalized for c in self.citations for n in c.numbers}

    def ljn_values(self):
        return {value for _s, _e, value, _cue in self.ljns}


# Domestic file numbers that look like "C 123/05": Polish "I C 123/05",
# "sygn. akt XXV C 1234/10".
_DOMESTIC_PREFIX_RE = re.compile(r"(?:\b[IVXL]{1,5}|\d|\bsygn\.?(?:\s*akt)?|\bakt)\s*$", re.I)
_CJEU_CUE_RE = re.compile(
    r"CJEU|CJUE|CJEC|CJCE|Court of Justice|Cour de justice|EuGH|Gerichtshof der Europäischen|"
    r"Hof van Justitie|HvJ|Corte di giustizia|Tribunal de Justicia|TSUE|General Court|"
    r"Tribunal de l[’']Union|ECLI:EU|\bEU:[CTF]:|\b(?:Joined )?Cases?\b|\baffaires?\b|"
    r"\bRechtssache|\bgevoegde\b|\bzaak\b",
    re.I,
)


def _number_matches(text):
    out = []
    for match in identifiers.CJEU_CASE_NUMBER_RE.finditer(text):
        before = text[max(0, match.start() - 25) : match.start()]
        if match.group("court") is None:
            # "Case 26/62" only; a bare "17341/03" is an application number.
            if not _CASE_WORD_RE.search(before) or _APPNO_MARK_RE.search(before):
                continue
        else:
            if _DOMESTIC_PREFIX_RE.search(before):
                continue
            written = match.group(0)
            if not re.search(_H, written):
                # "C 199/12" without a hyphen: only next to a CJEU cue.
                window = text[max(0, match.start() - 300) : match.end() + 200]
                if not _CJEU_CUE_RE.search(window):
                    continue
        normalized = identifiers.normalize_cjeu_case_number(match.group(0))
        if normalized is None:
            continue
        out.append((match, normalized))
    return out


_ABBREVIATIONS = {
    "v", "vs", "no", "nos", "nr", "p", "pp", "para", "paras", "cf", "e.g", "i.e", "mr", "mrs",
    "ms", "dr", "art", "arts", "op", "cit", "ibid", "c", "rec", "ecr", "itd", "al", "st", "co",
}  # fmt: skip


def _sentence_start(window):
    """Offset in window after the last real sentence end (not 'v.', 'no.', initials)."""
    start = 0
    for match in _SENTENCE_END_RE.finditer(window):
        if window[match.start()] == ".":
            word = re.search(r"([\w.]+)$", window[: match.start()])
            token = (word.group(1) if word else "").lower()
            if token in _ABBREVIATIONS or len(token) == 1:
                continue
        start = match.end()
    return start


def _opinion_cue(text, start):
    window = text[max(0, start - 160) : start]
    window = window[_sentence_start(window) :]
    last_cue = max((m.end() for m in _OPINION_CUE_RE.finditer(window)), default=-1)
    last_judgment = max((m.end() for m in _JUDGMENT_WORD_RE.finditer(window)), default=-1)
    return last_cue > last_judgment


def _expand_range(first: NumberMention, last: NumberMention, text):
    """Members strictly between two written numbers of a range, same court and year."""
    a = identifiers.parse_cjeu_case_number(text[first.start : first.end])
    b = identifiers.parse_cjeu_case_number(text[last.start : last.end])
    if not a or not b or a[0] != b[0] or a[2] != b[2] or not 0 < b[1] - a[1] <= 20:
        return []
    court, year = a[0], a[2]
    prefix = f"{court}-" if court else ""
    return [
        NumberMention(first.start, first.end, f"{prefix}{n}/{year}", None, written=False)
        for n in range(a[1] + 1, b[1])
    ]


def scan_cjeu(text: str) -> Tuple[List[CjeuCitation], List[Tuple[int, int, str]]]:
    """Case-number citations (with an ECLI of the same citation) and other EU ECLIs."""
    citations: List[CjeuCitation] = []
    used_eclis = set()
    group: List[NumberMention] = []
    group_end = None

    def close():
        nonlocal group
        if not group:
            return
        citation = CjeuCitation(numbers=group, opinion_cue=_opinion_cue(text, group[0].start))
        following = _FOLLOWING_ECLI_RE.match(text, group_end)
        if following:
            ecli = identifiers.normalize_ecli(following.group("ecli"))
            if ecli:
                citation.ecli = (following.start("ecli"), following.end("ecli"), ecli)
                used_eclis.add(following.start("ecli"))
        citations.append(citation)
        group = []

    for match, normalized in _number_matches(text):
        suffix = match.group("suffix")
        number = NumberMention(match.start(), match.end(), normalized, suffix)
        if group:
            between = text[group_end : match.start()]
            sep = _LIST_SEP_RE.match(between) if len(between) <= 40 else None
            if sep:
                word = (sep.group("word") or "").lower()
                if word in _RANGE_WORDS and group[-1].written:
                    group.extend(_expand_range(group[-1], number, text))
                group.append(number)
                group_end = match.end()
                continue
            close()
        group = [number]
        group_end = match.end()
    close()

    eclis = []
    for match in EU_ECLI_RE.finditer(text):
        if match.start() in used_eclis:
            continue
        ecli = identifiers.normalize_ecli(match.group(0))
        if ecli:
            eclis.append((match.start(), match.end(), ecli))
    return citations, eclis


# ---------------------------------------------------------------------------
# Dutch ECLIs and LJNs
# ---------------------------------------------------------------------------

NL_ECLI_RE = re.compile(r"(?<![\w:])ECLI:NL:[A-Z0-9]{2,7}:\d{4}:[A-Z0-9]{1,25}(?![\w:])", re.I)
_LJN_RE = re.compile(
    r"\bLJN(?:[\s-]*(?:nr\.?|nummer|number|no\.?))?\s*[:.]?\s*"
    r"(?P<list>[A-Z]{2}\d{4}(?:\s*(?:,|;|and|en|et|und)\s*[A-Z]{2}\d{4})*)\b"
)
_LJN_ITEM_RE = re.compile(r"[A-Z]{2}\d{4}")
_NL_OPINION_CUE_RE = re.compile(
    r"\b(?:conclusie|conclusion|conclusions|opinion|Advocate[\s-]General|advocaat[\s-]generaal|"
    r"avocat général)\b",
    re.I,
)


def scan_rs(text: str):
    eclis = []
    for match in NL_ECLI_RE.finditer(text):
        ecli = identifiers.normalize_ecli(match.group(0))
        if ecli:
            eclis.append((match.start(), match.end(), ecli))
    ljns = []
    for match in _LJN_RE.finditer(text):
        cue = bool(_NL_OPINION_CUE_RE.search(text[max(0, match.start() - 80) : match.start()]))
        for item in _LJN_ITEM_RE.finditer(match.group("list")):
            start = match.start("list") + item.start()
            value = identifiers.normalize_ljn(item.group(0))
            if value:
                ljns.append((start, start + 6, value, cue))
    return eclis, ljns


def scan(text: str) -> Scan:
    citations, eu_eclis = scan_cjeu(text)
    nl_eclis, ljns = scan_rs(text)
    return Scan(citations=citations, eu_eclis=eu_eclis, nl_eclis=nl_eclis, ljns=ljns)


# ---------------------------------------------------------------------------
# Sections (decision D4)
# ---------------------------------------------------------------------------

_UPPER_RUN_RE = re.compile(
    r"(?<![\w’'])(?:[A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý’'\-]*\s+){1,11}[A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý’'\-]*(?![\w’'])"
)
_HEADING_RULES = (
    ("operative", re.compile(r"^(?:FOR THESE REASONS|PAR CES MOTIFS)\b")),
    (
        "separate_opinion",
        re.compile(
            r"\b(?:CONCURRING|DISSENTING|SEPARATE|PARTLY)\b.*\bOPINION\b|"
            r"\bOPINION\s+(?:CONCORDANTE|DISSIDENTE|SÉPARÉE|EN PARTIE)"
        ),
    ),
    (
        "eu_international_law",
        re.compile(
            r"\b(?:EUROPEAN UNION|EU LAW|COURT OF JUSTICE|INTERNATIONAL\s+(?:LAW|MATERIAL|TEXTS|"
            r"INSTRUMENTS|AND\s+EUROPEAN)|COUNCIL OF EUROPE|COMPARATIVE\s+(?:LAW|MATERIAL)|"
            r"DROIT\s+(?:DE\s+L[’']UNION|INTERNATIONAL|COMPARÉ|EUROPÉEN)|TEXTES\s+INTERNATIONAUX|"
            r"INTERNATIONAUX\s+PERTINENTS|UNION\s+EUROPÉENNE)\b"
        ),
    ),
    (
        "domestic_law",
        re.compile(
            r"\b(?:DOMESTIC|NATIONAL)\s+(?:LAW|LEGISLATION|PRACTICE|LEGAL)|"
            r"\bDROIT\s+(?:ET\s+(?:LA\s+)?PRATIQUE\s+)?INTERNES?\b|\bINTERNES?\s+PERTINENT"
        ),
    ),
    (
        "legal_framework",
        re.compile(
            r"\b(?:LEGAL FRAMEWORK|CADRE JURIDIQUE|RELEVANT LAW|DROIT PERTINENT|"
            r"RELEVANT LEGISLATION)\b"
        ),
    ),
    ("law", re.compile(r"^(?:[IVX]+\.?\s+)?(?:THE LAW|EN DROIT|AS TO THE LAW|IN LAW)$")),
    (
        "facts",
        re.compile(
            r"^(?:[IVX]+\.?\s+)?(?:THE FACTS|EN FAIT|AS TO THE FACTS|"
            r"THE CIRCUMSTANCES OF THE CASE|LES CIRCONSTANCES DE L[’']ESPÈCE)$"
        ),
    ),
    ("procedure", re.compile(r"^(?:[IVX]+\.?\s+)?(?:PROCEDURE|PROCÉDURE)$")),
)
# Mixed-case subheadings inside a legal-framework part ("B. European Union law").
_SUBHEADING_RE = re.compile(
    r"(?<![\w.])(?:[A-H]|[IVX]{1,4}|\d{1,2})\.\s+(?:The\s+)?(?:Relevant\s+)?"
    r"(?:(?P<eu>European\s+Union|EU\s+law|Union\s+law|International|Council\s+of\s+Europe|"
    r"Comparative|Case-law\s+of\s+the\s+Court\s+of\s+Justice|"
    r"(?:Decisions|Judgments)\s+of\s+the\s+Court\s+of\s+Justice|Droit\s+de\s+l[’']Union|"
    r"Droit\s+international|Textes\s+internationaux|Jurisprudence\s+de\s+la\s+Cour\s+de\s+justice)"
    r"|(?P<nl>Domestic|National\s+law|Droit\s+interne|Droit\s+national|Le\s+droit\s+interne))"
)
_UNNUMBERED_EU_HEADING_RE = re.compile(
    r"(?:Case-law|Decisions|Judgments)\s+of\s+the\s+Court\s+of\s+Justice[^.]{0,80}?\s\d{1,4}\s?\.\s"
)
_FRAMEWORK = ("domestic_law", "legal_framework", "eu_international_law")


def heading_sections(text: str) -> List[Tuple[int, str]]:
    """(offset, section) at each heading, in text order."""
    marks = []
    for match in _UPPER_RUN_RE.finditer(text):
        run = re.sub(r"\s+", " ", match.group(0)).strip()
        run = re.sub(r"^(?:[IVX]+|[A-H])\.?\s+", "", run)
        run = re.sub(r"\s+(?:[IVX]+|[A-H])$", "", run)  # "THE LAW I. ALLEGED ..."
        for label, rule in _HEADING_RULES:
            if rule.search(run):
                marks.append((match.start(), label))
                break
    marks.sort()
    # Subheadings refine a legal-framework part only.
    current_by_offset = list(marks)
    extra = []
    for regex in (_SUBHEADING_RE, _UNNUMBERED_EU_HEADING_RE):
        for match in regex.finditer(text):
            section = _section_at(current_by_offset, match.start())
            if section not in _FRAMEWORK:
                continue
            if regex is _UNNUMBERED_EU_HEADING_RE or match.group("eu"):
                extra.append((match.start(), "eu_international_law"))
            else:
                extra.append((match.start(), "domestic_law"))
    return sorted(marks + extra)


def _section_at(marks, offset):
    section = None
    for start, label in marks:
        if start > offset:
            break
        section = label
    return section


_SEGMENT_LABELS = (
    ("procedure", "procedure"),
    ("facts", "facts"),
    ("complaints", "law"),
    ("law", "law"),
    ("court_assessment", "law"),
    ("operative", "operative"),
    ("separate_opinion", "separate_opinion"),
)


def segment_spans(text: str, segments: Optional[Dict[str, str]]) -> List[Tuple[int, int, str]]:
    """Locate echr_extractor_segments parts in text: [(start, end, section)]."""
    spans = []
    if not segments:
        return spans
    for column, label in _SEGMENT_LABELS:
        part = (segments.get(column) or "").strip()
        if len(part) < 40:
            continue
        start = text.find(part[:120])
        if start < 0:
            continue
        end = start + len(part)
        spans.append((start, end, label))
    return spans


class Sections:
    """Section of the judgment at an offset: segments first, headings refine."""

    def __init__(self, text: str, segments: Optional[Dict[str, str]] = None):
        self.marks = heading_sections(text)
        self.spans = segment_spans(text, segments)

    def at(self, offset: int) -> Optional[str]:
        heading = _section_at(self.marks, offset)
        if heading in _FRAMEWORK:
            return heading
        for start, end, label in self.spans:
            if start <= offset < end:
                return label
        return heading


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _choose_number(number: NumberMention, lookup_result, source_date, opinion_cue):
    candidates = resolver.filter_cjeu_suffix(
        lookup_result.get(number.normalized, []), number.suffix
    )
    return resolver.choose_cjeu(candidates, source_date, opinion_cue=opinion_cue)


def _cjeu_target_key(candidate):
    return CaseKey.from_dict(candidate.key())


def _relation(section, domestic_flag):
    if domestic_flag and section in DOMESTIC_SECTIONS:
        return RELATION_DOMESTIC
    return RELATION


def resolve(
    scan_result: Scan,
    unit: TextUnit,
    source: Source,
    lookup,
    sections: Optional[Sections] = None,
    domestic_flag: bool = True,
) -> List[PendingLink]:
    """Turn the references found in one text into pending links."""
    out: List[PendingLink] = []

    def add(dataset, target, start, end, method, confidence, ref=None, scheme=None, extra=()):
        section = sections.at(start) if sections else None
        mentions = [mention(unit, start, end, section)]
        mentions.extend(mention(unit, s, e, sections.at(s) if sections else None) for s, e in extra)
        out.append(
            PendingLink(
                target=target,
                relation_type=_relation(section, domestic_flag),
                source_dataset=dataset,
                match_method=method,
                confidence=confidence,
                target_ref_raw=ref,
                target_ref_scheme=scheme,
                mentions=mentions,
            )
        )

    numbers = lookup.get("cjeu_case_number", sorted(scan_result.case_numbers()))

    for citation in scan_result.citations:
        written = [n for n in citation.numbers if n.written]
        if citation.ecli is not None:
            start, end, ecli = citation.ecli
            candidate_eclis = {
                (c.ecli or "").upper()
                for n in citation.numbers
                for c in numbers.get(n.normalized, [])
            }
            any_candidates = bool(candidate_eclis)
            if ecli in candidate_eclis or not any_candidates:
                # The ECLI names the document; the numbers are part of its citation.
                add(
                    DATASET_CJEU,
                    CaseKey(ecli=ecli),
                    start,
                    end,
                    "ecli",
                    CONF_ECLI,
                    extra=[(n.start, n.end) for n in written],
                )
            else:
                # The numbers resolve but none to this ECLI (a typo on one side):
                # keep the explicit ECLI, leave the numbers for review.
                add(
                    DATASET_CJEU,
                    CaseKey(ecli=ecli),
                    start,
                    end,
                    match_method("ecli", "numbers_disagree"),
                    CONF_ECLI_CONFLICT,
                )
                for n in written:
                    add(
                        DATASET_CJEU,
                        None,
                        n.start,
                        n.end,
                        "case_number",
                        None,
                        ref=n.normalized,
                        scheme="cjeu_case_number",
                    )
            continue

        choices = [
            (n, _choose_number(n, numbers, source.date, citation.opinion_cue))
            for n in citation.numbers
        ]
        lead = next(((n, ch) for n, ch in choices if ch is not None), None)
        if lead is None:
            for n in written:
                add(
                    DATASET_CJEU,
                    None,
                    n.start,
                    n.end,
                    "case_number",
                    None,
                    ref=n.normalized,
                    scheme="cjeu_case_number",
                )
            continue
        lead_number, lead_choice = lead
        lead_id = lead_choice.candidate.case_id
        extra = []
        for n, choice in choices:
            if n is lead_number or not n.written:
                continue
            if choice is None or choice.candidate.case_id == lead_id:
                extra.append((n.start, n.end))
            elif choice.candidate.kind == resolver.CJEU_JUDGMENT:
                # A separately decided case listed in the same citation.
                add(
                    DATASET_CJEU,
                    _cjeu_target_key(choice.candidate),
                    n.start,
                    n.end,
                    match_method("case_number", choice.rule),
                    choice.confidence,
                    ref=n.normalized,
                    scheme="cjeu_case_number",
                )
        start, end = (lead_number.start, lead_number.end)
        if not lead_number.written:  # only an implied range member resolved
            start, end = written[0].start, written[0].end
        add(
            DATASET_CJEU,
            _cjeu_target_key(lead_choice.candidate),
            start,
            end,
            match_method("case_number", lead_choice.rule),
            lead_choice.confidence,
            ref=lead_number.normalized,
            scheme="cjeu_case_number",
            extra=[e for e in extra if e != (start, end)],
        )

    for start, end, ecli in scan_result.eu_eclis:
        add(DATASET_CJEU, CaseKey(ecli=ecli), start, end, "ecli", CONF_ECLI)

    for start, end, ecli in scan_result.nl_eclis:
        add(DATASET_RS, CaseKey(ecli=ecli), start, end, "ecli", CONF_ECLI)

    ljn_candidates = lookup.get("ljn", sorted(scan_result.ljn_values()))
    for start, end, value, cue in scan_result.ljns:
        choice = resolver.choose_ljn(ljn_candidates.get(value, []), source.date, opinion_cue=cue)
        if choice is None:
            add(DATASET_RS, None, start, end, "ljn", None, ref=value, scheme="ljn")
        else:
            target = CaseKey.from_dict(choice.candidate.key())
            add(
                DATASET_RS,
                target,
                start,
                end,
                match_method("ljn", choice.rule),
                choice.confidence,
                ref=value,
                scheme="ljn",
            )
    return out


def extract_text(
    unit: TextUnit,
    source: Source,
    lookup,
    segments: Optional[Dict[str, str]] = None,
    domestic_flag: Optional[bool] = None,
) -> List[LinkRecord]:
    """All links one HUDOC text supports (pure apart from ``lookup``)."""
    if domestic_flag is None:
        domestic_flag = env_flag(DOMESTIC_FLAG, True)
    if not unit.text:
        return []
    found = scan(unit.text)
    sections = Sections(unit.text, segments)
    pending = resolve(found, unit, source, lookup, sections, domestic_flag)
    return build_records(source, pending, EXTRACTOR_VERSION)


# ---------------------------------------------------------------------------
# Database entry point
# ---------------------------------------------------------------------------

_IDS_SQL = f"""
    SELECT DISTINCT case_id FROM {SCHEMA}.case_text
     WHERE source = 'HUDOC' AND fulltext IS NOT NULL {{where}}
"""

_TEXTS_SQL = f"""
    SELECT t.case_id, c.ecli, c.celex_id, c.item_id, c.date_decision,
           t.language, t.fulltext, t.summary, NULL::text AS item_id
      FROM {SCHEMA}.case_text t
      JOIN {SCHEMA}.cases c ON c.id = t.case_id
     WHERE t.source = 'HUDOC' AND t.case_id = ANY(%s)
"""

_SECONDARY_SQL = f"""
    SELECT d.case_id, d.language, s.fulltext, d.item_id
      FROM {SCHEMA}.echr_document_secondary_text s
      JOIN {SCHEMA}.echr_document d ON d.item_id = s.item_id
     WHERE d.case_id = ANY(%s)
"""

_SEGMENTS_SQL = f"""
    SELECT d.case_id, g.item_id, g.procedure, g.facts, g.complaints, g.law, g.operative,
           g.court_assessment, g.separate_opinion
      FROM {SCHEMA}.echr_extractor_segments g
      JOIN {SCHEMA}.echr_document d ON d.item_id = g.item_id
     WHERE d.case_id = ANY(%s) AND g.error IS NULL
"""

_SEGMENT_COLUMNS = (
    "procedure",
    "facts",
    "complaints",
    "law",
    "operative",
    "court_assessment",
    "separate_opinion",
)


def _table_exists(cursor, name):
    cursor.execute("SELECT to_regclass(%s)", (f"{SCHEMA}.{name}",))
    return cursor.fetchone()[0] is not None


def _segments_for(segments_by_case, case_id, text):
    for segments in segments_by_case.get(case_id, []):
        if segment_spans(text, segments):
            return segments
    return None


def extract_batch(cursor, case_ids: Sequence[int], lookup, domestic_flag: bool, has_secondary=True):
    cursor.execute(_TEXTS_SQL, (list(case_ids),))
    rows = cursor.fetchall()
    sources, units = {}, []
    for case_id, ecli, celex, item_id, decided, language, fulltext, summary, _ in rows:
        sources[case_id] = Source(
            CaseKey(ecli=ecli or None, celex=celex or None, item_id=item_id or None), decided
        )
        if fulltext:
            units.append((case_id, TextUnit(fulltext, "fulltext", language, HUDOC)))
        if summary:
            units.append((case_id, TextUnit(summary, "summary", language, HUDOC)))
    if has_secondary:
        cursor.execute(_SECONDARY_SQL, (list(case_ids),))
        for case_id, language, fulltext, _item in cursor.fetchall():
            if case_id in sources and fulltext:
                units.append((case_id, TextUnit(fulltext, "fulltext", language, HUDOC_SECONDARY)))
    segments_by_case = {}
    if _table_exists(cursor, "echr_extractor_segments"):
        cursor.execute(_SEGMENTS_SQL, (list(case_ids),))
        for row in cursor.fetchall():
            segments_by_case.setdefault(row[0], []).append(dict(zip(_SEGMENT_COLUMNS, row[2:])))

    scans = [(case_id, unit, scan(unit.text)) for case_id, unit in units]
    lookup.prefetch("cjeu_case_number", {n for _c, _u, s in scans for n in s.case_numbers()})
    lookup.prefetch("ljn", {v for _c, _u, s in scans for v in s.ljn_values()})

    pending_by_case: Dict[int, List[PendingLink]] = {}
    for case_id, unit, found in scans:
        source = sources[case_id]
        if not (source.key.ecli or source.key.celex or source.key.item_id):
            continue
        sections = Sections(unit.text, _segments_for(segments_by_case, case_id, unit.text))
        pending_by_case.setdefault(case_id, []).extend(
            resolve(found, unit, source, lookup, sections, domestic_flag)
        )
    records = []
    for case_id, pending in pending_by_case.items():
        records.extend(build_records(sources[case_id], pending, EXTRACTOR_VERSION))
    return records


def write_out(records: List[LinkRecord], out_path, datasets=DATASETS):
    """A directory gets one file per dataset (empty files included); a file gets all."""
    if os.path.isdir(out_path) or str(out_path).endswith(os.sep):
        os.makedirs(out_path, exist_ok=True)
        counts = {}
        for dataset in datasets:
            path = os.path.join(out_path, f"{dataset}.jsonl")
            counts[dataset] = write_artifact(
                (r for r in records if r.source_dataset == dataset), path
            )
        return counts
    return {"all": write_artifact(records, out_path)}


def extract(conn, case_ids=None, id_range=None, out_path=None, domestic_flag=None, batch_size=500):
    """Scan HUDOC texts in the database and write the link artifact(s).

    Returns {"records": n, "by_dataset": {...}, "written": {...}}.
    """
    if domestic_flag is None:
        domestic_flag = env_flag(DOMESTIC_FLAG, True)
    records: List[LinkRecord] = []
    with conn.cursor() as cursor:
        has_secondary = _table_exists(cursor, "echr_document_secondary_text")
        lookup = CandidateLookup(cursor)
        for ids in iter_case_batches(
            conn, _IDS_SQL, case_ids=case_ids, id_range=id_range, batch_size=batch_size
        ):
            records.extend(extract_batch(cursor, ids, lookup, domestic_flag, has_secondary))
            lookup.clear()
            log.info("echr_text: up to case %s, %s records", ids[-1], len(records))
    by_dataset = {}
    for record in records:
        by_dataset[record.source_dataset] = by_dataset.get(record.source_dataset, 0) + 1
    written = write_out(records, out_path) if out_path else {}
    return {"records": len(records), "by_dataset": by_dataset, "written": written}


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = cli_args("ECtHR text -> CJEU and Rechtspraak links (R2.2)", argv)
    conn = connect(args.dsn_env)
    try:
        result = extract(
            conn,
            case_ids=args.case_id,
            id_range=(args.from_id, args.to_id),
            out_path=args.out,
            batch_size=args.batch_size,
        )
    finally:
        conn.close()
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
