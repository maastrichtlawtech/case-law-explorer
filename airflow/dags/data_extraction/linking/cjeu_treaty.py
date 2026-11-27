"""Extract ECHR, Council of Europe Protocol, and core UN treaty references from CJEU texts.

CELLAR SPARQL metadata only emits EU legislation (``scheme = 'celex'``), so CJEU
judgments and AG opinions citing the ECHR, its Protocols, the 1951 Geneva Refugee
Convention, ICCPR, CRC, or CRPD produce zero rows in ``case_law_reference`` unless
scanned from ``case_text``.

Pure scanner (``scan``) + incremental DB extractor (``extract_pending``) + idempotent
JSONL loader (``load_artifact``) writing ``source_dataset = 'cjeu_text_treaty'``
under the partial unique index ``case_law_reference_uk_cjeu_treaty`` (migration 0018).
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
DATASET = "cjeu_text_treaty"
EXTRACTOR_VERSION = "cjeu_treaty/1.0.0"
ROLE = "cited"

# Separators include '_' because historical cellar_extractor fulltexts replaced ',' with '_'.
_SEP = r"[\s\u00a0,_;:]+"
_OPT_SEP = r"[\s\u00a0,_;:]*"

# Article number + optional paragraph/subdivision, e.g. "6(1)", "8, lid 1", "3, paragraph 2", "1A".
_ART_HEAD = r"(?:Articles?|Arts?\.?|Artikelen|Artikel|Art[íi]culos?|Articoli|Articolo)"
_ART_NUM = r"(\d{1,2}[A-Za-z]?)"
_PARA_TAIL = (
    r"(?:"
    r"\s*\(\s*(\d{1,2}[a-z]?)\s*\)"
    r"|" + _OPT_SEP + r"(?:paragraphs?|para\.?|paragraphes?|Abs\.?|Absatz|lid|leden|apartados?|comma)\s*(\d{1,2}[a-z]?)"
    r")?"
)
_ART_SPEC = _ART_HEAD + r"[\s\u00a0]+" + _ART_NUM + _PARA_TAIL

# Second article in a simple pair like "Articles 7 and 8 of the ECHR" or "articles 6 et 13 de la CEDH".
_CONJ = r"(?:and|et|und|en|y|e)"
_ART_PAIR = (
    _ART_HEAD + r"[\s\u00a0]+" + _ART_NUM + _PARA_TAIL
    + r"[\s\u00a0]+" + _CONJ + r"[\s\u00a0]+" + _ART_NUM + _PARA_TAIL
)

# Negative lookahead rejecting ECtHR case reporter citations like "ECHR 1999-I", "CEDH 2000-V", "EMRK 2006-XI".
_NOT_REPORTER = r"(?![\s\u00a0]*\d{4}[\s\u00a0]*[-–—‑][\s\u00a0]*[IVXLCDM]+)"
# Reject matches embedded inside an ECLI like "CE:ECHR:2015:..."
_NOT_ECLI_L = r"(?<![A-Za-z0-9:])"
_NOT_ECLI_R = r"(?![A-Za-z0-9:])"

_ECHR_ACRONYM = (
    _NOT_ECLI_L + r"(?:ECHR|CEDH|EMRK|EVRM|CEDU)" + _NOT_ECLI_R + _NOT_REPORTER
)
_ECHR_FULL = (
    r"(?:European\s+Convention\s+(?:for\s+the\s+Protection\s+of|on)\s+Human\s+Rights(?:\s+and\s+Fundamental\s+Freedoms)?"
    r"|Convention\s+europ[ée]enne\s+(?:de\s+sauvegarde\s+des|des)\s+droits\s+de\s+l['’]homme(?:\s+et\s+des\s+libert[ée]s\s+fondamentales)?"
    r"|Europ[äa]ischen?\s+Konvention\s+zum\s+Schutze?\s+der\s+Menschenrechte(?:\s+und\s+Grundfreiheiten)?"
    r"|Europe(?:es|se)\s+Verdrag\s+(?:tot\s+bescherming\s+van|voor|inzake)\s+de\s+rechten\s+van\s+de\s+mens(?:\s+en\s+de\s+fundamentele\s+vrijheden)?"
    r"|Convenio\s+Europeo\s+para\s+la\s+Protecci[óo]n\s+de\s+los\s+Derechos\s+Humanos(?:\s+y\s+de\s+las\s+Libertades\s+Fundamentales)?"
    r"|Convenzione\s+europea\s+per\s+la\s+salvaguardia\s+dei\s+diritti\s+dell['’]uomo(?:\s+e\s+delle\s+libert[àa]\s+fondamentali)?)"
)

_ECHR_CONN = r"(?:of\s+the|under\s+the|de\s+la|der|des|van\s+het|het|del|della)"

# Protocols to the ECHR: protocol number -> (coe_treaty ETS identifier, max article)
ECHR_PROTOCOLS: Dict[int, Tuple[str, int]] = {
    1: ("009", 5),
    4: ("046", 7),
    6: ("114", 8),
    7: ("117", 10),
    12: ("177", 6),
    13: ("187", 8),
}

_PROTO_NUM_WORD = {
    "1": 1, "1st": 1, "first": 1, "premier": 1, "1er": 1, "eerste": 1, "1e": 1, "ersten": 1, "primo": 1, "primero": 1,
    "4": 4, "4th": 4, "fourth": 4, "quatrième": 4, "vierde": 4, "4e": 4, "vierten": 4, "quarto": 4, "cuarto": 4,
    "6": 6, "6th": 6, "sixth": 6, "sixième": 6, "zesde": 6, "6e": 6, "sechsten": 6, "sesto": 6, "sexto": 6,
    "7": 7, "7th": 7, "seventh": 7, "septième": 7, "zevende": 7, "7e": 7, "siebten": 7, "settimo": 7, "séptimo": 7,
    "12": 12, "12th": 12, "twelfth": 12, "douzième": 12, "twaalfde": 12, "12e": 12,
    "13": 13, "13th": 13, "thirteenth": 13, "treizième": 13, "dertiende": 13, "13e": 13,
}

# Patterns: ECHR Protocols (checked before bare ECHR so "Article 1 of Protocol No 1 to the ECHR"
# maps to coe_treaty/009 rather than coe_treaty/005).
_PROTO_PHRASE = (
    r"(?:Protocol\s+(?:No\.?\s*)?(1|4|6|7|12|13)\b(?:\s+to\s+the\s+(?:" + _ECHR_ACRONYM + r"|Convention))?"
    r"|Additional\s+Protocol\s+to\s+the\s+(?:" + _ECHR_ACRONYM + r"|" + _ECHR_FULL + r")"
    r"|protocole\s+(?:additionnel\s+)?n[°o]\.?\s*(1|4|6|7|12|13)\b(?:\s+[àa]\s+la\s+(?:" + _ECHR_ACRONYM + r"|convention))?"
    r"|Protokoll\s+Nr\.?\s*(1|4|6|7|12|13)\b(?:\s+(?:zur|der)\s+(?:" + _ECHR_ACRONYM + r"|Konvention))?"
    r"|Zusatzprotokoll(?:s)?\s+zur\s+(?:" + _ECHR_ACRONYM + r"|" + _ECHR_FULL + r")"
    r"|(Eerste|Vierde|Zesde|Zevende|1e|4e|6e|7e)\s+Protocol\s+bij\s+het\s+(?:" + _ECHR_ACRONYM + r"|Verdrag)"
    r"|Protocolo\s+n\.?[º°o]\s*(1|4|6|7|12|13)\b(?:\s+del\s+" + _ECHR_ACRONYM + r")?"
    r"|Protocollo\s+n\.?\s*(1|4|6|7|12|13)\b(?:\s+alla\s+" + _ECHR_ACRONYM + r")?)"
)

_RE_PROTO_ART = re.compile(
    _ART_SPEC + _OPT_SEP + r"(?:of|du|des|van\s+het|del|della)?[\s\u00a0]*" + _PROTO_PHRASE,
    re.IGNORECASE,
)

# ECHR article pair: "Articles 7 and 8 of the ECHR", "articles 6 et 13 de la CEDH"
_RE_ECHR_PAIR = re.compile(
    _ART_PAIR + _OPT_SEP + r"(?:" + _ECHR_CONN + r"[\s\u00a0]+)?"
    + r"(?:" + _ECHR_ACRONYM + r"|" + _ECHR_FULL + r")",
    re.IGNORECASE,
)

# Single ECHR article: "Article 6(1) of the ECHR", "Art. 8 EMRK", "artikel 6, lid 1, EVRM"
_RE_ECHR_ART = re.compile(
    _ART_SPEC + _OPT_SEP + r"(?:" + _ECHR_CONN + r"[\s\u00a0]+)?"
    + r"(?:" + _ECHR_ACRONYM + r"|" + _ECHR_FULL + r")",
    re.IGNORECASE,
)

# Whole-treaty ECHR mentions (full name or explicit "of/under the ECHR", never reporter/ECLI)
_RE_ECHR_WHOLE_FULL = re.compile(_ECHR_FULL, re.IGNORECASE)
_RE_ECHR_WHOLE_ACRO = re.compile(
    r"(?:\b(?:of|under|by|in|to|with)\s+the|\bde\s+la|\bà\s+la|\bder|\bvan\s+het|\bhet|\bdel|\bdella)[\s\u00a0]+"
    + _ECHR_ACRONYM,
    re.IGNORECASE,
)

# Core UN Treaties already in cle_v2.legislation (scheme = 'un_treaty')
_UN_TREATIES: Tuple[Tuple[str, int, re.Pattern, re.Pattern], ...] = (
    # Geneva Refugee Convention 1951 (un_treaty / V-2) — never match bare "Geneva"
    (
        "V-2",
        46,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of\s+the|de\s+la|der|van\s+het|del|della)?[\s\u00a0]*"
            r"(?:Geneva\s+Convention(?:\s+of\s+28\s+July\s+1951)?(?:\s+relating\s+to\s+the\s+Status\s+of\s+Refugees)?"
            r"|Convention\s+relating\s+to\s+the\s+Status\s+of\s+Refugees"
            r"|Convention\s+de\s+Gen[èe]ve(?:\s+du\s+28\s+juillet\s+1951)?(?:\s+relative\s+au\s+statut\s+des\s+r[ée]fugi[ée]s)?"
            r"|Genfer\s+Fl[üu]chtlingskonvention"
            r"|Genfer\s+Abkommen(?:s)?\s+[üu]ber\s+die\s+Rechtsstellung\s+der\s+Fl[üu]chtlinge"
            r"|Vluchtelingenverdrag"
            r"|Verdrag\s+betreffende\s+de\s+status\s+van\s+vluchtelingen)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:Convention\s+relating\s+to\s+the\s+Status\s+of\s+Refugees"
            r"|Geneva\s+Convention\s+(?:of\s+28\s+July\s+1951|relating\s+to\s+the\s+Status\s+of\s+Refugees)"
            r"|Convention\s+de\s+Gen[èe]ve\s+(?:du\s+28\s+juillet\s+1951|relative\s+au\s+statut\s+des\s+r[ée]fugi[ée]s)"
            r"|Genfer\s+Fl[üu]chtlingskonvention"
            r"|Vluchtelingenverdrag"
            r"|Verdrag\s+betreffende\s+de\s+status\s+van\s+vluchtelingen)",
            re.IGNORECASE,
        ),
    ),
    # ICCPR (un_treaty / IV-4)
    (
        "IV-4",
        53,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of\s+the|du|des|van\s+het|del)?[\s\u00a0]*"
            r"(?:" + _NOT_ECLI_L + r"(?:ICCPR|IVBPR|IPbpR)" + _NOT_ECLI_R
            + r"|International\s+Covenant\s+on\s+Civil\s+and\s+Political\s+Rights"
            r"|Pacte\s+international\s+relatif\s+aux\s+droits\s+civils\s+et\s+politiques"
            r"|Internationaal\s+Verdrag\s+inzake\s+burgerrechten\s+en\s+politieke\s+rechten)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:" + _NOT_ECLI_L + r"(?:ICCPR|IVBPR|IPbpR)" + _NOT_ECLI_R
            + r"|International\s+Covenant\s+on\s+Civil\s+and\s+Political\s+Rights"
            r"|Pacte\s+international\s+relatif\s+aux\s+droits\s+civils\s+et\s+politiques"
            r"|Internationaal\s+Verdrag\s+inzake\s+burgerrechten\s+en\s+politieke\s+rechten)",
            re.IGNORECASE,
        ),
    ),
    # UN Convention on the Rights of the Child (un_treaty / IV-11)
    (
        "IV-11",
        54,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of\s+the|de\s+la|der|van\s+het|del)?[\s\u00a0]*"
            r"(?:" + _NOT_ECLI_L + r"(?:UNCRC|IVRK)" + _NOT_ECLI_R
            + r"|(?:UN\s+)?Convention\s+on\s+the\s+Rights\s+of\s+the\s+Child"
            r"|Convention\s+(?:internationale\s+)?relative\s+aux\s+droits\s+de\s+l['’]enfant"
            r"|UN-Kinderrechtskonvention"
            r"|Internationaal\s+Verdrag\s+inzake\s+de\s+rechten\s+van\s+het\s+kind)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:" + _NOT_ECLI_L + r"(?:UNCRC|IVRK)" + _NOT_ECLI_R
            + r"|Convention\s+on\s+the\s+Rights\s+of\s+the\s+Child"
            r"|Convention\s+(?:internationale\s+)?relative\s+aux\s+droits\s+de\s+l['’]enfant"
            r"|UN-Kinderrechtskonvention"
            r"|Internationaal\s+Verdrag\s+inzake\s+de\s+rechten\s+van\s+het\s+kind)",
            re.IGNORECASE,
        ),
    ),
    # UN Convention on the Rights of Persons with Disabilities (un_treaty / IV-15)
    (
        "IV-15",
        50,
        re.compile(
            _ART_SPEC + _OPT_SEP + r"(?:of\s+the|de\s+la|der|van\s+het|del)?[\s\u00a0]*"
            r"(?:" + _NOT_ECLI_L + r"(?:UNCRPD|CRPD)" + _NOT_ECLI_R
            + r"|(?:UN\s+)?Convention\s+on\s+the\s+Rights\s+of\s+Persons\s+with\s+Disabilities"
            r"|Convention\s+(?:des\s+Nations\s+[Uu]nies\s+)?relative\s+aux\s+droits\s+des\s+personnes\s+handicap[ée]es"
            r"|UN-Behindertenrechtskonvention"
            r"|Verdrag\s+inzake\s+de\s+rechten\s+van\s+personen\s+met\s+een\s+handicap)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:" + _NOT_ECLI_L + r"(?:UNCRPD|CRPD)" + _NOT_ECLI_R
            + r"|Convention\s+on\s+the\s+Rights\s+of\s+Persons\s+with\s+Disabilities"
            r"|Convention\s+(?:des\s+Nations\s+[Uu]nies\s+)?relative\s+aux\s+droits\s+des\s+personnes\s+handicap[ée]es"
            r"|UN-Behindertenrechtskonvention"
            r"|Verdrag\s+inzake\s+de\s+rechten\s+van\s+personen\s+met\s+een\s+handicap)",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class TreatyHit:
    scheme: str           # 'coe_treaty' | 'un_treaty'
    identifier: str       # '005', '009', '117', 'V-2', 'IV-4', 'IV-11', 'IV-15'
    article: Optional[str]
    raw_subdivision: Optional[str]
    match_method: str     # 'treaty_article' | 'treaty_name'
    confidence: float
    start: int
    end: int
    raw_text: str


@dataclass(frozen=True)
class TreatyRefRecord:
    ecli: Optional[str]
    celex: Optional[str]
    scheme: str
    identifier: str
    raw_subdivision: Optional[str]
    article: Optional[str]
    raw_reference: str
    match_method: str
    confidence: float
    source_dataset: str = DATASET
    extractor_version: str = EXTRACTOR_VERSION
    role: str = ROLE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TreatyRefRecord":
        return cls(
            ecli=data.get("ecli") or None,
            celex=data.get("celex") or None,
            scheme=str(data["scheme"]),
            identifier=str(data["identifier"]),
            raw_subdivision=data.get("raw_subdivision") or None,
            article=data.get("article") or None,
            raw_reference=str(data.get("raw_reference") or ""),
            match_method=str(data.get("match_method") or "treaty_article"),
            confidence=float(data.get("confidence", 0.9)),
            source_dataset=str(data.get("source_dataset") or DATASET),
            extractor_version=str(data.get("extractor_version") or EXTRACTOR_VERSION),
            role=str(data.get("role") or ROLE),
        )


def _article_number_int(article: str) -> Optional[int]:
    m = re.match(r"^(\d+)", article)
    return int(m.group(1)) if m else None


def _format_subdivision(art: str, para1: Optional[str], para2: Optional[str]) -> Tuple[str, str]:
    art_clean = art.strip()
    para = (para1 or para2 or "").strip()
    if para:
        return art_clean, f"{art_clean}({para})"
    return art_clean, art_clean


def _overlaps(span: Tuple[int, int], covered: List[Tuple[int, int]]) -> bool:
    s, e = span
    return any(s < ce and e > cs for cs, ce in covered)


def _clean_ref(raw: str) -> str:
    return " ".join(raw.split())[:240]


def scan(text: str, language: Optional[str] = None) -> List[TreatyHit]:
    """Scan a single CJEU judgment/opinion text for ECHR, Protocol, and UN treaty citations."""
    if not text:
        return []
    hits: List[TreatyHit] = []
    covered: List[Tuple[int, int]] = []
    seen_acts: set[Tuple[str, str]] = set()

    # 1. ECHR Protocols first so "Article 1 of Protocol No 1 to the ECHR" isn't stolen by bare ECHR.
    has_echr_context = bool(
        re.search(_ECHR_ACRONYM, text) or _RE_ECHR_WHOLE_FULL.search(text)
    )
    for m in _RE_PROTO_ART.finditer(text):
        art_raw, p1, p2 = m.group(1), m.group(2), m.group(3)
        proto_num: Optional[int] = None
        for g in m.groups()[3:]:
            if g:
                proto_num = _PROTO_NUM_WORD.get(g.lower())
                if proto_num is not None:
                    break
        if proto_num is None and re.search(r"Additional\s+Protocol|Zusatzprotokoll", m.group(0), re.I):
            proto_num = 1
        if proto_num not in ECHR_PROTOCOLS:
            continue
        # Bare "Protocol No 7" without ECHR in the match requires ECHR context in the document
        # so we don't confuse EU Treaty Protocols (Protocol No 1 / No 7 to TFEU) with ECHR Protocols.
        explicit_echr_in_match = bool(
            re.search(_ECHR_ACRONYM, m.group(0))
            or _RE_ECHR_WHOLE_FULL.search(m.group(0))
            or re.search(r"Convention|Konvention|Verdrag", m.group(0), re.I)
        )
        if not explicit_echr_in_match and not has_echr_context:
            continue
        if not explicit_echr_in_match and re.search(r"TFEU|TEU|TFUE|TUE|AEUV|EUV|VWEU|VEU|Statute", text[max(0, m.start() - 40):m.end() + 40], re.I):
            continue
        ident, max_art = ECHR_PROTOCOLS[proto_num]
        num = _article_number_int(art_raw)
        if num is None or not (1 <= num <= max_art):
            continue
        art, sub = _format_subdivision(art_raw, p1, p2)
        hits.append(TreatyHit(
            scheme="coe_treaty",
            identifier=ident,
            article=art,
            raw_subdivision=sub,
            match_method="treaty_article",
            confidence=0.95 if explicit_echr_in_match else 0.85,
            start=m.start(),
            end=m.end(),
            raw_text=_clean_ref(m.group(0)),
        ))
        covered.append((m.start(), m.end()))
        seen_acts.add(("coe_treaty", ident))

    # 2. ECHR article pairs ("Articles 7 and 8 of the ECHR")
    for m in _RE_ECHR_PAIR.finditer(text):
        if _overlaps((m.start(), m.end()), covered):
            continue
        pairs = ((m.group(1), m.group(2), m.group(3)), (m.group(4), m.group(5), m.group(6)))
        added = False
        for art_raw, p1, p2 in pairs:
            num = _article_number_int(art_raw)
            if num is None or not (1 <= num <= 59):
                continue
            art, sub = _format_subdivision(art_raw, p1, p2)
            hits.append(TreatyHit(
                scheme="coe_treaty",
                identifier="005",
                article=art,
                raw_subdivision=sub,
                match_method="treaty_article",
                confidence=0.95,
                start=m.start(),
                end=m.end(),
                raw_text=_clean_ref(m.group(0)),
            ))
            added = True
        if added:
            covered.append((m.start(), m.end()))
            seen_acts.add(("coe_treaty", "005"))

    # 3. Single ECHR articles ("Article 6(1) of the ECHR", "article 8 de la CEDH", "Art. 8 EMRK")
    for m in _RE_ECHR_ART.finditer(text):
        if _overlaps((m.start(), m.end()), covered):
            continue
        art_raw, p1, p2 = m.group(1), m.group(2), m.group(3)
        num = _article_number_int(art_raw)
        if num is None or not (1 <= num <= 59):
            continue
        art, sub = _format_subdivision(art_raw, p1, p2)
        hits.append(TreatyHit(
            scheme="coe_treaty",
            identifier="005",
            article=art,
            raw_subdivision=sub,
            match_method="treaty_article",
            confidence=0.95,
            start=m.start(),
            end=m.end(),
            raw_text=_clean_ref(m.group(0)),
        ))
        covered.append((m.start(), m.end()))
        seen_acts.add(("coe_treaty", "005"))

    # 4. Whole-treaty ECHR fallback if no specific article was found in this text
    if ("coe_treaty", "005") not in seen_acts:
        m = _RE_ECHR_WHOLE_FULL.search(text) or _RE_ECHR_WHOLE_ACRO.search(text)
        if m is not None and not _overlaps((m.start(), m.end()), covered):
            hits.append(TreatyHit(
                scheme="coe_treaty",
                identifier="005",
                article=None,
                raw_subdivision=None,
                match_method="treaty_name",
                confidence=0.90 if _RE_ECHR_WHOLE_FULL.match(m.group(0)) else 0.85,
                start=m.start(),
                end=m.end(),
                raw_text=_clean_ref(m.group(0)),
            ))
            seen_acts.add(("coe_treaty", "005"))

    # 5. Core UN Treaties (Geneva Refugee Convention 1951, ICCPR, CRC, CRPD)
    for ident, max_art, art_re, whole_re in _UN_TREATIES:
        for m in art_re.finditer(text):
            if _overlaps((m.start(), m.end()), covered):
                continue
            art_raw, p1, p2 = m.group(1), m.group(2), m.group(3)
            num = _article_number_int(art_raw)
            if num is None or not (1 <= num <= max_art):
                continue
            # Extra safety for Geneva Convention: reject if text talks about Geneva 1949 war conventions
            # unless Refugee / 1951 cue is present in the match or nearby.
            if ident == "V-2" and "refugee" not in m.group(0).lower() and "réfugié" not in m.group(0).lower() and "flüchtling" not in m.group(0).lower() and "vluchteling" not in m.group(0).lower() and "1951" not in m.group(0):
                ctx = text[max(0, m.start() - 250):m.end() + 250].lower()
                if not any(w in ctx for w in ("refugee", "réfugié", "flüchtling", "vluchteling", "asylum", "asile", "asiel", "1951")):
                    continue
            art, sub = _format_subdivision(art_raw, p1, p2)
            hits.append(TreatyHit(
                scheme="un_treaty",
                identifier=ident,
                article=art,
                raw_subdivision=sub,
                match_method="treaty_article",
                confidence=0.95,
                start=m.start(),
                end=m.end(),
                raw_text=_clean_ref(m.group(0)),
            ))
            covered.append((m.start(), m.end()))
            seen_acts.add(("un_treaty", ident))

        if ("un_treaty", ident) not in seen_acts:
            m = whole_re.search(text)
            if m is not None and not _overlaps((m.start(), m.end()), covered):
                hits.append(TreatyHit(
                    scheme="un_treaty",
                    identifier=ident,
                    article=None,
                    raw_subdivision=None,
                    match_method="treaty_name",
                    confidence=0.90,
                    start=m.start(),
                    end=m.end(),
                    raw_text=_clean_ref(m.group(0)),
                ))
                seen_acts.add(("un_treaty", ident))

    return hits


def records_for_case(
    ecli: Optional[str],
    celex: Optional[str],
    texts: Iterable[Tuple[Optional[str], str]],
) -> List[TreatyRefRecord]:
    """Extract deduplicated TreatyRefRecords across all language texts of one CJEU case."""
    merged: Dict[Tuple[str, str, str], TreatyHit] = {}
    acts_with_articles: set[Tuple[str, str]] = set()

    for language, text in texts:
        for hit in scan(text, language=language):
            if hit.article is not None:
                acts_with_articles.add((hit.scheme, hit.identifier))
            key = (hit.scheme, hit.identifier, hit.raw_subdivision or "")
            existing = merged.get(key)
            if existing is None or hit.confidence > existing.confidence:
                merged[key] = hit

    # Drop act-level (subdivision=None) fallback if any language of the same case
    # yielded specific article citations for that same treaty.
    records: List[TreatyRefRecord] = []
    for (scheme, ident, sub), hit in sorted(merged.items()):
        if not sub and (scheme, ident) in acts_with_articles:
            continue
        records.append(TreatyRefRecord(
            ecli=ecli or None,
            celex=celex or None,
            scheme=scheme,
            identifier=ident,
            raw_subdivision=hit.raw_subdivision,
            article=hit.article,
            raw_reference=hit.raw_text,
            match_method=hit.match_method,
            confidence=hit.confidence,
        ))
    return records


def write_jsonl(path: str, records: Iterable[TreatyRefRecord]) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    count = 0
    with open(tmp, "w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    os.replace(tmp, path)
    return count


def read_jsonl(path: str) -> List[TreatyRefRecord]:
    out: List[TreatyRefRecord] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(TreatyRefRecord.from_dict(json.loads(line)))
    return out


_INSERT_RESOLVED_SQL = f"""
    INSERT INTO {SCHEMA}.case_law_reference (
        case_id, legislation_id, provision_id,
        raw_scheme, raw_resource, raw_subdivision, raw_reference,
        role, source_dataset, extractor_version, match_method, confidence
    )
    SELECT case_id, legislation_id, provision_id,
           raw_scheme, raw_resource, raw_subdivision, raw_reference,
           role, source_dataset, extractor_version, match_method, confidence
      FROM (VALUES %s) AS v(
        ord, case_id, legislation_id, provision_id,
        raw_scheme, raw_resource, raw_subdivision, raw_reference,
        role, source_dataset, extractor_version, match_method, confidence
      )
     ORDER BY ord
    ON CONFLICT (case_id, raw_scheme, raw_resource, COALESCE(raw_subdivision, ''), role, source_dataset)
    WHERE raw_resource IS NOT NULL
      AND (legislation_id IS NOT NULL OR provision_id IS NOT NULL)
      AND source_dataset = '{DATASET}'
    DO NOTHING
    RETURNING provision_id
