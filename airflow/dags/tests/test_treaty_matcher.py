"""Unit tests for the declarative 200+ multilingual international treaty matcher."""

from __future__ import annotations

from data_extraction.linking import cjeu_treaty, echr_treaty, treaty_matcher


def test_catalog_loads_with_broad_coverage_and_no_duplicate_keys():
    entries = treaty_matcher.load_catalog()
    assert len(entries) >= 200
    keys = [e.key for e in entries]
    assert len(keys) == len(set(keys))
    schemes = {e.scheme for e in entries}
    assert {"coe_treaty", "un_treaty", "intl_treaty", "celex"} <= schemes


def test_matcher_extracts_multilingual_articles_and_names_across_domains():
    text = (
        "Under Article 31(1) of the Vienna Convention on the Law of Treaties (VCLT), "
        "Article 12 of the Hague Convention on the Civil Aspects of International Child Abduction, "
        "Article 9(3) of the Aarhus Convention, "
        "Article 17(1) of the Montreal Convention for air carriage, "
        "Article 27(1) of the TRIPS Agreement, "
        "Article 5 of the Berne Convention for the Protection of Literary and Artistic Works, "
        "Article 3 of the ILO Convention No. 87, "
        "Article 6 of the Istanbul Convention, "
        "and l'article 35 de la CISG."
    )
    hits = treaty_matcher.scan(text)
    got = {(h.scheme, h.identifier, h.raw_subdivision) for h in hits}
    assert ("un_treaty", "XXIII-1", "31(1)") in got
    assert ("intl_treaty", "hcch-28", "12") in got
    assert ("un_treaty", "XXVII-13", "9(3)") in got
    assert ("intl_treaty", "icao-montreal1999", "17(1)") in got
    assert ("intl_treaty", "wto-trips1994", "27(1)") in got
    assert ("intl_treaty", "wipo-berne1886", "5") in got
    assert ("intl_treaty", "ilo-c087", "3") in got
    assert ("coe_treaty", "210", "6") in got
    assert ("un_treaty", "X-10", "35") in got


def test_matcher_disambiguation_prevents_false_positives():
    # Revised European Social Charter should match 163, NOT 035.
    text = "Under Article 24 of the Revised European Social Charter (1996)."
    hits = treaty_matcher.scan(text)
    ids = {(h.scheme, h.identifier) for h in hits}
    assert ("coe_treaty", "163") in ids
    assert ("coe_treaty", "035") not in ids

    # Lowercase 'cmr' or 'trips' or 'epc' must NOT trigger uppercase-only acronyms.
    noise = "During his trips to the pct office, the epc cat walked by cmr."
    assert treaty_matcher.scan(noise) == []

    # Bern wildlife convention must NOT match Berne copyright convention.
    wildlife = "Under Article 6 of the Bern Convention on the Conservation of European Wildlife and Natural Habitats."
    w_ids = {(h.scheme, h.identifier) for h in treaty_matcher.scan(wildlife)}
    assert ("coe_treaty", "104") in w_ids
    assert ("intl_treaty", "wipo-berne1886") not in w_ids

    # Dublin Regulation must NOT match the 1990 Dublin Convention.
    dublin_reg = "Pursuant to Article 17 of the Dublin Regulation (EU) No 604/2013."
    assert ("intl_treaty", "dublin-1990") not in {(h.scheme, h.identifier) for h in treaty_matcher.scan(dublin_reg)}


def test_cjeu_and_echr_wrappers_integrate_broad_catalog():
    doc = (
        "Under Article 6(1) of the ECHR, Article 31 of the Vienna Convention on the Law of Treaties, "
        "Article 13 of the 1980 Hague Convention on Child Abduction, and Article 8 of the Lanzarote Convention."
    )
    cjeu_hits = {(h.scheme, h.identifier, h.raw_subdivision) for h in cjeu_treaty.scan(doc, "en")}
    assert ("coe_treaty", "005", "6(1)") in cjeu_hits
    assert ("un_treaty", "XXIII-1", "31") in cjeu_hits
    assert ("intl_treaty", "hcch-28", "13") in cjeu_hits
    assert ("coe_treaty", "201", "8") in cjeu_hits

    echr_hits = {(h.scheme, h.identifier, h.raw_subdivision) for h in echr_treaty.scan(doc, "en")}
    # ECHR Convention itself is skipped by echr_treaty (handled by echr_article),
    # while non-ECHR CoE / UN / HCCH treaties ARE extracted!
    assert all(h[0:2] != ("coe_treaty", "005") for h in echr_hits)
    assert ("un_treaty", "XXIII-1", "31") in echr_hits
    assert ("intl_treaty", "hcch-28", "13") in echr_hits
    assert ("coe_treaty", "201", "8") in echr_hits


def test_berne_wildlife_vs_berne_copyright_and_curly_apostrophes():
    wildlife = (
        "La convention relative\nà la conservation de la vie sauvage et du milieu naturel de l’Europe, "
        "signée le 19 septembre 1979 à Berne (ci-après la « convention de Berne »). "
        + ("Texte intermédiaire sur les espèces protégées et les habitats naturels. " * 10)
        + "En vertu de l'article 7 de la convention de Berne."
    )
    wildlife_keys = {(h.scheme, h.identifier) for h in treaty_matcher.scan(wildlife)}
    assert ("coe_treaty", "104") in wildlife_keys
    assert ("intl_treaty", "wipo-berne1886") not in wildlife_keys

    copyright_doc = (
        "Under Art. 19 der Berner Übereinkunft zum Schutz von Werken der Literatur und Kunst, "
        "copyright protection applies automatically."
    )
    cp_hits = {(h.scheme, h.identifier, h.raw_subdivision) for h in treaty_matcher.scan(copyright_doc)}
    assert ("intl_treaty", "wipo-berne1886", "19") in cp_hits
    assert all(h[0:2] != ("coe_treaty", "104") for h in cp_hits)
