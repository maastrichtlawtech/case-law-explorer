"""Compliance guardrail tests for judicial metadata extraction and loading.

Enforces:
  1. Hard apex/international court allowlist (ECLI:NL:HR, ECLI:NL:PHR, ECLI:CE:ECHR, ECLI:EU).
     Rejects lower Dutch courts (RBAMS, RBDHA, GHAMS, ...) and French national courts (ECLI:FR:*).
  2. Art. 5(1)(d) accuracy: OCR-broken Dutch initial normalization, co-rapporteur preservation,
     and concatenated CJEU Advocate General splitting/deduplication.
  3. Durable GDPR Art. 16/17/21 person_governance_override enforcement in both judges.load_records
     and cjeu_loader.write.
  4. Static architectural guardrail: judge extraction/loading modules never join case_judge or
     cjeu_ag_opinion with case_outcome, case_status, or echr_document_article.
"""

from pathlib import Path

from data_extraction.case_context import judges
from data_loading import cjeu_loader
from data_loading.cjeu_mapping import clean_ag_name, map_row
from data_loading.clients import postgres as postgres_module
from data_loading.clients.postgres import PostgresCLEClient

from .fakes import FakeHook


def test_court_allowlist_blocks_lower_dutch_and_french_courts():
    assert judges.is_allowed_judge_ecli("ECLI:NL:HR:2024:100") is True
    assert judges.is_allowed_judge_ecli("ECLI:NL:PHR:2024:200") is True
    assert judges.is_allowed_judge_ecli("ECLI:CE:ECHR:2024:0101JUD000012320") is True
    assert judges.is_allowed_judge_ecli("ECLI:EU:C:2024:50") is True

    # Lower Dutch courts MUST be rejected (GDPR Art. 5(1)(c) minimization / personal safety).
    for disallowed in (
        "ECLI:NL:RBAMS:2025:1234",
        "ECLI:NL:RBDHA:2025:5678",
        "ECLI:NL:RBMNE:2024:999",
        "ECLI:NL:GHAMS:2025:11",
        "ECLI:NL:CRVB:2025:22",
        "ECLI:NL:RVS:2025:33",
        # French national courts MUST be rejected (France Art. 33 Loi n° 2019-222).
        "ECLI:FR:CCASS:2025:CR00123",
        "ECLI:FR:CECHR:2025:456789",
        "",
        None,
    ):
        assert judges.is_allowed_judge_ecli(disallowed) is False

    panel_text = (
        "Aldus gewezen door mrs. A.B. Jansen, voorzitter, C.D. de Vries en "
        "E.F. Bakker, rechters, in tegenwoordigheid van mr. G.H. Griffier, griffier."
    )
    assert judges.extract_rs_judges(panel_text, "ECLI:NL:RBAMS:2025:1234") == []
    assert judges.extract_rs_judges(panel_text, "ECLI:NL:GHAMS:2025:11") == []
    assert judges.extract_rs_judges(panel_text, "ECLI:FR:CCASS:2025:CR00123") == []
    assert len(judges.extract_rs_judges(panel_text, "ECLI:NL:HR:2025:100")) == 3

    echr_text = (
        "The European Court of Human Rights, sitting as a Chamber composed of:\n"
        "Robert Spano, President, Marko Bošnjak, Judges, and Hasan Bakırcı, Section Registrar"
    )
    assert judges.extract_echr_judges(echr_text, "ECLI:FR:CCASS:2025:CR00123") == []
    assert len(judges.extract_echr_judges(echr_text, "ECLI:CE:ECHR:2024:0101JUD000012320")) == 2


def test_extract_pending_sql_restricts_rs_to_hr_and_phr_only():
    src = Path(judges.__file__).read_text(encoding="utf-8")
    assert "LIKE 'ECLI:NL:%%'" not in src
    assert "ECLI:NL:HR:%%" in src
    assert "ECLI:NL:PHR:%%" in src


def test_dutch_ocr_initial_normalization():
    cases = [
        ("D.J. M .W. Paridaens", "D.J.M.W. Paridaens"),
        ("T .N.B. M . Spronken", "T.N.B.M. Spronken"),
        ("B .F. Keulen", "B.F. Keulen"),
        ("D. J. C. Aben", "D.J.C. Aben"),
        ("W. L. Valk", "W.L. Valk"),
        ("P.H.P.H.M.C van Kempen", "P.H.P.H.M.C. van Kempen"),
        ("M.E. VAN HILTEN", "M.E. van Hilten"),
    ]
    for raw, expected in cases:
        assert judges._clean_dutch_name(raw) == expected


