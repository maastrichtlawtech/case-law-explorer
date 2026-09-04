from datetime import date

from data_transformation.utils import (
    format_cellar_celex,
    format_echr_date,
    format_jurisdiction,
    format_rs_newline_list,
)


def test_format_jurisdiction_accepts_lowercase_dcterms_language_code():
    assert format_jurisdiction("nl") == "NL"


def test_format_jurisdiction_accepts_existing_uppercase_and_dutch_name():
    assert format_jurisdiction("NL") == "NL"
    assert format_jurisdiction("Nederland") == "NL"


def test_format_rs_newline_list_joins_and_dedupes():
    text = "ECLI:NL:HR:2020:1\nECLI:NL:HR:2020:2\nECLI:NL:HR:2020:1"
    assert format_rs_newline_list(text) == "ECLI:NL:HR:2020:1; ECLI:NL:HR:2020:2"


def test_format_rs_newline_list_strips_blank_lines_and_whitespace():
    text = "\n  ECLI:NL:HR:2020:1  \n\n ECLI:NL:HR:2020:2\n"
    assert format_rs_newline_list(text) == "ECLI:NL:HR:2020:1; ECLI:NL:HR:2020:2"


def test_format_rs_newline_list_single_value_no_trailing_separator():
    assert format_rs_newline_list("ECLI:NL:HR:2020:1") == "ECLI:NL:HR:2020:1"


def test_format_rs_newline_list_returns_none_for_empty_input():
    assert format_rs_newline_list("") is None
    assert format_rs_newline_list("\n\n  \n") is None


def test_format_echr_date_uses_documented_day_month_year_order():
    assert format_echr_date("09-07-2026") == date(2026, 7, 9)


def test_format_cellar_celex_canonicalizes_suffix_only_documents():
    assert (
        format_cellar_celex("62025TJ0204_RES;62025TJ0204_EXT")
        == "62025TJ0204"
    )


def test_format_cellar_celex_prefers_non_information_document():
    assert (
        format_cellar_celex("62025TJ0267_INF;62025TJ0267") == "62025TJ0267"
    )
