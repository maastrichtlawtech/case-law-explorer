"""Tests for preserving commas in CELLAR JSON full-text extraction."""

import sys
import types


def test_preserve_fulltext_commas_rebinds_cellar_extractor_helpers(monkeypatch):
    # Stub heavy optional imports so cellar_extraction can be imported in unit tests.
    fake_cell = types.ModuleType("cellar_extractor")
    fake_eurlex = types.ModuleType("cellar_extractor.eurlex_scraping")
    fake_saving = types.ModuleType("cellar_extractor.fulltext_saving")

    def legacy_replace(html):
        return html.replace(",", "_")

    def clean_preserve(html):
        return html

    fake_eurlex.get_full_text_from_html = legacy_replace
    fake_eurlex.get_clean_text_from_html = clean_preserve
    fake_saving.get_full_text_from_html = legacy_replace
    fake_cell.eurlex_scraping = fake_eurlex
    fake_cell.fulltext_saving = fake_saving

    fake_airflow = types.ModuleType("airflow")
    fake_airflow_models = types.ModuleType("airflow.models")
    fake_airflow_var = types.ModuleType("airflow.models.variable")
    fake_airflow_var.Variable = object

    monkeypatch.setitem(sys.modules, "cellar_extractor", fake_cell)
    monkeypatch.setitem(sys.modules, "cellar_extractor.eurlex_scraping", fake_eurlex)
    monkeypatch.setitem(sys.modules, "cellar_extractor.fulltext_saving", fake_saving)
    monkeypatch.setitem(sys.modules, "airflow", fake_airflow)
    monkeypatch.setitem(sys.modules, "airflow.models", fake_airflow_models)
    monkeypatch.setitem(sys.modules, "airflow.models.variable", fake_airflow_var)
    monkeypatch.delitem(
        sys.modules, "data_extraction.caselaw.cellar.cellar_extraction", raising=False
    )

    from data_extraction.caselaw.cellar import cellar_extraction

    assert cellar_extraction._preserve_fulltext_commas() is True
    assert fake_eurlex.get_full_text_from_html is clean_preserve
    assert fake_saving.get_full_text_from_html is clean_preserve
    assert fake_saving.get_full_text_from_html("Article 20, TFEU") == "Article 20, TFEU"
