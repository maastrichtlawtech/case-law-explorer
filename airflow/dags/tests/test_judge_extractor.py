"""Unit tests for cross-court NL & ECHR judge / AG extraction."""

from data_extraction.case_context import judges as mod


def test_extract_rs_judges_multi_member_panel_excludes_griffier():
    text = (
        "Dit arrest is gewezen door mrs. A.B. Jansen, voorzitter, C.D. de Vries en "
        "prof. mr. E.F. Bakker, raadsheren, in tegenwoordigheid van mr. G.H. Griffier, "
        "griffier, en in het openbaar uitgesproken op 12 maart 2024."
    )
    recs = mod.extract_rs_judges(text, "ECLI:NL:HR:2024:100")
    assert [(r.name, r.role, r.source_dataset) for r in recs] == [
        ("A.B. Jansen", "judge", "rs_text_judge"),
        ("C.D. de Vries", "judge", "rs_text_judge"),
        ("E.F. Bakker", "judge", "rs_text_judge"),
    ]


def test_extract_rs_phr_advocate_general():
    text = (
        "4. Conclusie\nDe conclusie strekt tot verwerping van het cassatieberoep.\n\n"
        "De Procureur-Generaal bij de Hoge Raad der Nederlanden,\n"
        "mr. F.F. Langemeijer\n"
        "Advocaat-Generaal\n"
    )
    recs = mod.extract_rs_judges(text, "ECLI:NL:PHR:2023:55")
    assert len(recs) == 1
    assert recs[0].name == "F.F. Langemeijer"
    assert recs[0].role == "advocate_general"
    assert recs[0].source_dataset == "rs_phr_ag"


def test_extract_echr_judges_en_and_fr_excludes_registrar():
    en_text = (
        "The European Court of Human Rights (Second Section), sitting as a Chamber composed of:\n"
        "Robert Spano, President,\n"
        "Marko Bošnjak, Julia Laffranque, Paul Lemmens, Judges,\n"
        "and Hasan Bakırcı, Section Registrar,\n"
        "Having deliberated in private..."
    )
    en_recs = mod.extract_echr_judges(en_text, "ECLI:CE:ECHR:2020:0114JUD001234517")
    assert [r.name for r in en_recs] == [
        "Robert Spano",
        "Marko Bošnjak",
        "Julia Laffranque",
        "Paul Lemmens",
    ]
    assert all(r.source_dataset == "echr_hudoc_judge" for r in en_recs)

    fr_text = (
        "La Cour européenne des droits de l'homme, siégeant en une chambre composée de :\n"
        "Síofra O'Leary, présidente,\n"
        "Gabriele Kucsko-Stadlmayer, Jolien Schukking, juges,\n"
        "et de Victor Soloveytchik, greffier de section,\n"
        "Après en avoir délibéré en chambre du conseil..."
    )
    fr_recs = mod.extract_echr_judges(fr_text, "ECLI:CE:ECHR:2022:0510JUD009999919")
    assert [r.name for r in fr_recs] == [
        "Síofra O'Leary",
        "Gabriele Kucsko-Stadlmayer",
        "Jolien Schukking",
    ]


def test_judge_artifact_roundtrip(tmp_path):
    recs = [
        mod.JudgeRecord("ECLI:NL:HR:2024:100", "A.B. Jansen", "judge", "rs_text_judge"),
        mod.JudgeRecord("ECLI:NL:PHR:2023:55", "F.F. Langemeijer", "advocate_general", "rs_phr_ag"),
    ]
    path = tmp_path / "cross_court_judges.jsonl"
    assert mod.write_artifact(str(path), recs) == 2
    assert mod.read_artifact(str(path)) == recs
