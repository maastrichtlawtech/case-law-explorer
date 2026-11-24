"""
CELEX numbers of EU acts (sectors 1, 2 and 3) and the act each one names.

A CELEX number is sector, year, type letter(s) and, outside the treaties, a
number: ``32016R0679`` (sector 3, 2016, regulation 679), ``21994A1223(01)``
(sector 2, an agreement of 23 December 1994, first of that day). References
in Cellar data name parts of acts as well, and those parts are not acts of
their own:

    sector 1 (treaties)   ``12008E267`` is article 267 of the 2008 TFEU, and
                          ``12016M/PRO/01`` protocol 1 to the 2016 TEU: the act
                          is sector, year and letter (``12008E``), the rest is
                          the subdivision.
    sectors 2 and 3       the act is sector, year, letter(s), four digits and an
                          optional ``(nn)`` sequence (part of the document's
                          identity); anything after it, such as a corrigendum
                          ``R(02)`` or an article suffix, is the subdivision,
                          so a reference to a corrigendum names its act.

Normalisation: surrounding space removed, upper case, a ``CELEX:`` prefix and a
``/TXT`` suffix dropped. Anything else (sectors 0 and 4-9, C and E, malformed
values) is not parsed: ``parse_celex`` returns None and the caller counts it.

Document types are EUR-Lex's sector-3 descriptors (an unknown letter gives
``celex_3<letter>``); sector 1 is ``treaty`` (the curated fixture names the
treaty kinds), sector 2 letter A ``international_agreement``.
"""

import re
from dataclasses import dataclass
from typing import Optional

SECTORS = ("1", "2", "3")
MIN_YEAR, MAX_YEAR = 1950, 2100

_PREFIX = re.compile(r"^CELEX\s*:\s*", re.IGNORECASE)
_TREATY = re.compile(r"^1(\d{4})([A-Z])(.*)$")
_ACT = re.compile(r"^([23])(\d{4})([A-Z]{1,2})(\d{4})(\(\d{2}\))?(.*)$")

SECTOR3_TYPES = {
    "A": "opinion",
    "B": "budget",
    "C": "declaration",
    "D": "decision",
    "E": "cfsp_act",
    "F": "pjcc_act",
    "G": "resolution",
    "H": "recommendation",
    "J": "competition_non_opposition",
    "K": "ecsc_recommendation",
    "L": "directive",
    "M": "competition_non_opposition",
    "O": "ecb_guideline",
    "Q": "institutional_arrangement",
    "R": "regulation",
    "S": "ecsc_decision",
    "X": "other_act",
    "Y": "other_act",
}


@dataclass(frozen=True)
class Celex:
    value: str  # the normalised reference
    sector: str
    year: int
    type: str
    act: str  # CELEX number of the act
    subdivision: Optional[str] = None  # what follows the act, e.g. '267', 'PRO/01', 'R(02)'

    @property
    def document_type(self) -> str:
        return document_type(self.sector, self.type)


def normalize(value) -> Optional[str]:
    if value is None:
        return None
    text = _PREFIX.sub("", str(value).strip()).replace(" ", "").upper()
    if text.endswith("/TXT"):
        text = text[: -len("/TXT")]
    return text or None


def document_type(sector: str, letter: str) -> str:
    if sector == "1":
        return "treaty"
    if sector == "2":
        return "international_agreement" if letter == "A" else f"celex_2{letter}"
    return SECTOR3_TYPES.get(letter, f"celex_3{letter}")


def parse_celex(value) -> Optional[Celex]:
    """The act a CELEX reference of sectors 1-3 names, or None."""
    text = normalize(value)
    if not text:
        return None
    match = _TREATY.match(text)
    if match:
        year, letter, rest = match.groups()
        sector, act = "1", f"1{year}{letter}"
        rest = rest.lstrip("/") or None
    else:
        match = _ACT.match(text)
        if not match:
            return None
        sector, year, letter, number, sequence, rest = match.groups()
        act = f"{sector}{year}{letter}{number}{sequence or ''}"
        rest = rest or None
    if not MIN_YEAR <= int(year) <= MAX_YEAR:
        return None
    return Celex(text, sector, int(year), letter, act, rest)


def sector(value) -> Optional[str]:
    """First character of the normalised value (the CELEX sector), or None."""
    text = normalize(value)
    return text[0] if text else None
