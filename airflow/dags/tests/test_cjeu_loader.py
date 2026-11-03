import pytest
from data_loading import cjeu_loader
from data_loading.clients import postgres as postgres_module
from data_loading.clients.postgres import PostgresCLEClient
from data_loading.cjeu_mapping import document_kind, extractor_row, map_row
from definitions.mappings.attribute_name_maps import MAP_CELLAR
from data_loading.cjeu_mapping import MAPPED_COLUMNS

from .fakes import FakeHook

# A real cellar-extractor 2.0.4 row (ECLI:EU:C:2026:691), as processed: the
# transformer renames only ecli -> ECLI.
ROW = {
    "ECLI": "ECLI:EU:C:2026:691",
    "celex": "62025CJ0147",
    "date_publication": "2026-09-03",
    "language_procedure": "Lithuanian",
    "judicial_procedure_type": "Reference for a preliminary ruling",
    "delivered_by_court_formation": "Fifth Chamber",
    "sector": "6",
    "type_procedure": "Reference for a preliminary ruling",
    "date_of_request": "2025-02-17",
    "judge_rapporteur": "Smulders",
    "commented_by_agent": "European Commission;Italy",
    "origin_country": "Lithuania",
    "eurovoc": "Fundamental rights;Charter of Fundamental Rights",
    "directory_codes": "DFON;PESC",
    "case_law_published_in_erecueil": "1",
    "work_part_of_dossier": "http://publications.europa.eu/resource/cellar/89bde9c9",
    "citing": "62019CJ0001;62020CJ0002",
    "legal_resource": "12016P047",
}


@pytest.fixture
def client(monkeypatch):
    hook = FakeHook()
    monkeypatch.setattr(postgres_module, "PostgresHook", lambda postgres_conn_id=None: hook)
    return PostgresCLEClient()


def test_map_row_produces_the_migration_rows():
    m = map_row(extractor_row(ROW))

    assert m.case == {
        "ecli": "ECLI:EU:C:2026:691",
        "celex": "62025CJ0147",
        "title": "Case C-147/25",
        "date_decision": "2026-09-03",
        "court_code": "CJEU",
        "lang": "lt",
        "doctype": "judgment",
        "proc": "Reference for a preliminary ruling",
        "case_number": "C-147/25",
        "importance": 2,
    }
    assert m.document["formation_code"] == "5C"
    assert m.document["date_lodged"] == "2025-02-17"
    assert m.document["erecueil_ref"] == "1"
    assert m.judges == {("Smulders", "rapporteur")}
    assert m.parties == {
        ("European Commission", "agent", "commenting_agent"),
        ("Italy", "agent", "commenting_agent"),
        ("Lithuania", "agent", "referring_state"),
    }
    assert ("eurovoc", "Fundamental rights") in m.domains
    assert ("cjeu_directory_code", "PESC") in m.domains
    assert m.citations == {("62019CJ0001", "cites"), ("62020CJ0002", "cites")}
    assert m.lawrefs == {("12016P047", "legal_basis")}
    assert m.ag is None


def test_map_row_records_the_advocate_general_on_opinions():
    m = map_row({"ecli": "ECLI:EU:C:2026:1", "celex": "62025CC0001",
                 "advocate_general": "Norkus", "date_publication": "2026-01-02"})
    assert m.case["doctype"] == "opinion"
    assert m.ag["ag"] == "Norkus"


@pytest.mark.parametrize(
    "celex, kind",
    [("62025CJ0147", "judgment"), ("62025CO0852", "order"), ("62025CC0001", "opinion"),
     ("62025TJ0001", "judgment"), ("62025CV0001", "ruling"), ("62025CX0001", "other")],
)
def test_document_kind_follows_the_celex_descriptor(celex, kind):
    assert document_kind(celex) == kind


def test_map_cellar_keeps_every_column_the_mapping_reads():
    assert set(MAPPED_COLUMNS) - {"ecli"} <= set(MAP_CELLAR)


