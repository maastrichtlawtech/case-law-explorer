"""
Identifier normalisation shared by every link extractor and by case_identifier.

One function per scheme. Each returns the normalised value (the key stored in
case_identifier.value_normalized and used for lookups) or None when the input
is not an identifier of that scheme. The SQL twin used by the historical
backfill (cjeu-migration) is tested against these functions, so change both
together.

Schemes (case_identifier.scheme):
    ecli              ECLI:EU:C:2019:189
    celex             62017CJ0221
    cjeu_case_number  C-221/17 (court letter, number without leading zeros, two-digit year)
    echr_appno        17341/03
    nl_zaaknummer     201012342/1/T1/V2 (also stored without the instance segment)
    ljn               BW3076
"""

import re
import unicodedata

# Characters courts and publishers use for the hyphen in "C-221/17": hyphen,
# non-breaking hyphen (U+2011, used by the CJEU's own texts), figure dash,
# en dash, em dash, horizontal bar, minus sign and the soft hyphen.
HYPHENS = "-‐‑‒–—―−­"
_HYPHEN_CLASS = "[" + re.escape(HYPHENS) + "]"
# Spaces, including no-break and thin spaces.
_SPACE_CLASS = r"[    ]"

# Procedure suffixes after a case number ("C-221/17 P", "C-89/24 PPU").
CJEU_SUFFIXES = (
    "PPU",
    "P",
    "R",
    "RX",
    "REC",
    "DEP",
    "AJ",
    "TO",
    "INT",
    "REV",
    "OP",
    "SA",
)

# A CJEU, General Court or Civil Service Tribunal case number. The court
# letter is optional (cases before 1989 have none: "26/62"); the separator
# between letter and number may be a hyphen of any kind, a space, or both.
CJEU_CASE_NUMBER_RE = re.compile(
    r"(?<![\w/])"
    r"(?:(?P<court>[CTF])" + _SPACE_CLASS + r"?(?:" + _HYPHEN_CLASS + r")?" + _SPACE_CLASS + r"?)?"
    r"(?P<number>\d{1,4})/(?P<year>\d{2})(?![\d/])"
    r"(?:" + _SPACE_CLASS + r"(?P<suffix>" + "|".join(CJEU_SUFFIXES) + r")\b)?"
)

_ECLI_RE = re.compile(
    r"^(?:ECLI:)?(?P<country>[A-Z]{2}):(?P<court>[A-Z0-9.]{1,7}):"
    r"(?P<year>\d{4}):(?P<number>[A-Z0-9.]{1,25})$"
)
_CELEX_RE = re.compile(r"^(?P<sector>[0-9CE])(?P<year>\d{4})(?P<type>[A-Z]{1,2})(?P<number>\d{4})")
_APPNO_RE = re.compile(r"^(?P<number>\d{1,6})/(?P<year>\d{2})$")
_LJN_RE = re.compile(r"^[A-Z]{2}\d{4}$")


def _clean(value):
    """NFKC-normalise and collapse whitespace; None for empty input."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    # NFKC maps U+2011 to U+2010 but leaves the other dashes; unify them all.
    text = re.sub(_HYPHEN_CLASS, "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_ecli(value):
    """'ecli:eu:c:2019:189' or 'EU:C:2019:189' -> 'ECLI:EU:C:2019:189'."""
    text = _clean(value)
    if text is None:
        return None
    text = text.upper().replace(" ", "")
    match = _ECLI_RE.match(text)
    if not match:
        return None
    return "ECLI:{country}:{court}:{year}:{number}".format(**match.groupdict())


def normalize_celex(value):
    """'62017CJ0221' -> '62017CJ0221'; keeps a trailing '(01)'-style variant
    out of the key ('62019CO0001(01)' -> '62019CO0001') because Cellar files
    corrigenda and duplicate manifestations under it."""
    text = _clean(value)
    if text is None:
        return None
    text = text.upper().replace(" ", "")
    text = re.sub(r"^CELEX:", "", text)
    match = _CELEX_RE.match(text)
    if not match:
        return None
    return match.group(0)


def parse_cjeu_case_number(value):
    """Split a case number into (court, number, year, suffix), or None.

    'C‑221/17 P' -> ('C', 221, '17', 'P'); '26/62' -> ('', 26, '62', None).
    """
    text = _clean(value)
    if text is None:
        return None
    text = re.sub(r"^(?:case|zaak|affaire|aff\.|rechtssache|rs\.)\s+", "", text, flags=re.I)
    match = CJEU_CASE_NUMBER_RE.fullmatch(text.upper())
    if not match:
        return None
    court = match.group("court") or ""
    return court, int(match.group("number")), match.group("year"), match.group("suffix")


def normalize_cjeu_case_number(value):
    """'C‑04/19', 'C 4/19', 'c-4/19 P' -> 'C-4/19'; '26/62' -> '26/62'."""
    parts = parse_cjeu_case_number(value)
    if parts is None:
        return None
    court, number, year, _suffix = parts
    if not court:
        return f"{number}/{year}"
    return f"{court}-{number}/{year}"


def normalize_echr_appno(value):
    """'no. 017341/03' -> '17341/03'."""
    text = _clean(value)
    if text is None:
        return None
    text = re.sub(r"^(?:nos\.?|no\.?|nr\.?|n°|requête|application)\s*", "", text, flags=re.I)
    match = _APPNO_RE.match(text.replace(" ", ""))
    if not match:
        return None
    return f"{int(match.group('number'))}/{match.group('year')}"


def normalize_zaaknummer(value):
    """Dutch case numbers: collapse whitespace, upper-case letters.

    '201012342/1/t1/v2' -> '201012342/1/T1/V2'. Use zaaknummer_variants to get
    the forms with and without the Raad van State instance segment.
    """
    text = _clean(value)
    if text is None:
        return None
    return text.upper().replace(" ", "")


def zaaknummer_variants(value):
    """All forms a Dutch case number is cited in, normalised.

    The Raad van State writes '201012342/1/T1/V2' in its decisions while
    Cellar's referral data writes '201012342/T1/V2'. Returns the normalised
    value first, then the form without (or with) the '/1/' instance segment.
    """
    base = normalize_zaaknummer(value)
    if base is None:
        return []
    variants = [base]
    parts = base.split("/")
    if len(parts) >= 3 and parts[1].isdigit() and len(parts[1]) == 1:
        variants.append("/".join([parts[0]] + parts[2:]))
    return variants


def normalize_ljn(value):
    """'bw3076' -> 'BW3076'."""
    text = _clean(value)
    if text is None:
        return None
    text = text.upper().replace(" ", "")
    return text if _LJN_RE.match(text) else None


NORMALIZERS = {
    "ecli": normalize_ecli,
    "celex": normalize_celex,
    "cjeu_case_number": normalize_cjeu_case_number,
    "echr_appno": normalize_echr_appno,
    "nl_zaaknummer": normalize_zaaknummer,
    "ljn": normalize_ljn,
}


def normalize(scheme, value):
    """Normalise value under scheme; KeyError for an unknown scheme."""
    return NORMALIZERS[scheme](value)
