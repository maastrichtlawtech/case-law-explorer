"""Unit tests for Track B legislation metadata & full-text enrichment."""

import datetime as dt

from data_extraction.legislation import legislation_enrichment as mod


SAMPLE_CELLAR_TREE = b"""<?xml version="1.0" encoding="UTF-8"?>
<NOTICE>
  <WORK>
    <WORK_DATE_DOCUMENT type="date"><VALUE>2016-04-27</VALUE></WORK_DATE_DOCUMENT>
    <RESOURCE_LEGAL_IN-FORCE type="data"><VALUE>true</VALUE></RESOURCE_LEGAL_IN-FORCE>
    <RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE type="date"><VALUE>2018-05-25</VALUE></RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE>
    <RESOURCE_LEGAL_ELI type="data"><VALUE>http://data.europa.eu/eli/reg/2016/679/oj</VALUE></RESOURCE_LEGAL_ELI>
    <WORK_IS_ABOUT_CONCEPT_EUROVOC>
      <WORK_IS_ABOUT_CONCEPT_EUROVOC_CONCEPT><PREFLABEL>personal data</PREFLABEL></WORK_IS_ABOUT_CONCEPT_EUROVOC_CONCEPT>
    </WORK_IS_ABOUT_CONCEPT_EUROVOC>
    <RESOURCE_LEGAL_BASED_ON_CONCEPT_TREATY>
      <IDENTIFIER>TFEU_2012</IDENTIFIER>
      <PREFLABEL>TFEU</PREFLABEL>
    </RESOURCE_LEGAL_BASED_ON_CONCEPT_TREATY>
    <RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL>
      <SAMEAS><URI><TYPE>celex</TYPE><IDENTIFIER>32024R1689</IDENTIFIER></URI></SAMEAS>
    </RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL>
  </WORK>
  <EXPRESSION>
    <EXPRESSION_TITLE><VALUE>Regulation (EU) 2016/679 (GDPR)</VALUE></EXPRESSION_TITLE>
    <EXPRESSION_TITLE_SHORT><VALUE>gdpr, personal data</VALUE></EXPRESSION_TITLE_SHORT>
  </EXPRESSION>
</NOTICE>
"""

SAMPLE_CELLAR_XHTML = """<html><body>
<div id="art_1" class="eli-subdivision">
  <p class="oj-ti-art">Article 1</p>
  <p class="oj-sti-art">Subject-matter and objectives</p>
  <p>1. This Regulation lays down rules relating to the protection of natural persons.</p>
</div>
<div id="art_2" class="eli-subdivision">
  <p class="oj-ti-art">Article 2</p>
  <p class="oj-sti-art">Material scope</p>
  <p>This Regulation applies to the processing of personal data.</p>
</div>
</body></html>"""

SAMPLE_BWB_SRU = b"""<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns:dcterms="http://purl.org/dc/terms/" xmlns:overheidbwb="http://standaarden.overheid.nl/bwb/terms/">
  <numberOfRecords>1</numberOfRecords>
  <records><record><recordData><gzd>
    <dcterms:identifier>BWBR0005537</dcterms:identifier>
    <dcterms:title>Algemene wet bestuursrecht</dcterms:title>
    <overheidbwb:rechtsgebied>Bestuursrecht</overheidbwb:rechtsgebied>
    <overheidbwb:overheidsdomein>Overheid, bestuur en koninkrijk</overheidbwb:overheidsdomein>
    <overheidbwb:geldigheidsperiode_startdatum>2026-11-10</overheidbwb:geldigheidsperiode_startdatum>
    <overheidbwb:geldigheidsperiode_einddatum>9999-12-31</overheidbwb:geldigheidsperiode_einddatum>
    <overheidbwb:locatie_toestand>https://repository.officiele-overheidspublicaties.nl/bwb/BWBR0005537/2026-11-10_0/xml/BWBR0005537_2026-11-10_0.xml</overheidbwb:locatie_toestand>
  </gzd></recordData></record></records>
</searchRetrieveResponse>
"""

SAMPLE_BWB_TOESTAND = b"""<?xml version="1.0" encoding="UTF-8"?>
<toestand>
  <artikel label-id="2813914" label="Artikel 1:1">
    <kop><label>Artikel</label><nr>1:1</nr><titel>Bestuursorgaan</titel></kop>
    <lid><lidnr>1.</lidnr><al>Onder bestuursorgaan wordt verstaan een orgaan van een rechtspersoon.</al></lid>
  </artikel>
</toestand>
"""


def test_parse_cellar_notice_and_xhtml_articles():
    rec = mod.parse_cellar_notice_xml("32016R0679", SAMPLE_CELLAR_TREE)
    assert rec.identifier == "32016R0679"
    assert rec.title == "Regulation (EU) 2016/679 (GDPR)"
    assert rec.short_title == "gdpr, personal data"
    assert rec.date_document == "2016-04-27"
    assert rec.date_entry_into_force == "2018-05-25"
    assert rec.in_force is True
    assert rec.eli == "http://data.europa.eu/eli/reg/2016/679/oj"
    assert rec.subjects == ("personal data",)
    assert rec.legal_basis == ("TFEU",)
    assert rec.amending_acts == ("32024R1689",)

    arts = mod.parse_cellar_xhtml_articles(SAMPLE_CELLAR_XHTML)
    assert len(arts) == 2
    assert arts[0].article_label == "1"
    assert arts[0].title == "Subject-matter and objectives"
    assert "protection of natural persons" in arts[0].text
    assert arts[1].article_label == "2"


def test_parse_bwb_sru_and_toestand_xml():
    meta = mod.parse_bwb_sru_xml("BWBR0005537", SAMPLE_BWB_SRU, today=dt.date(2026, 11, 27))
    assert meta is not None
    assert meta.title == "Algemene wet bestuursrecht"
    assert meta.in_force is True
    assert meta.start_date == "2026-11-10"
    assert meta.subjects == ("Bestuursrecht", "Overheid, bestuur en koninkrijk")

    arts = mod.parse_bwb_toestand_xml(SAMPLE_BWB_TOESTAND)
    assert len(arts) == 1
    assert arts[0].article_label == "1:1"
    assert arts[0].title == "Bestuursorgaan"
    assert arts[0].bwb_label_id == 2813914
    assert "bestuursorgaan" in arts[0].text.lower()


def test_echr_convention_enrichment_and_artifact_roundtrip(tmp_path):
    rec = mod.echr_convention_enrichment()
    assert rec.scheme == "coe_treaty"
    assert rec.identifier == "005"
    assert rec.in_force is True
    labels = {a.article_label for a in rec.articles}
    assert {"2", "3", "6", "8", "10", "P1-1"}.issubset(labels)

    out = tmp_path / "legislation_enrichment.jsonl"
    assert mod.write_enrichment_artifact(str(out), [rec]) == 1
    loaded = mod.read_enrichment_artifact(str(out))
    assert len(loaded) == 1
    assert loaded[0] == rec