def test_co_rapporteurs_preserved_and_concatenated_ags_cleaned():
    m = map_row(
        {
            "ecli": "ECLI:EU:T:2026:582",
            "celex": "62024TJ0582",
            "judge_rapporteur": "da Silva Passos;van der Woude",
            "date_publication": "2026-06-10",
        }
    )
    assert m.judges == {
        ("da Silva Passos", "rapporteur"),
        ("van der Woude", "rapporteur"),
    }

    assert clean_ag_name("SzpunarSzpunar") == "Szpunar"
    assert clean_ag_name("La PergolaLa Pergola") == "La Pergola"
    assert clean_ag_name("Campos Sánchez-BordonaCampos Sánchez-Bordona") == "Campos Sánchez-Bordona"
    assert clean_ag_name("BotLéger") == "Bot / Léger"
    assert clean_ag_name("SharpstonJacobs") == "Sharpston / Jacobs"
    assert clean_ag_name("Stix-HacklTizzano") == "Stix-Hackl / Tizzano"
    assert clean_ag_name("Capeta") == "Ćapeta"
    # Genuine Mc/Mac/De/Van surnames must NEVER be split.
    assert clean_ag_name("McMahon") == "McMahon"
    assert clean_ag_name("MacCormick") == "MacCormick"
    assert clean_ag_name("O'Higgins") == "O'Higgins"


def test_load_records_enforces_court_guard_and_governance_overrides():
    class FakeCursor:
        def __init__(self):
            self.executed = []
            self.rowcount = 1
            self._next_fetch = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self.executed.append((sql, params))
            if "to_regclass" in sql:
                self._next_fetch = ("cle_v2.person_governance_override",)
            elif "FROM cle_v2.person_governance_override" in sql:
                self._next_fetch = [
                    ("a.b. jansen", "judge", "RS", "suppress", None),
                    ("c.d. de vries", "judge", "RS", "rename", "C.D. de Vries-Koster"),
                ]
            else:
                self._next_fetch = []

        def fetchone(self):
            return self._next_fetch

        def fetchall(self):
            return self._next_fetch

    class FakeConn:
        def __init__(self):
            self.cur = FakeCursor()
            self.commits = 0

        def cursor(self):
            return self.cur

        def commit(self):
            self.commits += 1

    conn = FakeConn()
    recs = [
        judges.JudgeRecord("ECLI:NL:RBAMS:2025:1", "X.Y. Lower", "judge", "rs_text_judge"),
        judges.JudgeRecord("ECLI:NL:HR:2025:1", "A.B. Jansen", "judge", "rs_text_judge"),
        judges.JudgeRecord("ECLI:NL:HR:2025:1", "C.D. de Vries", "judge", "rs_text_judge"),
    ]
    stats = judges.load_records(conn, recs)
    assert stats["rejected_court"] == 1
    assert stats["suppressed"] == 1
    assert stats["renamed"] == 1
    assert conn.commits == 1
    insert_names = next(p for sql, p in conn.cur.executed if "INSERT INTO cle_v2.judge" in sql)
    assert insert_names == (["C.D. de Vries-Koster"],)


def test_cjeu_loader_respects_governance_overrides(monkeypatch):
    hook = FakeHook()
    monkeypatch.setattr(postgres_module, "PostgresHook", lambda postgres_conn_id=None: hook)
    client = PostgresCLEClient()

    def fake_fetch(sql, params=None):
        if "to_regclass" in sql:
            return [("cle_v2.person_governance_override",)]
        if "person_governance_override" in sql:
            return [
                ("smulders", "rapporteur", "CJEU", "suppress", None),
                ("capeta", "advocate_general", "CJEU", "rename", "Ćapeta"),
            ]
        return []

    monkeypatch.setattr(client, "fetch_rows", fake_fetch)
    m = map_row(
        {
            "ecli": "ECLI:EU:C:2026:99",
            "celex": "62025CC0099",
            "judge_rapporteur": "Smulders",
            "advocate_general": "Capeta",
            "date_publication": "2026-03-01",
        }
    )
    cjeu_loader.write(client, [m])
    assert m.judges == set()
    assert m.ag["ag"] == "Ćapeta"


def test_static_guardrail_no_judge_outcome_joins():
    """Architectural guardrail: judge extraction/loading never joins outcome/violation tables."""
    forbidden_targets = ("case_outcome", "case_status", "echr_document_article")
    for mod_path in (Path(judges.__file__), Path(cjeu_loader.__file__)):
        text = mod_path.read_text(encoding="utf-8").lower()
        for tbl in forbidden_targets:
            assert tbl not in text, f"{mod_path.name} must not reference {tbl}"