def test_write_runs_every_statement_in_one_transaction_document_last(client):
    m = map_row(extractor_row(ROW))

    counts = cjeu_loader.write(client, [m])

    conn = client._get_conn()
    assert conn.commit_count == 1
    statements = [sql for sql, _ in conn.executed]
    assert "INSERT INTO cle_v2.cjeu_document" in statements[-1]
    assert {"cases", "cases (enriched)", "case_judge", "case_party", "case_domain",
            "case_law_reference", "case_citation", "case_citation link (celex)",
            "case_citation link (ecli)", "cjeu_document"} <= set(counts)
    citation_sql, citation_params = next(
        (sql, params) for sql, params in conn.executed if "INSERT INTO cle_v2.case_citation" in sql)
    assert "'cellar_sparql'" in citation_sql
    assert citation_params[1] == ["62019CJ0001", "62020CJ0002"]


def test_link_statements_only_touch_unresolved_rows_of_this_batch(client):
    cjeu_loader.write(client, [map_row(extractor_row(ROW))])

    conn = client._get_conn()
    celex_sql, celex_params = next(
        (sql, params) for sql, params in conn.executed
        if sql.lstrip().startswith("UPDATE cle_v2.case_citation") and "target_celex_raw = ANY" in sql)
    assert "cc.target_case_id IS NULL" in celex_sql
    assert "cc.source_dataset = 'cellar_sparql'" in celex_sql
    assert celex_params == [["62025CJ0147"]]


def test_validate_loads_a_case_whose_celex_another_case_holds_without_celex(client, monkeypatch):
    monkeypatch.setattr(client, "fetch_rows",
                        lambda sql, params: [("62025CJ0147", "ECLI:EU:C:2026:999")])
    m = map_row(extractor_row(ROW))

    valid, failures = cjeu_loader.validate(client, [m])

    assert failures == []
    assert valid == [m]
    assert m.celex is None and m.case["celex"] is None and m.document["celex"] is None
    assert m.case["case_number"] == "C-147/25"  # still described by its CELEX


def test_validate_drops_a_celex_shared_within_the_batch(client):
    a = map_row({"ecli": "ECLI:EU:C:2026:1", "celex": "62025CJ0001"})
    b = map_row({"ecli": "ECLI:EU:C:2026:2", "celex": "62025CJ0001"})

    valid, failures = cjeu_loader.validate(client, [a, b])

    assert failures == []
    assert [m.case["celex"] for m in valid] == [None, None]


def test_validate_rejects_rows_without_ecli_or_with_malformed_celex(client):
    a = map_row({"celex": "62025CJ0001"})
    b = map_row({"ecli": "ECLI:EU:C:2026:2", "celex": "not-a-celex"})

    valid, failures = cjeu_loader.validate(client, [a, b])

    assert valid == []
    assert failures == [("62025CJ0001", "no ECLI"),
                        ("ECLI:EU:C:2026:2", "malformed CELEX 'not-a-celex'")]


def test_load_rows_retries_a_failed_batch_case_by_case(client, monkeypatch):
    calls = []

    def fake_write(_client, mappings):
        calls.append([m.ecli for m in mappings])
        if len(mappings) > 1 or mappings[0].ecli == "ECLI:EU:C:2026:2":
            raise RuntimeError("boom")
        return {}

    monkeypatch.setattr(cjeu_loader, "write", fake_write)
    failures = []
    rows = [{"ECLI": "ECLI:EU:C:2026:1", "celex": "62025CJ0001"},
            {"ECLI": "ECLI:EU:C:2026:2", "celex": "62025CJ0002"}]

    loaded = cjeu_loader.load_rows(client, rows, lambda key, error: failures.append(key))

    assert loaded == 1
    assert failures == ["ECLI:EU:C:2026:2"]
    assert calls == [["ECLI:EU:C:2026:1", "ECLI:EU:C:2026:2"],
                     ["ECLI:EU:C:2026:1"], ["ECLI:EU:C:2026:2"]]
