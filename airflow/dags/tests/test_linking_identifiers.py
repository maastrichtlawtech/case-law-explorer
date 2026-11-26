import pytest
from data_extraction.linking import identifiers as ids


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("C-221/17", "C-221/17"),
        ("C‑199/12", "C-199/12"),  # non-breaking hyphen, as in CJEU texts
        ("C–199/12", "C-199/12"),  # en dash
        ("C 199/12", "C-199/12"),  # plain space (French ECtHR texts)
        ("C - 199/12", "C-199/12"),
        ("C-04/19", "C-4/19"),
        ("c-4/19", "C-4/19"),
        ("C-221/17 P", "C-221/17"),
        ("C-89/24 PPU", "C-89/24"),
        ("T-123/04", "T-123/04"),
        ("F-12/05", "F-12/05"),
        ("26/62", "26/62"),
        ("zaak C-221/17", "C-221/17"),
        ("Case C-221/17", "C-221/17"),
    ],
)
def test_normalize_cjeu_case_number(raw, expected):
    assert ids.normalize_cjeu_case_number(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "19/02010", "201012342/1/T1/V2", "C-221", "X-1/12"])
def test_normalize_cjeu_case_number_rejects(raw):
    assert ids.normalize_cjeu_case_number(raw) is None


def test_parse_cjeu_case_number_keeps_suffix():
    assert ids.parse_cjeu_case_number("C‑221/17 P") == ("C", 221, "17", "P")
    assert ids.parse_cjeu_case_number("26/62") == ("", 26, "62", None)


def test_case_number_regex_finds_mentions_in_text():
    text = (
        "gevoegde zaken C‑199/12 tot en met C‑201/12, en arrest van "
        "12 maart 2019, Tjebbes, C-221/17, EU:C:2019:189"
    )
    found = [m.group(0) for m in ids.CJEU_CASE_NUMBER_RE.finditer(text)]
    assert [ids.normalize_cjeu_case_number(f) for f in found] == [
        "C-199/12",
        "C-201/12",
        "C-221/17",
    ]


def test_case_number_regex_ignores_longer_numbers():
    assert not list(ids.CJEU_CASE_NUMBER_RE.finditer("zaaknummer 19/02010"))
    assert not list(ids.CJEU_CASE_NUMBER_RE.finditer("201504577/1/A3"))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ECLI:EU:C:2019:189", "ECLI:EU:C:2019:189"),
        ("EU:C:2019:189", "ECLI:EU:C:2019:189"),
        ("ecli:nl:rvs:2020:423", "ECLI:NL:RVS:2020:423"),
        ("ECLI:CE:ECHR:2004:0622DEC001734103", "ECLI:CE:ECHR:2004:0622DEC001734103"),
        ("ECLI:NL:RBGEL:2026:1195", "ECLI:NL:RBGEL:2026:1195"),
    ],
)
def test_normalize_ecli(raw, expected):
    assert ids.normalize_ecli(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "ECLI:EU", "C-221/17", "EU:C:19:189"])
def test_normalize_ecli_rejects(raw):
    assert ids.normalize_ecli(raw) is None


def test_normalize_celex():
    assert ids.normalize_celex("62017CJ0221") == "62017CJ0221"
    assert ids.normalize_celex("62019CO0001(01)") == "62019CO0001"
    assert ids.normalize_celex("celex:62012cc0199") == "62012CC0199"
    assert ids.normalize_celex("C-221/17") is None


@pytest.mark.parametrize(
    "raw, expected",
    [("17341/03", "17341/03"), ("no. 017341/03", "17341/03"), ("nos. 1/99", "1/99")],
)
def test_normalize_echr_appno(raw, expected):
    assert ids.normalize_echr_appno(raw) == expected


def test_normalize_echr_appno_rejects():
    assert ids.normalize_echr_appno("C-221/17") is None
    assert ids.normalize_echr_appno("17341/2003") is None


def test_zaaknummer_variants():
    assert ids.zaaknummer_variants("201012342/1/t1/v2") == [
        "201012342/1/T1/V2",
        "201012342/T1/V2",
    ]
    assert ids.zaaknummer_variants("19/02010") == ["19/02010"]
    assert ids.zaaknummer_variants(None) == []


def test_normalize_ljn():
    assert ids.normalize_ljn("bw3076") == "BW3076"
    assert ids.normalize_ljn("BW30761") is None


def test_normalize_dispatch():
    assert ids.normalize("cjeu_case_number", "C‑199/12") == "C-199/12"
    with pytest.raises(KeyError):
        ids.normalize("unknown", "x")


# Review round 3: procedure suffixes. The strings are illustrative constructions
# from the review notes, not quoted case text.
@pytest.mark.parametrize(
    "text, expected",
    [
        ("C-123/15 SA Lorraine", ("C-123/15", None)),  # a company form, not 'SA' proceedings
        ("C-221/17 OP GROND VAN", ("C-221/17", None)),  # upper-cased prose
        ("C-221/17 R. v. Smith", ("C-221/17", None)),  # an initial, not interim relief
        ("C-204/21 R, EU:C:2021:593", ("C-204/21", "R")),
        ("C-204/21 R and C-205/21 R", ("C-204/21", "R")),
        ("C-204/21 R.", ("C-204/21", "R")),
        ("C-123/15 SA", ("C-123/15", "SA")),
        ("C-123/15 TO, EU:C:2016:1", ("C-123/15", "TO")),
    ],
)
def test_illustrative_suffix_not_taken_from_prose(text, expected):
    match = ids.CJEU_CASE_NUMBER_RE.search(text)
    assert (ids.normalize_cjeu_case_number(match.group(0)), match.group("suffix")) == expected


def test_illustrative_to_between_two_numbers_is_a_range_word():
    matches = list(ids.CJEU_CASE_NUMBER_RE.finditer("C-199/12 TO C-201/12"))
    assert [(m.group(0), m.group("suffix")) for m in matches] == [
        ("C-199/12", None),
        ("C-201/12", None),
    ]


def test_space_class_is_exported_with_no_break_and_thin_spaces():
    import re

    space = re.compile(ids.SPACE_CLASS)
    assert all(space.fullmatch(ch) for ch in (" ", " ", " ", " "))
