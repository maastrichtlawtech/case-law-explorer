"""Unit tests for data_extraction.linking.cjeu_treaty."""

from __future__ import annotations

from data_extraction.linking import cjeu_treaty


def test_scan_echr_multilingual_articles_and_subdivisions():
    en = (
        "The Charter mirrors the right referred to in Article 6(1) of the ECHR "
        "and Articles 7 and 8 of the ECHR. See also Article 3 of the ECHR_ which "
        "prohibits torture."
    )
    hits_en = cjeu_treaty.scan(en, "en")
    assert {(h.scheme, h.identifier, h.raw_subdivision) for h in hits_en} == {
        ("coe_treaty", "005", "6(1)"),
        ("coe_treaty", "005", "7"),
        ("coe_treaty", "005", "8"),
        ("coe_treaty", "005", "3"),
    }

    fr = "Une violation de l’article 8 de la CEDH et des articles 6 et 13 de la CEDH."
    hits_fr = cjeu_treaty.scan(fr, "fr")
    assert {(h.identifier, h.raw_subdivision) for h in hits_fr} == {
        ("005", "8"),
        ("005", "6"),
        ("005", "13"),
    }

    de = "Gemäß Artikel 6 Abs. 1 EMRK und Art. 8 der EMRK."
    hits_de = cjeu_treaty.scan(de, "de")
    assert {(h.identifier, h.raw_subdivision) for h in hits_de} == {
        ("005", "6(1)"),
        ("005", "8"),
    }

    nl = "In strijd met artikel 6_ lid 1_ van het EVRM en art. 8 EVRM."
    hits_nl = cjeu_treaty.scan(nl, "nl")
    assert {(h.identifier, h.raw_subdivision) for h in hits_nl} == {
        ("005", "6(1)"),
        ("005", "8"),
    }

    es = "Tomando en consideración el artículo 3 del CEDH."
    assert {(h.identifier, h.raw_subdivision) for h in cjeu_treaty.scan(es, "es")} == {("005", "3")}

    it = "Ai sensi dell'articolo 6 della CEDU."
    assert {(h.identifier, h.raw_subdivision) for h in cjeu_treaty.scan(it, "it")} == {("005", "6")}


def test_scan_rejects_ecthr_reporter_and_ecli_false_positives():
    reporter_only = (
        "See ECtHR_ Waite and Kennedy v. Germany [GC]_ no. 26083/94_ ECHR 1999-I_ "
        "Rotaru v. Romania_ CEDH 2000-V_ EMRK 1999-I_ and judgment of 7 December 2017 "
        "Atanasov v. Bulgaria (CE:ECHR:2017:1207JUD000604608)."
    )
    assert cjeu_treaty.scan(reporter_only, "en") == []


def test_scan_echr_protocols_and_rejects_eu_treaty_protocols():
    text = (
        "Under Article 1 of Protocol No 1 to the ECHR and Article 4 of Protocol No 7 "
        "to the ECHR (ne bis in idem), as well as Article 1 of Protocol No 7 to the TFEU."
    )
    hits = cjeu_treaty.scan(text, "en")
    assert {(h.scheme, h.identifier, h.raw_subdivision) for h in hits} == {
        ("coe_treaty", "009", "1"),
        ("coe_treaty", "117", "4"),
    }


def test_scan_whole_treaty_echr_when_no_article_cited():
    opinion_2_13 = (
        "The agreement envisaged contains a series of amendments of the ECHR "
        "that are to make accession operational within the system established by the ECHR."
    )
    hits = cjeu_treaty.scan(opinion_2_13, "en")
    assert len(hits) == 1
    assert (hits[0].scheme, hits[0].identifier, hits[0].raw_subdivision, hits[0].match_method) == (
        "coe_treaty",
        "005",
        None,
        "treaty_name",
    )


def test_scan_un_treaties_and_rejects_unrelated_geneva_treaties():
    unrelated = (
        "In 1958 the working party adopted the Geneva Protocol on standardisation of fresh fruit. "
        "The WIPO Copyright Treaty signed in Geneva on 20 December 1996."
    )
    hits = cjeu_treaty.scan(unrelated, "en")
    keys = {(h.scheme, h.identifier) for h in hits}
    assert ("un_treaty", "V-2") not in keys
    assert ("intl_treaty", "wipo-wct1996") in keys

    asylum_and_rights = (
        "Article 1A(2) of the Geneva Convention of 28 July 1951 relating to the Status of Refugees, "
        "Article 14(1) of the ICCPR, Article 3(1) of the Convention on the Rights of the Child, "
        "and Article 5 of the UNCRPD."
    )
    hits = cjeu_treaty.scan(asylum_and_rights, "en")
    assert {(h.scheme, h.identifier, h.raw_subdivision) for h in hits} == {
        ("un_treaty", "V-2", "1A(2)"),
        ("un_treaty", "IV-4", "14(1)"),
        ("un_treaty", "IV-11", "3(1)"),
        ("un_treaty", "IV-15", "5"),
    }


def test_records_for_case_deduplicates_across_languages_and_drops_whole_fallback(tmp_path):
    recs = cjeu_treaty.records_for_case(
        "ECLI:EU:C:2014:238",
        "62012CJ0293",
        [
            ("en", "Under the ECHR, Article 8 of the ECHR applies."),
            ("fr", "Conformément à l'article 8 de la CEDH."),
            ("de", "Nach der EMRK."),
        ],
    )
    assert len(recs) == 1
    assert recs[0].scheme == "coe_treaty"
    assert recs[0].identifier == "005"
    assert recs[0].article == "8"
    assert recs[0].raw_subdivision == "8"

    path = str(tmp_path / "cjeu_text_treaty.jsonl")
    assert cjeu_treaty.write_jsonl(path, recs) == 1
    reloaded = cjeu_treaty.read_jsonl(path)
    assert reloaded == recs
