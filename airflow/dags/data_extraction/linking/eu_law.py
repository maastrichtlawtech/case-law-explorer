"""
EU-law references: CELEX rules and a text scanner (roadmap R3.2-R3.4).

Pure: nothing here reads a database or calls a remote service.

CELEX (sector, year, type, number), as EUR-Lex builds it:

    directive               3YYYYL####   Richtlijn 2011/95/EU        -> 32011L0095
    regulation              3YYYYR####   Verordening (EU) 2016/679   -> 32016R0679
                                         Verordening (EG) nr. 1408/71 -> 31971R1408
    decision                3YYYYD####   Besluit 2010/405/EU         -> 32010D0405
    framework decision      3YYYYF####   Kaderbesluit 2002/584/JBZ   -> 32002F0584
    treaty article (Cellar) 1YYYYXnnn    12008E267 = art. 267 TFEU (OJ 2008)

Framework decisions are type F in CELEX, not D (32002F0584 is the European
arrest warrant framework decision).

Treaties and the Charter (TREATIES) are a small curated fixture: the CELEX
numbers of the consolidated versions on EUR-Lex (sector 1, type E = TFEU / EC /
EEC treaty, M = TEU, P = Charter). The row stores one canonical CELEX per act
(``raw_resource``); the loader also tries the other versions listed as
alternatives, so it resolves whichever version ``legislation`` holds. Source:
EUR-Lex document numbers of the treaty texts (eur-lex.europa.eu, "Treaties
currently in force" and the consolidated versions 2008, 2012 and 2016), copied
by hand; nothing is fetched at runtime.

The scanner (``scan``) finds, in Dutch, English and French texts:

  * secondary law by number: "Richtlijn 2011/95/EU", "Directive (EU)
    2016/680", "Verordening (EU) nr. 604/2013", "Regulation (EC) No 1408/71",
    "Kaderbesluit 2002/584/JBZ", "Council Framework Decision 2002/584/JHA",
    "Besluit 2010/405/EU", "décision-cadre 2002/584/JAI", and further numbers
    of the same kind in a list ("Richtlijnen 2004/83/EG en 2011/95/EU");
  * treaty and Charter articles: "artikel 267 VWEU", "art. 4, lid 3, VEU",
    "artikel 47 van het Handvest", "Article 267 TFEU", "Articles 7 and 8 of the
    Charter", "article 47 de la Charte", "artikel 234 EG";
  * the GDPR by name: "artikel 6 AVG", "Article 6 GDPR", "Algemene
    verordening gegevensbescherming".

with the article and, where given as a number, the paragraph ("lid 3",
"eerste lid", "3(2)", "§ 2", "paragraph 2"): raw_subdivision "4(3)",
article "4". Unnumbered subparagraphs ("derde alinea", "third paragraph")
and points ("aanhef en onder c") are kept only in the mention text.

Precision rules:

  * a decision ("besluit", "beschikking", "decision", "décision") needs the
    institutional suffix or the "(EU)"-style prefix (Dutch "besluit" is an
    ordinary word, and "Besluit nr. 1/80" of the EEC-Turkey Association
    Council is not an EU act with a CELEX of this form);
  * years must be possible (1952 to next year; two-digit years only before
    1999) and treaty article numbers must exist in that treaty;
  * a treaty or the Charter counts only with an article; a secondary act
    counts on its own too (article-less reference);
  * the bare word "Handvest" / "Charter" / "Charte" means the EU Charter only
    when the text does not mention another charter (European Social Charter,
    UN Charter); in ECtHR texts the full name of the EU Charter must also be
    written somewhere in the text (profile 'echr');
  * "EG"/"EC" (EC Treaty) only directly after an article ("artikel 234 EG"),
    never with a connector, so "Richtlijn 2004/38/EG" never reads as a treaty;
  * EC Treaty articles are read in the Amsterdam numbering when the citing
    decision is from 1 May 1999 on, in the older numbering before that or
    with an "(oud)" / "(old)" / "(ancien)" cue; texts after 1999 still use the
    old numbers without a cue, so these references carry confidence 0.8;
  * anaphora ("die richtlijn", "that Directive") and named acts other than the
    GDPR ("Kwalificatierichtlijn", which names two different directives) are
    not resolved.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from data_extraction.linking.identifiers import SPACE_CLASS

# ---------------------------------------------------------------------------
# Treaties and the Charter (curated fixture; see the module docstring)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Treaty:
    key: str
    raw_resource: str
    alternatives: Tuple[str, ...]
    max_article: int


def _versions(*bases):
    """'12016E', ... -> ('12016E/TXT', '12016E', ...)."""
    out = []
    for base in bases:
        out.extend((f"{base}/TXT", base))
    return tuple(out)


def _treaty(key, bases, max_article, more=()):
    versions = _versions(*bases) + tuple(more)
    return Treaty(key, versions[0], versions[1:], max_article)


TREATIES = {
    t.key: t
    for t in (
        _treaty("TFEU", ("12016E", "12012E", "12008E"), 358),
        _treaty("TEU", ("12016M", "12012M", "12008M"), 55),
        # The 2000 Charter was a proclamation (OJ C 364, 18.12.2000), not a
        # treaty: CELEX 32000X1218(01), tried last.
        _treaty("CHARTER", ("12016P", "12012P", "12007P"), 54, ("32000X1218(01)",)),
        # EC Treaty in the Amsterdam numbering (1 May 1999 to 30 November 2009)
        _treaty("EC", ("12006E", "12002E", "11997E"), 314),
        # EC Treaty before Amsterdam (Maastricht; EEC numbering)
        _treaty("EC_1992", ("11992E",), 248),
        _treaty("TEU_1997", ("12006M", "12002M", "11997M"), 53),
        _treaty("EEC", ("11957E",), 248),
    )
}

AMSTERDAM = date(1999, 5, 1)
LISBON = date(2009, 12, 1)

GDPR_CELEX = "32016R0679"

# ---------------------------------------------------------------------------
# CELEX helpers
# ---------------------------------------------------------------------------

SECONDARY_TYPES = ("L", "R", "D", "F")


def secondary_celex(kind: str, year: int, number: int) -> str:
    """('L', 2011, 95) -> '32011L0095'."""
    if kind not in SECONDARY_TYPES:
        raise ValueError(f"unknown act type {kind!r}")
    return f"3{year:04d}{kind}{number:04d}"


@dataclass(frozen=True)
class CellarTarget:
    """How one Cellar CELEX is stored and resolved (cellar_law_refs)."""

    sector: str
    identifier: str  # normalised CELEX (upper case, no 'CELEX:' prefix)
    alternatives: Tuple[str, ...] = ()
    article: Optional[str] = None  # treaty article encoded in the CELEX


# Sectors that are law references here (R3.2). 5 (preparatory acts) belongs
# to Phase 4 (authority_document); 6 is case law (case_citation); 7-9, C, E
# are national measures, national case law, parliamentary questions, OJ C
# and EFTA documents.
LAW_SECTORS = ("0", "1", "2", "3", "4")

_TREATY_ARTICLE_RE = re.compile(r"^1(\d{4})([A-Z]{1,2})(\d{3})([A-Z]{0,2})$")
_TREATY_ACT_RE = re.compile(r"^1(\d{4})([A-Z]{1,2})(?:/TXT)?$")
_CONSOLIDATED_RE = re.compile(r"^0(\d{4}[A-Z]{1,2}\d{4}(?:\(\d{2}\))?)(?:-\d{8})?$")
# A corrigendum of an act of sectors 2-4: the act followed by R(nn).
_CORRIGENDUM_RE = re.compile(r"^([234]\d{4}[A-Z]{1,2}\d{4}(?:\(\d{2}\))?)R\(\d{2}\)$")


def clean_celex(value) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", "", str(value)).upper()
    text = re.sub(r"^CELEX:", "", text)
    return text or None


def celex_sector(value) -> Optional[str]:
    text = clean_celex(value)
    return text[0] if text else None


def cellar_target(value) -> Optional[CellarTarget]:
    """The CellarTarget of a law CELEX, or None when it is not a law
    reference (LAW_SECTORS).

    '12008E267'  -> article '267' of the TFEU 2008; also tried as '12008E/TXT', '12008E'
    '12012P/TXT' -> the Charter 2012; also tried as '12012P'
    '02016R0679-20160504' (consolidated) -> also tried as '32016R0679'
    '32016R0679R(02)' (corrigendum) -> also tried as '32016R0679'
    other CELEX of sectors 2, 3, 4: exact only
    """
    text = clean_celex(value)
    if not text or text[0] not in LAW_SECTORS:
        return None
    sector = text[0]
    if sector == "1":
        match = _TREATY_ARTICLE_RE.match(text)
        if match:
            year, kind, digits, letters = match.groups()
            base = f"1{year}{kind}"
            article = str(int(digits)) + letters.lower()
            if article == "0":
                return CellarTarget(sector, text)
            return CellarTarget(sector, text, (f"{base}/TXT", base), article)
        match = _TREATY_ACT_RE.match(text)
        if match:
            base = f"1{match.group(1)}{match.group(2)}"
            return CellarTarget(sector, text, tuple(v for v in (base, f"{base}/TXT") if v != text))
        return CellarTarget(sector, text)
    if sector == "0":
        match = _CONSOLIDATED_RE.match(text)
        if match:
            return CellarTarget(sector, text, ("3" + match.group(1),))
        return CellarTarget(sector, text)
    match = _CORRIGENDUM_RE.match(text)
    if match:
        return CellarTarget(sector, text, (match.group(1),))
    return CellarTarget(sector, text)


# ---------------------------------------------------------------------------
# Text scanner
# ---------------------------------------------------------------------------

_S = SPACE_CLASS
_WS = r"[\s   ]"

_ORDINALS = {
    # nl
    "eerste": 1, "tweede": 2, "derde": 3, "vierde": 4, "vijfde": 5, "zesde": 6,
    "zevende": 7, "achtste": 8, "negende": 9, "tiende": 10,
}  # fmt: skip

_ACT_WORDS = (
    # (regex, CELEX type); longest alternatives first
    (r"uitvoeringsrichtlijn|gedelegeerde" + _WS + r"+richtlijn|richtlijnen|richtlijn", "L"),
    (r"directives|directive", "L"),
    (r"uitvoeringsverordening|gedelegeerde" + _WS + r"+verordening|verordeningen|verordening", "R"),
    (r"regulations|regulation|règlements|règlement|reglement", "R"),
    (r"kaderbesluiten|kaderbesluit|framework" + _WS + r"+decisions?", "F"),
    (r"décision[-" + _S[1:-1] + r"]cadre|decision-cadre", "F"),
    (r"uitvoeringsbesluit|besluiten|besluit|beschikkingen|beschikking", "D"),
    (r"decisions|decision|décisions|décision", "D"),
)
_PREFIX = r"\((?P<prefix>EU|EG|EEG|EC|EEC|CE|CEE|UE|Euratom|EGKS|EGA|ECSC)\)"
_SUFFIXES = (
    "EU|EG|EEG|EC|EEC|CE|CEE|UE|JBZ|JHA|JAI|GBVB|CFSP|PESC|Euratom|EURATOM|EGKS|ECSC|CECA|GVDB|CSDP"
)
_NR = r"(?:nr\.?|no\.?|No\.?|n°|nº|n" + _S + r"?o|number)"
_NUMBER = (
    r"(?P<a>\d{1,4})" + _S + r"?/" + _S + r"?(?P<b>\d{1,4})"
    r"(?:" + _S + r"?/" + _S + r"?(?P<suffix>" + _SUFFIXES + r"))?(?![\d/])"
)

_ACT_RE = re.compile(
    r"(?i)(?<![\w-])(?P<word>"
    + "|".join(f"(?P<w{i}>{word})" for i, (word, _kind) in enumerate(_ACT_WORDS))
    + r")"
    + _WS
    + r"+(?:(?-i:"
    + _PREFIX
    + r")"
    + _WS
    + r"*)?(?:(?P<nr>"
    + _NR
    + r")"
    + _WS
    + r"*)?(?-i:"
    + _NUMBER
    + r")"
)
_ACT_KINDS = {f"w{i}": kind for i, (_word, kind) in enumerate(_ACT_WORDS)}

# Further numbers of the same kind right after an act: "2004/83/EG en 2011/95/EU".
_MORE_RE = re.compile(
    r"(?i)"
    + _WS
    + r"*(?:,|\ben\b|\band\b|\bet\b|\bof\b|\bor\b|\bou\b)"
    + _WS
    + r"*(?P<ref>(?:(?-i:"
    + _PREFIX
    + r")"
    + _WS
    + r"*)?(?:(?P<nr>"
    + _NR
    + r")"
    + _WS
    + r"*)?(?-i:"
    + _NUMBER
    + r"))"
)

# Treaty names: (regex, treaty key, needs the article right before it, case-sensitive?)
_TREATY_NAMES = (
    # TFEU
    (r"Verdrag" + _WS + r"+betreffende" + _WS + r"+de" + _WS + r"+werking" + _WS + r"+van"
     + _WS + r"+de" + _WS + r"+Europese" + _WS + r"+Unie", "TFEU", False, False),
    (r"Treaty" + _WS + r"+on" + _WS + r"+the" + _WS + r"+Functioning" + _WS + r"+of" + _WS
     + r"+the" + _WS + r"+European" + _WS + r"+Union", "TFEU", False, False),
    (r"Traité" + _WS + r"+sur" + _WS + r"+le" + _WS + r"+fonctionnement" + _WS + r"+de"
     + _WS + r"+l['’]" + _WS + r"*Union" + _WS + r"+européenne", "TFEU", False, False),
    (r"VWEU|TFEU|TFUE|AEUV", "TFEU", False, True),
    # TEU
    (r"Verdrag" + _WS + r"+betreffende" + _WS + r"+de" + _WS + r"+Europese" + _WS + r"+Unie",
     "TEU", False, False),
    (r"Treaty" + _WS + r"+on" + _WS + r"+European" + _WS + r"+Union", "TEU", False, False),
    (r"Traité" + _WS + r"+sur" + _WS + r"+l['’]" + _WS + r"*Union" + _WS + r"+européenne",
     "TEU", False, False),
    (r"VEU|TEU|TUE", "TEU", False, True),
    # Charter (full names; the bare word is handled by _BARE_CHARTER)
    (r"Handvest" + _WS + r"+van" + _WS + r"+de" + _WS + r"+grondrechten(?:" + _WS + r"+van"
     + _WS + r"+de" + _WS + r"+Europese" + _WS + r"+Unie|" + _WS + r"+van" + _WS + r"+de"
     + _WS + r"+EU)?", "CHARTER", False, False),
    (r"EU-Handvest|Handvest" + _WS + r"+EU\b|Handvest" + _WS + r"+van" + _WS + r"+de" + _WS
     + r"+EU", "CHARTER", False, False),
    (r"Charter" + _WS + r"+of" + _WS + r"+Fundamental" + _WS + r"+Rights(?:" + _WS + r"+of"
     + _WS + r"+the" + _WS + r"+European" + _WS + r"+Union|" + _WS + r"+of" + _WS + r"+the"
     + _WS + r"+EU)?", "CHARTER", False, False),
    (r"EU" + _WS + r"+Charter|Charter" + _WS + r"+of" + _WS + r"+the" + _WS + r"+EU",
     "CHARTER", False, False),
    (r"Charte" + _WS + r"+des" + _WS + r"+droits" + _WS + r"+fondamentaux(?:" + _WS + r"+de"
     + _WS + r"+l['’]" + _WS + r"*Union" + _WS + r"+européenne)?", "CHARTER", False, False),
    # EC Treaty
    (r"EG-Verdrag|EG" + _WS + r"+Verdrag|Verdrag" + _WS + r"+tot" + _WS + r"+oprichting"
     + _WS + r"+van" + _WS + r"+de" + _WS + r"+Europese" + _WS + r"+Gemeenschap(?!pen)",
     "EC", False, False),
    (r"EC" + _WS + r"+Treaty|Treaty" + _WS + r"+establishing" + _WS + r"+the" + _WS
     + r"+European" + _WS + r"+Community|traité" + _WS + r"+CE\b", "EC", False, False),
    (r"EG|EC", "EC", True, True),
    # EEC Treaty
    (r"EEG-Verdrag|EEG" + _WS + r"+Verdrag|EEC" + _WS + r"+Treaty|Treaty" + _WS
     + r"+establishing" + _WS + r"+the" + _WS + r"+European" + _WS + r"+Economic" + _WS
     + r"+Community|traité" + _WS + r"+CEE\b", "EEC", False, False),
    # GDPR by name
    (r"Algemene" + _WS + r"+verordening" + _WS + r"+gegevensbescherming|General" + _WS
     + r"+Data" + _WS + r"+Protection" + _WS + r"+Regulation|règlement" + _WS
     + r"+général" + _WS + r"+sur" + _WS + r"+la" + _WS + r"+protection" + _WS + r"+des"
     + _WS + r"+données", "GDPR", False, False),
    (r"AVG|GDPR|RGPD", "GDPR_ABBR", False, True),
)  # fmt: skip

_BARE_CHARTER_RE = re.compile(r"(?<![\w-])(?:Handvest|Charter|Charte)(?![\w-])")

_NAME_RE = re.compile(
    "|".join(
        f"(?P<t{i}>(?<![\\w-])(?{'-i' if case else 'i'}:{rx})(?![\\w-]))"
        for i, (rx, _k, _adj, case) in enumerate(_TREATY_NAMES)
    )
)
_NAME_INFO = {f"t{i}": (key, adj) for i, (_rx, key, adj, _case) in enumerate(_TREATY_NAMES)}

# Another charter in the text makes the bare word ambiguous.
_OTHER_CHARTER_RE = re.compile(
    r"(?i)Sociaal" + _WS + r"+Handvest|Social" + _WS + r"+Charter|Charte" + _WS + r"+sociale"
    r"|Handvest" + _WS + r"+(?:van" + _WS + r"+de|der)" + _WS + r"+Verenigde" + _WS + r"+Naties"
    r"|VN-Handvest|(?:United"
    + _WS
    + r"+Nations|UN)"
    + _WS
    + r"+Charter|Charter"
    + _WS
    + r"+of"
    + _WS
    + r"+the"
    + _WS
    + r"+United"
    + _WS
    + r"+Nations|Charte"
    + _WS
    + r"+des"
    + _WS
    + r"+Nations"
    + _WS
    + r"+Unies"
)
_FULL_CHARTER_RE = re.compile(
    r"(?i)Handvest"
    + _WS
    + r"+van"
    + _WS
    + r"+de"
    + _WS
    + r"+grondrechten|Charter"
    + _WS
    + r"+of"
    + _WS
    + r"+Fundamental"
    + _WS
    + r"+Rights|Charte"
    + _WS
    + r"+des"
    + _WS
    + r"+droits"
    + _WS
    + r"+fondamentaux"
)

# --- the article clause before a name or an act ---------------------------

_ART_WORD = r"(?:artikelen|artikel|artt?\.|art\b|articles|article|arts\.)"
_ART_NUM = r"(?P<{n}>\d{{1,3}}(?:[a-z](?![a-z]))?)(?![\d:./]\w)(?:\((?P<{p}>\d{{1,2}})\))?"
_PARA_SPEC = (
    r"(?:lid" + _WS + r"+(?P<{l}>\d{{1,2}})"
    r"|(?P<{o}>eerste|tweede|derde|vierde|vijfde|zesde|zevende|achtste|negende|tiende)"
    + _WS
    + r"+lid"
    r"|(?P<{d}>\d{{1,2}})(?:e|ste|de)" + _WS + r"+lid"
    r"|§" + _WS + r"*(?P<{s}>\d{{1,2}})"
    r"|paragraph(?:e)?" + _WS + r"+(?P<{g}>\d{{1,2}})"
    r"|para\." + _WS + r"*(?P<{q}>\d{{1,2}}))"
)
# Sub-designations that may follow an article and are not kept.
_OTHER_SPEC = (
    r"(?:(?:eerste|tweede|derde|vierde|vijfde|zesde)" + _WS + r"+(?:alinea|volzin)"
    r"|(?:first|second|third|fourth|fifth|sixth)" + _WS + r"+(?:sub)?paragraph"
    r"|(?:premier|deuxième|troisième|quatrième)" + _WS + r"+alinéa"
    r"|aanhef(?:" + _WS + r"+en)?(?:" + _WS + r"+onder" + _WS + r"+[a-z0-9]{1,4}\)?)?"
    r"|onder" + _WS + r"+[a-z0-9]{1,4}\)?|sub" + _WS + r"+[a-z0-9]{1,4}"
    r"|point" + _WS + r"+\(?[a-z0-9]{1,4}\)?|points?" + _WS + r"+[a-z]\)"
    r"|letter" + _WS + r"+[a-z]|sous" + _WS + r"+[a-z]\)|\([a-z]{1,4}\)|\(\d{1,2}\))"
)


def _item(i: int) -> str:
    names = {k: f"{k}{i}" for k in ("n", "p", "l", "o", "d", "s", "g", "q")}
    spec = (
        r"(?:"
        + _WS
        + r"*,?"
        + _WS
        + r"*(?:"
        + _PARA_SPEC.format(**names)
        + r"|"
        + _OTHER_SPEC
        + r"))"
    )
    return (
        r"(?:"
        + _ART_WORD
        + _WS
        + r"*)?"
        + _ART_NUM.format(**names)
        + spec
        + r"{0,4}"
        + _WS
        + r"*,?"
    )


_MAX_ITEMS = 4
_LIST_SEP = r"(?:" + _WS + r"*(?:,|\ben\b|\band\b|\bet\b|\bjuncto\b|\bjo\.)" + _WS + r"*)"
_CONNECTOR = (
    r"(?:van" + _WS + r"+(?:de|het)" + _WS + r"+|van" + _WS + r"+|of" + _WS + r"+the" + _WS
    + r"+|of" + _WS + r"+|de" + _WS + r"+la" + _WS + r"+|du" + _WS + r"+|de" + _WS
    + r"+l['’]" + _WS + r"*|de" + _WS + r"+)"
)  # fmt: skip
_CLAUSE_BODY = (
    r"(?i)(?<![\w-])"
    + _ART_WORD
    + _WS
    + r"*"
    + _item(0)
    + "".join(r"(?:" + _LIST_SEP + _item(i) + r")?" for i in range(1, _MAX_ITEMS))
    + _WS
    + r"*"
)
_CLAUSE_RE = re.compile(_CLAUSE_BODY + r"(?P<conn>" + _CONNECTOR + r")?$")
_CLAUSE_ADJACENT_RE = re.compile(_CLAUSE_BODY + r"$")
_LOOKBACK = 220


@dataclass(frozen=True)
class ArticleRef:
    article: str  # '47', '13a'
    paragraph: Optional[int] = None

    @property
    def subdivision(self) -> str:
        return f"{self.article}({self.paragraph})" if self.paragraph else self.article


def _clause_articles(match) -> List[ArticleRef]:
    out = []
    for i in range(_MAX_ITEMS):
        number = match.group(f"n{i}")
        if number is None:
            continue
        paragraph = None
        for k in ("p", "l", "d", "s", "g", "q"):
            value = match.group(f"{k}{i}")
            if value:
                paragraph = int(value)
                break
        ordinal = match.group(f"o{i}")
        if paragraph is None and ordinal:
            paragraph = _ORDINALS[ordinal.lower()]
        out.append(ArticleRef(number.lower(), paragraph or None))
    return out


def article_clause(text: str, end: int, adjacent_only: bool = False):
    """The article clause ending right before ``end`` ("artikel 4, lid 3, ",
    "Articles 7 and 8 of the "), as (start, [ArticleRef]) or None."""
    window_start = max(0, end - _LOOKBACK)
    window = text[window_start:end]
    pattern = _CLAUSE_ADJACENT_RE if adjacent_only else _CLAUSE_RE
    match = pattern.search(window)
    if not match:
        return None
    articles = _clause_articles(match)
    if not articles:
        return None
    return window_start + match.start(), articles


@dataclass(frozen=True)
class EuLawHit:
    """One reference found in a text."""

    start: int
    end: int
    celex: str  # canonical CELEX (raw_resource)
    alternatives: Tuple[str, ...]
    method: str  # act_number | treaty_article | act_name
    confidence: float
    article: Optional[ArticleRef] = None

    @property
    def raw_subdivision(self) -> Optional[str]:
        return self.article.subdivision if self.article else None


def _year(value: str) -> Optional[int]:
    """'93' -> 1993 (two-digit years 1952-1998), '2011' -> 2011, '1995' ->
    1995 (four-digit years 1952 to next year)."""
    if len(value) == 2:
        year = 1900 + int(value)
        return year if 1952 <= year < 1999 else None
    if len(value) == 4:
        year = int(value)
        return year if 1952 <= year <= date.today().year + 1 else None
    return None


_EU_PREFIXES = ("EU", "UE")


def act_celex(
    kind: str,
    a: str,
    b: str,
    has_nr: bool,
    max_year: Optional[int] = None,
    prefix: Optional[str] = None,
):
    """CELEX of a numbered act, or None when the number is not possible.

    Directives and (framework) decisions are year/number. Regulations are
    number/year until 2014 ("1408/71", "nr. 604/2013") and year/number from
    2015 ("(EU) 2016/679", also written "(EU) nr. 2016/679"): year/number when
    a is a four-digit year from 2015 on, unless b is a four-digit year up to
    2014 ("2016/2000": regulation 2016 of 2000), and then not when the prefix
    is (EU)/(UE), which no regulation before 2010 carries. has_nr no longer
    decides (kept for the callers)."""
    if kind == "R":
        a_year = _year(a) if len(a) == 4 else None
        b_year = _year(b) if len(b) == 4 else None
        year_first = a_year is not None and a_year >= 2015
        if year_first and b_year is not None and b_year <= 2014:
            # both year-like: the older style, unless the prefix rules it out
            year_first = prefix in _EU_PREFIXES and b_year < 2010
        if year_first:
            year, number = a_year, int(b)
        else:
            year, number = _year(b), int(a)
            if year is not None and year >= 2015:
                year = None  # number/year ended with 2014
    else:
        year, number = _year(a), int(b)
    if year is None or not 1 <= number <= 9999:
        return None
    if max_year is not None and year > max_year:
        return None
    return secondary_celex(kind, year, number)


# "artikel 85 EG-Verdrag (oud)", "Article 85 EC (old)", "article 85 CE (ancien)":
# the numbering before the Treaty of Amsterdam.
_OLD_NUMBERING_RE = re.compile(r"(?i)" + _WS + r"*\((?:oud|old|ancien|ex)\b")


def treaty_for(key: str, decided: Optional[date]) -> Optional[Treaty]:
    """The treaty a name means at the citing decision's date."""
    if key == "EC" and decided is not None and decided < AMSTERDAM:
        return TREATIES["EC_1992"]
    if key == "TEU" and decided is not None and decided < LISBON:
        return TREATIES["TEU_1997"]
    return TREATIES.get(key)


