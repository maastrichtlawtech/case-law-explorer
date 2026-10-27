import pytest
from data_loading import case_enrichment as ce


def test_rs_court_follows_the_ecli_court_code_production_uses():
    # Airflow's instance name differs from production's court; the ECLI decides.
    assert ce.rs_court_code("ECLI:NL:RBDHA:2026:1", "Rechtbank 's-Gravenhage") == "RS:Rechtbank Den Haag"
    assert ce.rs_court_code(
        "ECLI:NL:RBDHA:2026:2", "http://standaarden.overheid.nl/owms/terms/Rechtbank_Den_HaagRBDHA"
    ) == "RS:Rechtbank Den Haag"


def test_rs_court_falls_back_to_a_plain_instance_name_only():
    assert ce.rs_court_code("ECLI:NL:XNEW:2026:1", "Nieuw College") == "RS:Nieuw College"
    assert ce.rs_court_code("ECLI:NL:XNEW:2026:1", "http://example.org/terms/NieuwXNEW") is None
    assert ce.rs_court_code("ECLI:NL:XNEW:2026:1", None) is None


def test_every_mapped_rs_court_is_an_rs_court_code():
    assert len(ce.RS_COURT_CODES) > 200
    assert all(code.startswith("RS:") for code in ce.RS_COURT_CODES.values())


@pytest.mark.parametrize(
    "doctype, kind",
    [("HEJUD", "judgment"), ("HFDEC", "decision"), ("HECOM", "communicated"),
     ("HJUDUKR", "judgment"), ("CLIN", "other"), (None, "other")],
)
def test_echr_document_type(doctype, kind):
    assert ce.echr_document_type(doctype) == kind


def test_echr_case_number_and_importance():
    assert ce.echr_case_number("10023/25;11806/25") == "10023/25"
    assert ce.echr_case_number(" ") is None
    assert ce.echr_importance("3") == 3
    assert ce.echr_importance("9") is None
    assert ce.echr_importance(None) is None


class RecordingClient:
    def __init__(self):
        self.calls = []

    def execute_arrays(self, sql, params):
        self.calls.append((sql, params))
        return 1


def test_enrich_rs_passes_eclis_and_their_courts_in_order():
    client = RecordingClient()
    ce.enrich_rs(client, [("ECLI:NL:RBDHA:2026:1", "Rechtbank 's-Gravenhage"), (None, "x"),
                          ("ECLI:NL:XNEW:2026:1", "Nieuw College")])
    courts_sql, courts_params = client.calls[1]
    assert "INSERT INTO cle_v2.court" in courts_sql
    assert courts_params == [["RS:Nieuw College", "RS:Rechtbank Den Haag"]]
    update_sql, update_params = client.calls[-1]
    assert update_sql.lstrip().startswith("UPDATE cle_v2.cases k SET")
    assert update_params == [["ECLI:NL:RBDHA:2026:1", "ECLI:NL:XNEW:2026:1"],
                             ["RS:Rechtbank Den Haag", "RS:Nieuw College"]]


def test_enrich_rs_does_nothing_without_eclis():
    client = RecordingClient()
    assert ce.enrich_rs(client, [(None, "x")]) == 0
    assert client.calls == []