"""

_INSERT_UNRESOLVED_SQL = f"""
    INSERT INTO {SCHEMA}.case_law_reference (
        case_id, legislation_id, provision_id,
        raw_scheme, raw_resource, raw_subdivision, raw_reference,
        role, source_dataset, extractor_version, match_method, confidence
    )
    SELECT case_id, legislation_id, provision_id,
           raw_scheme, raw_resource, raw_subdivision, raw_reference,
           role, source_dataset, extractor_version, match_method, confidence
      FROM (VALUES %s) AS v(
        ord, case_id, legislation_id, provision_id,
        raw_scheme, raw_resource, raw_subdivision, raw_reference,
        role, source_dataset, extractor_version, match_method, confidence
      )
     ORDER BY ord
    ON CONFLICT (case_id, raw_scheme, raw_resource, COALESCE(raw_subdivision, ''), role, source_dataset)
    WHERE provision_id IS NULL AND legislation_id IS NULL AND raw_resource IS NOT NULL
    DO NOTHING
    RETURNING id
"""

_ROW_TEMPLATE = "(%s::integer, %s::bigint, %s::bigint, %s::bigint, %s::text, %s::text, %s::text, %s::text, %s::text, %s::text, %s::text, %s::text, %s::real)"


def load_records(conn, records: Sequence[TreatyRefRecord], batch_size: int = 1000) -> Dict[str, int]:
    """Idempotently load TreatyRefRecords into cle_v2.case_law_reference."""
    from psycopg2.extras import execute_values

    stats: Counter = Counter()
    if not records:
        return {}

    with conn.cursor() as cur:
        # Resolve cases by ECLI / CELEX
        eclis = sorted({r.ecli for r in records if r.ecli})
        celexes = sorted({r.celex for r in records if r.celex})
        case_by_ecli: Dict[str, int] = {}
        case_by_celex: Dict[str, int] = {}
        if eclis:
            cur.execute(f"SELECT ecli, id FROM {SCHEMA}.cases WHERE ecli = ANY(%s)", (eclis,))
            case_by_ecli = {e: int(i) for e, i in cur.fetchall()}
        if celexes:
            cur.execute(f"SELECT celex_id, id FROM {SCHEMA}.cases WHERE celex_id = ANY(%s)", (celexes,))
            case_by_celex = {c: int(i) for c, i in cur.fetchall()}

        # Resolve legislation by (scheme, identifier)
        schemes = sorted({r.scheme for r in records})
        idents = sorted({r.identifier for r in records})
        cur.execute(
            f"SELECT scheme, identifier, min(id) FROM {SCHEMA}.legislation "
            "WHERE scheme = ANY(%s) AND identifier = ANY(%s) GROUP BY scheme, identifier",
            (schemes, idents),
        )
        leg_map: Dict[Tuple[str, str], int] = {(s, i): int(lid) for s, i, lid in cur.fetchall()}

        # Resolve provisions by (legislation_id, lower(article_label))
        wanted_lids = sorted(set(leg_map.values()))
        wanted_arts = sorted({r.article.lower() for r in records if r.article})
        prov_map: Dict[Tuple[int, str], int] = {}
        if wanted_lids and wanted_arts:
            cur.execute(
                f"SELECT legislation_id, lower(article_label), min(id) FROM {SCHEMA}.legal_provision "
                "WHERE legislation_id = ANY(%s) AND element_type = 'article' AND lower(article_label) = ANY(%s) "
                "GROUP BY legislation_id, lower(article_label)",
                (wanted_lids, wanted_arts),
            )
            prov_map = {(int(lid), art): int(pid) for lid, art, pid in cur.fetchall()}

        for start in range(0, len(records), batch_size):
            chunk = records[start:start + batch_size]
            resolved_rows: List[Tuple[Any, ...]] = []
            unresolved_rows: List[Tuple[Any, ...]] = []
            seen_keys: set[Tuple[Any, ...]] = set()
            for r in chunk:
                case_id = (case_by_ecli.get(r.ecli) if r.ecli else None) or (
                    case_by_celex.get(r.celex) if r.celex else None
                )
                if case_id is None:
                    stats["source_missing"] += 1
                    continue
                nkey = (case_id, r.scheme, r.identifier, r.raw_subdivision or "", r.role, r.source_dataset)
                if nkey in seen_keys:
                    continue
                seen_keys.add(nkey)
                leg_id = leg_map.get((r.scheme, r.identifier))
                prov_id = (
                    prov_map.get((leg_id, r.article.lower()))
                    if leg_id is not None and r.article
                    else None
                )
                row_vals = (
                    case_id, leg_id, prov_id,
                    r.scheme, r.identifier, r.raw_subdivision, r.raw_reference,
                    r.role, r.source_dataset, r.extractor_version, r.match_method, r.confidence,
                )
                if leg_id is not None:
                    resolved_rows.append((len(resolved_rows),) + row_vals)
                else:
                    unresolved_rows.append((len(unresolved_rows),) + row_vals)

            if resolved_rows:
                ret = execute_values(
                    cur, _INSERT_RESOLVED_SQL, resolved_rows,
                    template=_ROW_TEMPLATE, page_size=len(resolved_rows), fetch=True,
                )
                stats["inserted"] += len(ret)
                stats["with_provision"] += sum(1 for (pid,) in ret if pid is not None)
                stats["existing"] += len(resolved_rows) - len(ret)
            if unresolved_rows:
                ret = execute_values(
                    cur, _INSERT_UNRESOLVED_SQL, unresolved_rows,
                    template=_ROW_TEMPLATE, page_size=len(unresolved_rows), fetch=True,
                )
                stats["inserted_unresolved"] += len(ret)
                stats["existing"] += len(unresolved_rows) - len(ret)
        conn.commit()
    return {k: v for k, v in stats.items() if v}


def load_artifact(conn, path: str) -> Dict[str, int]:
    """Load a cjeu_text_treaty.jsonl artifact into cle_v2.case_law_reference."""
    if not os.path.exists(path):
        return {}
    return load_records(conn, read_jsonl(path))


_CANDIDATE_TSQUERY = (
    "'ECHR' | 'CEDH' | 'EMRK' | 'EVRM' | 'CEDU' | "
    "'ICCPR' | 'IVBPR' | 'UNCRPD' | 'CRPD' | 'IVRK' | 'UNCRC' | "
    "'Vluchtelingenverdrag' | 'Flüchtlingskonvention' | "
    "('Geneva' & 'Refugees') | ('Genève' & 'réfugiés') | "
    "('Human' & 'Rights' & 'Rome') | ('droits' & 'homme' & 'Rome')"
)


def extract_pending(
    conn,
    limit: int = 2000,
    out_path: Optional[str] = None,
    load: bool = False,
) -> Dict[str, Any]:
    """Find CJEU cases mentioning treaties that don't yet have cjeu_text_treaty rows."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT c.id
              FROM {SCHEMA}.case_text ct
              JOIN {SCHEMA}.cases c ON c.id = ct.case_id
             WHERE c.ecli LIKE 'ECLI:EU:%%'
               AND ct.fulltext_tsv @@ to_tsquery('simple', %s)
               AND NOT EXISTS (
                   SELECT 1 FROM {SCHEMA}.case_law_reference r
                    WHERE r.case_id = c.id AND r.source_dataset = %s
               )
             ORDER BY c.id
             LIMIT %s
            """,
            (_CANDIDATE_TSQUERY, DATASET, limit),
        )
        case_ids = [int(row[0]) for row in cur.fetchall()]
    conn.rollback()

    all_records: List[TreatyRefRecord] = []
    cases_with_hits = 0
    if case_ids:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.id, c.ecli, c.celex_id, ct.language, ct.fulltext
                  FROM {SCHEMA}.case_text ct
                  JOIN {SCHEMA}.cases c ON c.id = ct.case_id
                 WHERE c.id = ANY(%s) AND ct.fulltext IS NOT NULL
                 ORDER BY c.id, ct.language, ct.id
                """,
                (case_ids,),
            )
            grouped: Dict[int, Tuple[Optional[str], Optional[str], List[Tuple[Optional[str], str]]]] = {}
            for cid, ecli, celex, lang, text in cur.fetchall():
                entry = grouped.get(cid)
                if entry is None:
                    entry = grouped[cid] = (ecli, celex, [])
                entry[2].append((lang, text))
        conn.rollback()
        for cid in sorted(grouped):
            ecli, celex, texts = grouped[cid]
            recs = records_for_case(ecli, celex, texts)
            if recs:
                cases_with_hits += 1
                all_records.extend(recs)

    if out_path:
        write_jsonl(out_path, all_records)
    load_stats = load_records(conn, all_records) if load and all_records else {}
    return {
        "candidates": len(case_ids),
        "cases_with_hits": cases_with_hits,
        "records": len(all_records),
        "load": load_stats,
    }
