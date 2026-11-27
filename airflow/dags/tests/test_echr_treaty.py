"""Unit tests for data_extraction.linking.echr_treaty."""

from __future__ import annotations

from data_extraction.linking import echr_treaty


def test_scan_extracts_all_un_treaties_and_skips_echr_convention():
    text = (
        "Under Article 3 of the Convention (ECHR), the Court also considered "
        "Article 3 of the UN Convention against Torture (UNCAT), "
        "Article 14(1) of the ICCPR, Article 12 of the ICESCR, "
        "Article 33 of the Geneva Convention of 28 July 1951 relating to the Status of Refugees, "
        "Article 1 of the Protocol relating to the Status of Refugees, "
        "Article 3(1) of the Convention on the Rights of the Child, "
        "Article 12 of the UNCRPD, Article 2 of CEDAW, and Article 4 of ICERD."
    )
    hits = echr_treaty.scan(text, "en")
    assert {(h.scheme, h.identifier, h.raw_subdivision) for h in hits} == {
        ("un_treaty", "IV-9", "3"),
        ("un_treaty", "IV-4", "14(1)"),
        ("un_treaty", "IV-3", "12"),
        ("un_treaty", "V-2", "33"),
        ("un_treaty", "V-5", "1"),
        ("un_treaty", "IV-11", "3(1)"),
        ("un_treaty", "IV-15", "12"),
        ("un_treaty", "IV-8", "2"),
        ("un_treaty", "IV-2", "4"),
    }


def test_records_for_case_french_and_dedup():
    recs = echr_treaty.records_for_case(
        "ECLI:CE:ECHR:2022:0510JUD001234519",
        [
            ("fr", "Voir l'article 3 de la Convention contre la torture et le Pacte international relatif aux droits civils et politiques."),
            ("en", "Under the UN Convention against Torture."),
        ],
    )
    assert {(r.identifier, r.raw_subdivision, r.source_dataset) for r in recs} == {
        ("IV-9", "3", "echr_text_treaty"),
        ("IV-4", None, "echr_text_treaty"),
    }
