"""
Patterns for cited authorities that are neither cases of the three
collections nor legislation (roadmap R4.1, R4.2, R4.4, R4.5), and the
identifiers they normalise to.

Pure functions only: ``scan(text)`` returns the references found in one text,
each with the document it names (authority_artifact.AuthorityDoc), its exact
offsets and the pinpoint written after it. Nothing here reads a database or
calls a remote service; URLs are built from the identifier, never fetched.

Kinds and identifiers
---------------------

nl_parliamentary_paper (R4.1)
    "Kamerstukken II 2015/16, 34 356, nr. 3, p. 12"  -> kst-34356-3
    "Kamerstukken I 2016/17, 34 356, C"               -> kst-34356-C
    "Kamerstukken II 2016/17, 34 550 VI, nr. 2"       -> kst-34550-VI-2
    "Kamerstukken II 2014/15, 21 501-20, nr. 1000"    -> kst-21501-20-1000
    scheme 'officielebekendmakingen' (the document ids of
    zoek.officielebekendmakingen.nl; url .../<id>.html). A dossier without a
    paper number ("Kamerstukken II 2015/16, 34 356") -> scheme
    'nl_kamerstuk_dossier', identifier '34356', url .../dossier/34356.
    "Handelingen II 2014/15, nr. 45, item 7"          -> h-tk-20142015-45-7
    (scheme 'officielebekendmakingen'); without the item, scheme
    'nl_handelingen' (h-tk-20142015-45, no url); by page only
    ("Handelingen II 2005/06, p. 1234"), scheme 'nl_handelingen_page'
    (h-tk-20052006-p1234, no url).
    A bare "MvT" or "memorie van toelichting" names no document and is not
    written; the Kamerstukken reference that usually follows it is.

nl_official_publication (decision, see below)
    "Stb. 2017, 123" -> stb-2017-123, "Stcrt. 2019, 12345" -> stcrt-2019-12345,
    "Trb. 1990, 12" -> trb-1990-12; scheme 'officielebekendmakingen'.

    Decision: a Staatsblad number names the publication of an act or decree,
    not the act. The legislation table holds BWB acts and cannot resolve a
    publication number, and the cited publication is often the nota van
    toelichting of a decree or the decree fixing an entry into force, so these
    are kept as authority documents of their own kind rather than as
    legislation. Staatscourant numbers are how policy rules are cited (R4.2).
    Behind AUTHORITY_NL_OFFICIAL_PUBLICATIONS (default on).

nl_policy_rule (R4.2)
    Vreemdelingencirculaire 2000: one document per part, the paragraph as
    pinpoint: "paragraaf C2/3.2 Vc 2000", "Vc 2000 (C) C2/3.2",
    "Vreemdelingencirculaire 2000, B8/3.1" -> scheme
    'nl_vreemdelingencirculaire', identifier 'vc2000-C' (or 'vc2000' when no
    part is written), pinpoint 'C2/3.2'.
    "WBV 2014/1" (wijzigingsbesluit Vreemdelingencirculaire) -> scheme 'nl_wbv',
    identifier '2014/1'.
    Decrees cited by date and reference number, as the tax authorities cite
    theirs: "besluit van de staatssecretaris van Financiën van 8 juli 2014,
    nr. DGB 2014/296M" -> scheme 'nl_besluit_kenmerk', identifier
    'DGB2014/296M', date 2014-07-08. A reference needs letters before the year
    or a year-number of at least three digits, so an ordinary decision number
    is not taken for one.
    Named "beleidsregels" without a number or publication are not written:
    a bare name is no identifier. When they are cited with their
    Staatscourant number, that number is.

national_court_decision (R4.4)
    Full ECLIs of other countries' courts ("ECLI:BE:GHCC:2021:ARR.168",
    "ECLI:DE:BGH:2018:141118BXII292.16.0"); scheme 'ecli', issuer the country
    and court codes ('BE:GHCC'). ECLIs of the three collections (NL, EU, CE)
    are the link extractors' business and are left out here.

un_treaty_body (R4.5)
    UN document symbols of the treaty bodies ("CCPR/C/GC/36",
    "CCPR/C/108/D/2149/2012", "CAT/C/GC/4", "E/C.12/GC/20"); scheme
    'un_symbol', url https://undocs.org/<symbol>. Communications cited by
    number with the committee named in the same sentence ("Human Rights
    Committee, communication No. 2149/2012") -> scheme 'un_communication',
    identifier 'CCPR/2149/2012'.

coe_body (R4.5)
    Venice Commission "CDL-AD(2016)007" (scheme 'coe_cdl'); CPT
    "CPT/Inf (2017) 1" -> 'CPT/Inf(2017)1' (scheme 'coe_cpt'); GRECO
    "GrecoEval4Rep(2016)3" (scheme 'coe_greco'); ECRI reports "CRI(2019)19"
    (scheme 'coe_ecri') and "ECRI General Policy Recommendation No. 15"
    (scheme 'coe_ecri_gpr', identifier '15'); Committee of Ministers
    "CM/Rec(2010)5", "CM/ResDH(2019)1", "Recommendation Rec(2006)2" (scheme
    'coe_cm'); Commissioner for Human Rights "CommDH(2019)1" (scheme
    'coe_commdh').
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence

from data_extraction.linking.authority_artifact import AuthorityDoc
from data_extraction.linking.text_common import DATE_RE, parse_date_match

OB_URL = "https://zoek.officielebekendmakingen.nl/{}.html"
OB_DOSSIER_URL = "https://zoek.officielebekendmakingen.nl/dossier/{}"
UNDOCS_URL = "https://undocs.org/{}"

_DASH_CHARS = "‐‑‒–—-"  # hyphen last: literal inside a class
_DASH = "[" + _DASH_CHARS + "]"
_SESSION_SEP = "[/" + _DASH_CHARS + "]"
_SP = r"[ \t  ]"  # spaces within one line


@dataclass(frozen=True)
class AuthorityHit:
    doc: AuthorityDoc
    start: int
    end: int
    pinpoint: Optional[str]
    method: str  # the pattern that found it
    confidence: float


def _session(first: str, second: str) -> Optional[str]:
    """'2015', '16' -> '20152016'; None when the years do not follow each other."""
    y1 = int(first)
    y2 = int(second)
    if len(second) == 2:
        if y2 != (y1 + 1) % 100:
            return None
        y2 = y1 + 1
    elif y2 != y1 + 1:
        return None
    return f"{y1}{y2}"


def _clean_pin(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return re.sub(_DASH, "-", value) or None


# ---------------------------------------------------------------------------
# R4.1 Kamerstukken and Handelingen
# ---------------------------------------------------------------------------

_PIN = (
    r"(?:(?:p|pag|blz|blad)\.?"
    + _SP
    + r"*\d+(?:"
    + _SP
    + r"*"
    + _DASH
    + _SP
    + r"*\d+)?|(?:par\.|§)"
    + _SP
    + r"*\d+(?:\.\d+)*)"
)  # noqa: E501

KST_RE = re.compile(
    r"(?<![\w.])(?:"
    r"(?:Kamerstukken|Kamerstuk|Kst\.)"
    r"(?:"
    + _SP
    + r"+(?P<ch1>II|I|TK|EK|Tweede"
    + _SP
    + r"+Kamer|Eerste"
    + _SP
    + r"+Kamer)(?![\w.]))?"
    r"|(?P<ch2>TK|EK)(?=" + _SP + r"+(?:19|20)\d{2}" + _SP + r"*" + _SESSION_SEP + r")"
    r")"
    r"(?:"
    + _SP
    + r"*,?"
    + _SP
    + r"*(?P<s1>(?:19|20)\d{2})"
    + _SP
    + r"*"
    + _SESSION_SEP
    + _SP
    + r"*(?P<s2>\d{4}|\d{2}))?"  # noqa: E501
    r"" + _SP + r"*,?" + _SP + r"*(?:nr\." + _SP + r"*)?"
    r"(?P<dossier>\d{2}" + _SP + r"?\d{3}|\d{4})(?![\d/])"
    r"(?:" + _DASH + r"(?P<dash>\d{1,3})(?!\d))?"
    r"(?:" + _SP + r"+(?P<sub>[IVXL]{1,6}|[A-Z])(?![\w.]))?"
    r"(?:" + _SP + r"*\((?:R" + _SP + r"?\d{3,4})\))?"
    r"(?:" + _SP + r"*,?" + _SP + r"*(?:(?:nr|no|nummer)\.?" + _SP + r"*(?P<nr>\d{1,4})(?![\d/])"
    r"|," + _SP + r"*(?P<nr2>\d{1,4})(?![\d/.])"
    r"|," + _SP + r"*(?P<letter>[A-Z]{1,3})(?![\w.])))?"
    r"(?:" + _SP + r"*," + _SP + r"*(?P<pin>" + _PIN + r"))?"
)

HAND_RE = re.compile(
    r"(?<![\w.])(?:Handelingen|Hand\.)" + _SP + r"+(?P<ch>II|I|TK|EK)(?![\w.])"
    r""
    + _SP
    + r"*,?"
    + _SP
    + r"*(?P<s1>(?:19|20)\d{2})"
    + _SP
    + r"*"
    + _SESSION_SEP
    + _SP
    + r"*(?P<s2>\d{4}|\d{2})"  # noqa: E501
    r"" + _SP + r"*,?" + _SP + r"*(?:"
    r"(?:nr|no)\.?" + _SP + r"*(?P<nr>\d{1,3})(?!\d)"
    r"(?:" + _SP + r"*,?" + _SP + r"*(?:item|punt)" + _SP + r"*(?P<item>\d{1,3})(?!\d))?"
    r"(?:" + _SP + r"*," + _SP + r"*(?P<pin>" + _PIN + r"))?"
    r"|(?P<page>(?:p|pag|blz)\.?"
    + _SP
    + r"*(?P<pageno>\d{1,5})(?:"
    + _SP
    + r"*"
    + _DASH
    + _SP
    + r"*\d+)?)"  # noqa: E501
    r")"
)


def _chamber(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value)
    if value in ("II", "TK", "Tweede Kamer"):
        return "tk"
    if value in ("I", "EK", "Eerste Kamer"):
        return "ek"
    return None


def kamerstuk_hits(text: str) -> List[AuthorityHit]:
    hits = []
    for m in KST_RE.finditer(text):
        chamber = _chamber(m.group("ch1") or m.group("ch2"))
        if m.group("s1") and _session(m.group("s1"), m.group("s2")) is None:
            continue
        if m.group("ch2") and not m.group("s1"):
            continue
        dossier = re.sub(r"\D", "", m.group("dossier"))
        if not 1000 <= int(dossier) <= 99999:
            continue
        number = m.group("nr") or m.group("nr2")
        letter = m.group("letter")
        if letter and chamber != "ek":
            # letters number the Eerste Kamer's papers only; elsewhere the
            # match stops at the dossier
            letter = None
        parts = [dossier]
        if m.group("dash"):
            parts.append(m.group("dash"))
        if m.group("sub"):
            parts.append(m.group("sub"))
        end = m.end()
        if m.group("letter") and not letter:
            # an ignored letter and anything after it are not part of the reference
            end = max(m.end(g) for g in ("dossier", "dash", "sub") if m.group(g) is not None)
            pin = None
        else:
            pin = m.group("pin")
        if number or letter:
            paper = str(int(number)) if number else letter
            identifier = "kst-" + "-".join(parts + [paper])
            doc = AuthorityDoc(
                kind="nl_parliamentary_paper",
                identifier_scheme="officielebekendmakingen",
                identifier=identifier,
                title=f"Kamerstuk {' '.join(parts)}, nr. {paper}",
                url=OB_URL.format(identifier),
            )
            confidence = 0.95
        else:
            if not (m.group("s1") or chamber):
                continue  # "Kamerstuk 1234" alone: too little to call it a dossier
            # A sub-dossier without a paper number names its main dossier.
            identifier = parts[0]
            doc = AuthorityDoc(
                kind="nl_parliamentary_paper",
                identifier_scheme="nl_kamerstuk_dossier",
                identifier=identifier,
                title=f"Kamerstukdossier {identifier}",
                url=OB_DOSSIER_URL.format(identifier),
            )
            confidence = 0.85
        hits.append(AuthorityHit(doc, m.start(), end, _clean_pin(pin), "nl_kamerstuk", confidence))
    return hits


def handelingen_hits(text: str) -> List[AuthorityHit]:
    hits = []
    for m in HAND_RE.finditer(text):
        session = _session(m.group("s1"), m.group("s2"))
        chamber = _chamber(m.group("ch"))
        if session is None or chamber is None:
            continue
        base = f"h-{chamber}-{session}"
        if m.group("nr"):
            nr = str(int(m.group("nr")))
            if m.group("item"):
                identifier = f"{base}-{nr}-{int(m.group('item'))}"
                doc = AuthorityDoc(
                    kind="nl_parliamentary_paper",
                    identifier_scheme="officielebekendmakingen",
                    identifier=identifier,
                    title=f"Handelingen {chamber.upper()} {session[:4]}/{session[4:]}, "
                    f"nr. {nr}, item {int(m.group('item'))}",
                    url=OB_URL.format(identifier),
                )
                confidence = 0.95
            else:
                identifier = f"{base}-{nr}"
                doc = AuthorityDoc(
                    kind="nl_parliamentary_paper",
                    identifier_scheme="nl_handelingen",
                    identifier=identifier,
                    title=f"Handelingen {chamber.upper()} {session[:4]}/{session[4:]}, nr. {nr}",
                )
                confidence = 0.9
            pin = m.group("pin")
        else:
            page = str(int(m.group("pageno")))
            identifier = f"{base}-p{page}"
            doc = AuthorityDoc(
                kind="nl_parliamentary_paper",
                identifier_scheme="nl_handelingen_page",
                identifier=identifier,
                title=f"Handelingen {chamber.upper()} {session[:4]}/{session[4:]}, p. {page}",
            )
            confidence = 0.85
            pin = m.group("page")
        hits.append(
            AuthorityHit(doc, m.start(), m.end(), _clean_pin(pin), "nl_handelingen", confidence)
        )
    return hits


# ---------------------------------------------------------------------------
# Staatsblad, Staatscourant, Tractatenblad
# ---------------------------------------------------------------------------

OFFICIAL_RE = re.compile(
    r"(?<![\w.])(?P<pub>Stb|Stcrt|Trb|Staatsblad|Staatscourant|Tractatenblad)\.?"
    r"" + _SP + r"*(?P<year>(?:18|19|20)\d{2})" + _SP + r"*,?" + _SP + r"*(?:nr\.?" + _SP + r"*)?"
    r"(?P<nr>\d{1,6})(?![\d/,.]\d)(?![\w/])"
)
_OFFICIAL_CODE = {
    "stb": "stb",
    "staatsblad": "stb",
    "stcrt": "stcrt",
    "staatscourant": "stcrt",
    "trb": "trb",
    "tractatenblad": "trb",
}
_OFFICIAL_TITLE = {"stb": "Staatsblad", "stcrt": "Staatscourant", "trb": "Tractatenblad"}


def official_publication_hits(text: str) -> List[AuthorityHit]:
    hits = []
    for m in OFFICIAL_RE.finditer(text):
        code = _OFFICIAL_CODE[m.group("pub").lower()]
        year, nr = m.group("year"), str(int(m.group("nr")))
        if int(nr) == 0:
            continue
        identifier = f"{code}-{year}-{nr}"
        doc = AuthorityDoc(
            kind="nl_official_publication",
            identifier_scheme="officielebekendmakingen",
            identifier=identifier,
            title=f"{_OFFICIAL_TITLE[code]} {year}, {nr}",
            url=OB_URL.format(identifier),
        )
        hits.append(AuthorityHit(doc, m.start(), m.end(), None, "nl_official_publication", 0.95))
    return hits


# ---------------------------------------------------------------------------
# R4.2 policy rules
# ---------------------------------------------------------------------------

_VC = r"(?:Vc|Vreemdelingencirculaire)" + _SP + r"*2000"
_VC_PARA = r"(?P<para{n}>[ABC]\d{{1,2}}(?:/\d{{1,2}}(?:\.\d{{1,2}}){{0,3}})?)(?![\w/])"
VC_AFTER_RE = re.compile(
    r"(?<![\w.])" + _VC + r"(?:" + _SP + r"*\((?P<part>[ABC])\))?"
    r"(?:"
    + _SP
    + r"*,?"
    + _SP
    + r"*(?:(?:paragraaf|par\.|§)"
    + _SP
    + r"*)?"
    + _VC_PARA.format(n=1)
    + r")?"  # noqa: E501
)
VC_BEFORE_RE = re.compile(
    r"(?<![\w/.])(?:(?:paragraaf|par\.|§)"
    + _SP
    + r"*)?"
    + _VC_PARA.format(n=2)
    + _SP
    + r"*(?:,|van"
    + _SP
    + r"+de)?"
    + _SP
    + r"*"
    + _VC
    + r"(?:"
    + _SP
    + r"*\((?P<part>[ABC])\))?"
)
WBV_RE = re.compile(
    r"(?<![\w.])WBV"
    + _SP
    + r"+(?P<year>(?:19|20)\d{2})"
    + _SP
    + r"*/"
    + _SP
    + r"*(?P<nr>\d{1,3})(?![\d/])"
)  # noqa: E501
BESLUIT_RE = re.compile(
    r"(?<![\w.])[Bb]esluit" + _SP + r"+van" + _SP + r"+"
    r"(?:de" + _SP + r"+[^,.;()\n]{3,90}?" + _SP + r"+van" + _SP + r"+)?"
    r"(?P<date>[0-3]?\d" + _SP + r"+[a-z]{3,9}" + _SP + r"+(?:19|20)\d{2})"
    r"" + _SP + r"*," + _SP + r"*(?:nr\.?|no\.?|kenmerk:?|nummer)" + _SP + r"*"
    r"(?P<ref>(?:[A-Z][A-Za-z]{1,7}"
    + _SP
    + r"?)(?:19|20)?\d{2,4}"
    + _SP
    + r"?[/-]"
    + _SP
    + r"?\d{1,7}[A-Z]{0,2}"  # noqa: E501
    r"|(?:19|20)\d{2}" + _SP + r"?[/-]" + _SP + r"?\d{3,7}[A-Z]{0,2})(?![\w/])"
)


def _vc_doc(part: Optional[str]) -> AuthorityDoc:
    identifier = f"vc2000-{part}" if part else "vc2000"
    title = f"Vreemdelingencirculaire 2000 ({part})" if part else "Vreemdelingencirculaire 2000"
    return AuthorityDoc(
        kind="nl_policy_rule",
        identifier_scheme="nl_vreemdelingencirculaire",
        identifier=identifier,
        title=title,
    )


def policy_rule_hits(text: str) -> List[AuthorityHit]:
    hits = []
    for regex, para_group in ((VC_BEFORE_RE, "para2"), (VC_AFTER_RE, "para1")):
        for m in regex.finditer(text):
            para = m.group(para_group)
            part = para[0] if para else m.group("part")
            hits.append(
                AuthorityHit(
                    _vc_doc(part),
                    m.start(),
                    m.end(),
                    para,
                    "nl_vreemdelingencirculaire",
                    0.95 if part else 0.9,
                )
            )
    for m in WBV_RE.finditer(text):
        identifier = f"{m.group('year')}/{int(m.group('nr'))}"
        doc = AuthorityDoc(
            kind="nl_policy_rule",
            identifier_scheme="nl_wbv",
            identifier=identifier,
            title=f"WBV {identifier}",
        )
        hits.append(AuthorityHit(doc, m.start(), m.end(), None, "nl_wbv", 0.9))
    for m in BESLUIT_RE.finditer(text):
        dm = DATE_RE.match(m.group("date") + " ")
        decided = parse_date_match(dm) if dm else None
        if decided is None:
            continue
        ref = re.sub(r"\s+", "", m.group("ref")).upper()
        doc = AuthorityDoc(
            kind="nl_policy_rule",
            identifier_scheme="nl_besluit_kenmerk",
            identifier=ref,
            title=f"Besluit nr. {ref}",
            date=decided.isoformat(),
        )
        hits.append(AuthorityHit(doc, m.start(), m.end(), None, "nl_besluit_kenmerk", 0.8))
    return hits


# ---------------------------------------------------------------------------
# R4.4 foreign ECLIs
# ---------------------------------------------------------------------------

FOREIGN_ECLI_COUNTRIES = frozenset(
    "AT BE BG CY CZ DE DK EE EL ES FI FR HR HU IE IT LT LU LV MT PL PT RO SE SI SK "
    "IS LI NO CH UK".split()
)
ECLI_RE = re.compile(
    r"(?<![\w:])ECLI" + _SP + r"?:" + _SP + r"?(?P<cc>[A-Z]{2}):(?P<court>[A-Z0-9][A-Z0-9.]{0,6}):"
    r"(?P<year>(?:19|20)\d{2}):(?P<ord>[A-Za-z0-9.]{1,25})"
)


def foreign_ecli_hits(text: str) -> List[AuthorityHit]:
    hits = []
    for m in ECLI_RE.finditer(text):
        cc = m.group("cc")
        if cc not in FOREIGN_ECLI_COUNTRIES:
            continue
        ordinal = m.group("ord").rstrip(".")
        if not ordinal:
            continue
        end = m.start("ord") + len(ordinal)
        court = m.group("court").rstrip(".")
        ecli = f"ECLI:{cc}:{court}:{m.group('year')}:{ordinal.upper()}"
        doc = AuthorityDoc(
            kind="national_court_decision",
            identifier_scheme="ecli",
            identifier=ecli,
            issuer=f"{cc}:{court}",
        )
        hits.append(AuthorityHit(doc, m.start(), end, None, "ecli", 0.95))
    return hits


# ---------------------------------------------------------------------------
# R4.5 UN treaty bodies and Council of Europe bodies
# ---------------------------------------------------------------------------

UN_BODIES = {
    "CCPR": "Human Rights Committee",
    "CAT": "Committee against Torture",
    "CRC": "Committee on the Rights of the Child",
    "CEDAW": "Committee on the Elimination of Discrimination against Women",
    "CERD": "Committee on the Elimination of Racial Discrimination",
    "CRPD": "Committee on the Rights of Persons with Disabilities",
    "CMW": "Committee on Migrant Workers",
    "CED": "Committee on Enforced Disappearances",
    "E/C.12": "Committee on Economic, Social and Cultural Rights",
}
UN_SYMBOL_RE = re.compile(
    r"(?<![\w/])(?P<sym>(?P<body>CCPR|CAT|CRC|CEDAW|CERD|CRPD|CMW|CED|E/C\.12)"
    r"(?:/[A-Z0-9][A-Za-z0-9]*(?:[.\-][A-Za-z0-9]+)*){2,8})(?![\w/])"
)
# Committee named near a communication number; Dutch and French names too.
_COMMITTEE_CUES = (
    (
        r"Human Rights Committee|Mensenrechtencomit[ée]|Comit[ée] des droits de l.homme|\bHRC\b",
        "CCPR",
    ),
    (
        r"Committee against Torture|Comit[ée] tegen (?:Foltering|marteling)"
        r"|Comit[ée] contre la torture|\bCAT\b",
        "CAT",
    ),
    (
        r"Committee on the Rights of the Child|Kinderrechtencomit[ée]"
        r"|Comit[ée] des droits de l.enfant",
        "CRC",
    ),
    (r"\bCEDAW\b|Committee on the Elimination of Discrimination against Women", "CEDAW"),
    (r"\bCERD\b|Committee on the Elimination of Racial Discrimination", "CERD"),
    (r"\bCRPD\b|Committee on the Rights of Persons with Disabilities", "CRPD"),
)
_COMMITTEE_CUES = tuple((re.compile(cue, re.I), code) for cue, code in _COMMITTEE_CUES)

COMMUNICATION_RE = re.compile(
    r"(?<![\w.])(?:[Cc]ommunication|[Cc]ommunicatie|[Cc]lacht)" + _SP + r"+"
    r"(?:No\.?|no\.?|nr\.?|n°|number)" + _SP + r"*(?P<n>\d{1,4}/(?:19|20)\d{2})(?![\d/])"
)

CDL_RE = re.compile(
    r"(?<![\w-])CDL-(?P<t>AD|PI|REF|INF|EL|LA|AS|UDT|JD|DEM|STD|JU)" + _SP + r"?\("
    r"(?P<y>(?:19|20)\d{2})\)" + _SP + r"?(?P<n>\d{1,3})(?P<s>[a-z]{0,3})(?![\w])"
)
CPT_RE = re.compile(
    r"(?<![\w/])CPT/Inf"
    + _SP
    + r"?\("
    + _SP
    + r"?(?P<y>(?:19|20)\d{2})"
    + _SP
    + r"?\)"
    + _SP
    + r"?(?P<n>\d{1,3})(?![\d])"  # noqa: E501
)
GRECO_RE = re.compile(
    r"(?<![\w])Greco"
    + _SP
    + r"?(?P<t>Eval"
    + _SP
    + r"?(?:[IVX]{1,4}|\d)"
    + _SP
    + r"?Rep|RC"
    + _SP
    + r"?(?:[IVX]{1,4}|\d))"  # noqa: E501
    r"" + _SP + r"?\((?P<y>(?:19|20)\d{2})\)" + _SP + r"?(?P<n>\d{1,3})(?P<s>[EF])?(?![\w])",
    re.I,
)
ECRI_RE = re.compile(
    r"(?<![\w/])CRI" + _SP + r"?\((?P<y>(?:19|20)\d{2})\)" + _SP + r"?(?P<n>\d{1,3})(?![\d])"
)  # noqa: E501
ECRI_GPR_RE = re.compile(
    r"(?<![\w])ECRI(?:['’]s)?" + _SP + r"+General" + _SP + r"+Policy" + _SP + r"+Recommendation"
    r"" + _SP + r"+(?:No\.?|no\.?|n°|nr\.?)" + _SP + r"*(?P<n>\d{1,2})(?!\d)"
)
CM_RE = re.compile(
    r"(?<![\w/])(?P<t>CM/Rec|CM/ResDH|CM/ResCMN|CM/ResChS|CM/Res|CM/Del/Dec|Rec|Res)"
    r"" + _SP + r"?\((?P<y>(?:19|20)\d{2})\)" + _SP + r"?(?P<n>\d{1,4})(?![\d])"
)
_CM_BARE_CUE = re.compile(
    r"(?:Recommendation|Resolution|Aanbeveling|Resolutie|Recommandation|Résolution|Committee of Ministers|Comité des Ministres|Comité van Ministers)\W{0,20}$",  # noqa: E501
    re.I,
)
COMMDH_RE = re.compile(
    r"(?<![\w])CommDH(?P<t>/Rec|/IssuePaper|/PositionPaper)?"
    + _SP
    + r"?\((?P<y>(?:19|20)\d{2})\)"
    + _SP
    + r"?(?P<n>\d{1,3})(?![\d])"  # noqa: E501
)


def _sentence_around(text: str, start: int, end: int, before=250, after=120) -> str:
    left = text[max(0, start - before) : start]
    cut = max(left.rfind(". "), left.rfind("\n"))
    if cut >= 0:
        left = left[cut + 1 :]
    right = text[end : end + after]
    stop = min([i for i in (right.find(". "), right.find("\n")) if i >= 0] or [len(right)])
    return left + " " + right[:stop]


def un_hits(text: str) -> List[AuthorityHit]:
    hits = []
    for m in UN_SYMBOL_RE.finditer(text):
        symbol = m.group("sym").rstrip(".-")
        end = m.start("sym") + len(symbol)
        body = m.group("body")
        doc = AuthorityDoc(
            kind="un_treaty_body",
            identifier_scheme="un_symbol",
            identifier=symbol,
            issuer=UN_BODIES[body],
            url=UNDOCS_URL.format(symbol),
        )
        hits.append(AuthorityHit(doc, m.start(), end, None, "un_symbol", 0.95))
    for m in COMMUNICATION_RE.finditer(text):
        around = _sentence_around(text, m.start(), m.end())
        bodies = {code for cue, code in _COMMITTEE_CUES if cue.search(around)}
        if len(bodies) != 1:
            continue  # no committee named, or several: not ours to guess
        body = bodies.pop()
        identifier = f"{body}/{m.group('n')}"
        doc = AuthorityDoc(
            kind="un_treaty_body",
            identifier_scheme="un_communication",
            identifier=identifier,
            title=f"Communication No. {m.group('n')}",
            issuer=UN_BODIES[body],
        )
        hits.append(AuthorityHit(doc, m.start(), m.end(), None, "un_communication", 0.85))
    return hits


def coe_hits(text: str) -> List[AuthorityHit]:
    hits = []

    def add(m, scheme, identifier, issuer, method, confidence=0.95):
        doc = AuthorityDoc(
            kind="coe_body", identifier_scheme=scheme, identifier=identifier, issuer=issuer
        )
        hits.append(AuthorityHit(doc, m.start(), m.end(), None, method, confidence))

    for m in CDL_RE.finditer(text):
        identifier = f"CDL-{m.group('t')}({m.group('y')}){int(m.group('n')):03d}{m.group('s')}"
        add(m, "coe_cdl", identifier, "Venice Commission", "coe_cdl")
    for m in CPT_RE.finditer(text):
        add(m, "coe_cpt", f"CPT/Inf({m.group('y')}){int(m.group('n'))}", "CPT", "coe_cpt")
    for m in GRECO_RE.finditer(text):
        kind = re.sub(r"\s+", "", m.group("t"))
        kind = re.sub(r"(?i)^eval", "Eval", kind)
        kind = re.sub(r"(?i)rep$", "Rep", kind)
        kind = re.sub(r"(?i)^rc", "RC", kind)
        identifier = f"Greco{kind}({m.group('y')}){int(m.group('n'))}"
        add(m, "coe_greco", identifier, "GRECO", "coe_greco")
    for m in ECRI_RE.finditer(text):
        add(m, "coe_ecri", f"CRI({m.group('y')}){int(m.group('n'))}", "ECRI", "coe_ecri")
    for m in ECRI_GPR_RE.finditer(text):
        add(m, "coe_ecri_gpr", str(int(m.group("n"))), "ECRI", "coe_ecri_gpr")
    for m in CM_RE.finditer(text):
        kind = m.group("t")
        if kind in ("Rec", "Res") and not _CM_BARE_CUE.search(
            text[max(0, m.start() - 60) : m.start()]
        ):
            continue
        identifier = f"{kind}({m.group('y')}){int(m.group('n'))}"
        add(m, "coe_cm", identifier, "Committee of Ministers", "coe_cm")
    for m in COMMDH_RE.finditer(text):
        identifier = f"CommDH{m.group('t') or ''}({m.group('y')}){int(m.group('n'))}"
        add(m, "coe_commdh", identifier, "Commissioner for Human Rights", "coe_commdh")
    return hits


# ---------------------------------------------------------------------------
# everything
# ---------------------------------------------------------------------------

GROUPS = ("nl_parliamentary", "nl_official", "nl_policy", "foreign_ecli", "un", "coe")
_SCANNERS = {
    "nl_parliamentary": (kamerstuk_hits, handelingen_hits),
    "nl_official": (official_publication_hits,),
    "nl_policy": (policy_rule_hits,),
    "foreign_ecli": (foreign_ecli_hits,),
    "un": (un_hits,),
    "coe": (coe_hits,),
}


def scan(text: str, groups: Sequence[str] = GROUPS) -> List[AuthorityHit]:
    """Every reference in text, in order; of overlapping hits the longest
    (then the earliest) is kept, so "paragraaf C2/3.2 Vc 2000 (C)" is one
    reference and a Staatscourant number inside a besluit citation another
    only where they do not overlap."""
    if not text:
        return []
    found = []
    for group in groups:
        for scanner in _SCANNERS[group]:
            found.extend(scanner(text))
    found.sort(key=lambda h: (h.start, -(h.end - h.start)))
    kept: List[AuthorityHit] = []
    for hit in sorted(found, key=lambda h: (-(h.end - h.start), h.start)):
        if any(hit.start < k.end and k.start < hit.end for k in kept):
            continue
        kept.append(hit)
    return sorted(kept, key=lambda h: (h.start, h.end))


def parse_iso(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None