def bare_charter_allowed(text: str, profile: str) -> bool:
    """May the bare word Handvest/Charter/Charte be read as the EU Charter?"""
    if _OTHER_CHARTER_RE.search(text):
        return False
    if profile == "echr":
        return bool(_FULL_CHARTER_RE.search(text))
    return True


def _article_ok(treaty: Treaty, article: ArticleRef) -> bool:
    digits = re.match(r"\d+", article.article)
    return bool(digits) and 1 <= int(digits.group(0)) <= treaty.max_article


def scan(text: str, decided: Optional[date] = None, profile: str = "rs") -> List[EuLawHit]:
    """Every EU-law reference in text, in text order (see the module docstring).

    ``decided`` (the citing decision's date) rejects acts from later years and
    picks the treaty version for "EG"/"VEU"; ``profile`` is 'rs' or 'echr'
    (bare Charter rule)."""
    if not text:
        return []
    max_year = decided.year if decided else None
    hits: List[EuLawHit] = []
    taken: List[Tuple[int, int]] = []

    def free(start, end):
        return all(end <= s or start >= e for s, e in taken)

    # 1. numbered secondary law
    for match in _ACT_RE.finditer(text):
        kind = next(_ACT_KINDS[g] for g in _ACT_KINDS if match.group(g))
        found = [(match.start(), match.end(), match)]
        position = match.end()
        while True:
            more = _MORE_RE.match(text, position)
            if not more or not (more.group("suffix") or more.group("prefix") or more.group("nr")):
                break
            found.append((more.start(), more.end(), more))
            position = more.end()
        for index, (start, end, m) in enumerate(found):
            prefix, suffix, nr = m.group("prefix"), m.group("suffix"), m.group("nr")
            if kind == "D" and not (prefix or suffix):
                continue
            celex = act_celex(kind, m.group("a"), m.group("b"), bool(nr), max_year, prefix)
            if celex is None:
                continue
            confidence = 0.95 if (prefix or suffix or (kind == "R" and nr)) else 0.85
            # The article clause applies to the first act of a list only.
            clause = article_clause(text, match.start()) if index == 0 else None
            if index > 0:
                start = m.start("ref")
            if clause:
                c_start, articles = clause
                for art in articles:
                    hits.append(EuLawHit(c_start, end, celex, (), "act_number", confidence, art))
                taken.append((c_start, end))
            else:
                hits.append(EuLawHit(start, end, celex, (), "act_number", confidence))
                taken.append((start, end))

    # 2. treaties, the Charter and the GDPR by name
    bare_ok = bare_charter_allowed(text, profile)
    name_matches = [(m.start(), m.end(), _NAME_INFO[m.lastgroup]) for m in _NAME_RE.finditer(text)]
    if bare_ok:
        named = [(s, e) for s, e, _i in name_matches]
        for m in _BARE_CHARTER_RE.finditer(text):
            if any(s <= m.start() < e for s, e in named):
                continue
            name_matches.append((m.start(), m.end(), ("CHARTER", False)))
    for start, end, (key, adjacent) in sorted(name_matches):
        if not free(start, end):
            continue
        if key in ("GDPR", "GDPR_ABBR"):
            clause = article_clause(text, start, adjacent_only=False)
            if clause:
                c_start, articles = clause
                for art in articles:
                    hits.append(EuLawHit(c_start, end, GDPR_CELEX, (), "act_name", 0.9, art))
                taken.append((c_start, end))
            elif key == "GDPR":
                hits.append(EuLawHit(start, end, GDPR_CELEX, (), "act_name", 0.9))
                taken.append((start, end))
            continue
        treaty = treaty_for(key, decided)
        if key == "EC" and _OLD_NUMBERING_RE.match(text, end):
            treaty = TREATIES["EC_1992"]
        if treaty is None:
            continue
        clause = article_clause(text, start, adjacent_only=adjacent)
        if not clause:
            continue
        c_start, articles = clause
        articles = [a for a in articles if _article_ok(treaty, a)]
        if not articles:
            continue
        # EC Treaty articles were renumbered on 1 May 1999 and texts after that
        # date still cite the old numbers ("artikel 85 EG-Verdrag" next to
        # "art. 81 EG" for the same provision): lower confidence.
        confidence = 0.8 if key == "EC" else 0.9 if adjacent else 0.95
        for art in articles:
            hits.append(
                EuLawHit(
                    c_start,
                    end,
                    treaty.raw_resource,
                    treaty.alternatives,
                    "treaty_article",
                    confidence,
                    art,
                )
            )
        taken.append((c_start, end))
    hits.sort(key=lambda h: (h.start, h.end, h.celex, h.raw_subdivision or ""))
    return hits
