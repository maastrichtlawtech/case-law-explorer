import pytest

from data_loading.clients import postgres as postgres_module
from data_loading.clients.postgres import PostgresCLEClient
from data_loading.row_processors import postgres as row_processors_module
from data_loading.row_processors.postgres import (
    PostgresCelexProcessor,
    PostgresItemIdProcessor,
    PostgresRSProcessor,
)
from definitions.terminology.attribute_names import (
    CELLAR_CELEX,
    ECHR_APPLICANTS,
    ECHR_DOCUMENT_ID,
    ECHR_DOCUMENT_TYPE,
    ECHR_LANGUAGE,
    ECHR_REFERENCE_DATE,
    ECLI,
    RS_BWB_ID,
    RS_CITING,
    RS_LEGISLATIONS,
    RS_TITLE,
)

from .fakes import FakeHook

RS_ENRICHMENT_STATEMENTS = 5  # jurisdiction, courts, procedures, document types, cases
ECHR_LOOKUP_STATEMENTS = 2  # ECTHR court (+ jurisdiction), document types


@pytest.fixture
def hook(monkeypatch):
    fake_hook = FakeHook()
    monkeypatch.setattr(postgres_module, "PostgresHook", lambda postgres_conn_id=None: fake_hook)
    return fake_hook


@pytest.fixture
def client(hook):
    return PostgresCLEClient()


@pytest.fixture(autouse=True)
def redirect_failure_log(tmp_path, monkeypatch):
    """Row processors log failed rows to a real repo path by default;
    redirect that to a throwaway file so tests don't write into the repo."""
    failure_log = tmp_path / "failed.csv"
    monkeypatch.setattr(row_processors_module, "get_path_processed", lambda name: str(failure_log))
    # Failures go beside the processed CSV; tests pass path="unused", so the
    # report lands in the working directory: make that the temporary one.
    monkeypatch.chdir(tmp_path)
    return failure_log


# --- RS processor: 3 statements (case + rs_document + case_text) ------------


def test_rs_processor_upload_row_commits_once_for_the_whole_row(client):
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {ECLI: "ECLI:NL:HR:2024:1", RS_TITLE: "Some title"}

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    assert conn.commit_count == 1
    assert len(conn.executed) == 3


def test_rs_processor_upload_row_rolls_back_the_whole_row_on_mid_row_failure(
    client, redirect_failure_log
):
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {ECLI: "ECLI:NL:HR:2024:2", RS_TITLE: "Some title"}

    conn = client._get_conn()
    conn.fail_next_execute = True  # fail on the 2nd statement (rs_document upsert)

    result = processor.upload_row(row)

    assert result == 0
    assert conn.commit_count == 0
    # only the case upsert (statement 1) landed before the failure, and that
    # was rolled back too since it's inside the same transaction() block
    assert conn.rollback_count == 1
    assert client._tx_depth == 0
    assert "ECLI:NL:HR:2024:2" in redirect_failure_log.read_text()


def test_rs_processor_upload_row_skips_rows_without_ecli(client):
    processor = PostgresRSProcessor(path="unused", client=client)
    assert processor.upload_row({}) == 0
    assert client._conn is None  # never even opened a connection


# --- RS processor: case_citation / case_law_reference ------------------------


def test_rs_processor_writes_one_case_citation_per_target_ecli(client, hook):
    processor = PostgresRSProcessor(path="unused", client=client)
    hook.get_first_return = lambda sql, parameters: (
        (7, ["RS"]) if parameters["val"] == "ECLI:NL:HR:2024:100" else None
    )
    row = {
        ECLI: "ECLI:NL:HR:2024:3",
        RS_TITLE: "Some title",
        RS_CITING: "ECLI:NL:HR:2024:100; ECLI:NL:HR:2024:101",
    }

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    # case + rs_document + case_text + 2 citations
    assert len(conn.executed) == 5
    citation_calls = [params for _, params in conn.executed[3:5]]
    resolved = next(p for p in citation_calls if p["target_ecli_raw"] is None)
    unresolved = next(p for p in citation_calls if p["target_ecli_raw"] is not None)
    assert resolved["target_case_id"] == 7
    assert unresolved["target_ecli_raw"] == "ECLI:NL:HR:2024:101"
    assert unresolved["target_case_id"] is None
    assert resolved["relation_type"] == "cites" == unresolved["relation_type"]
    assert resolved["source_dataset"] == "rs_lido_sqlite" == unresolved["source_dataset"]


def test_rs_processor_skips_formal_relation_labels_in_citations_outgoing(client, hook):
    """The live-API fallback puts dcterms:relation labels in citations_outgoing;
    they are not citations and must not end up in target_ecli_raw."""
    processor = PostgresRSProcessor(path="unused", client=client)
    hook.get_first_return = lambda sql, parameters: None
    row = {
        ECLI: "ECLI:NL:HR:2024:5",
        RS_TITLE: "Some title",
        RS_CITING: (
            "Eerste aanleg: ECLI:NL:RBAMS:2019:123, Bekrachtiging/bevestiging; "
            "ecli:nl:hr:2024:102; ECLI:NL:HR:2024:102\n"
            "Cassatie: ECLI:NL:HR:2025:1\nnot an ecli"
        ),
    }

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    citation_calls = [params for _, params in conn.executed[3:]]
    assert [p["target_ecli_raw"] for p in citation_calls] == ["ECLI:NL:HR:2024:102"]
    assert citation_calls[0]["source_dataset"] == "rs_lido_sqlite"


def test_citing_eclis_splits_on_semicolons_with_any_spacing():
    """Finding 12: 'A;B' and 'A ;B' used to stay one item, which is no ECLI,
    so both citations were lost."""
    value = "ECLI:NL:HR:2024:1;ECLI:NL:HR:2024:2 ; ECLI:NL:HR:2024:3;\nECLI:NL:HR:2024:4"
    assert row_processors_module._citing_eclis(value) == [
        "ECLI:NL:HR:2024:1",
        "ECLI:NL:HR:2024:2",
        "ECLI:NL:HR:2024:3",
        "ECLI:NL:HR:2024:4",
    ]


def test_rs_processor_sets_cross_jurisdiction_on_new_citation_rows(client, hook):
    """R2.7: resolved from the target's sources (the source is RS), unresolved
    from the cited ECLI's corpus."""
    processor = PostgresRSProcessor(path="unused", client=client)
    found = {
        "ECLI:NL:HR:2024:100": (7, ["RS"]),
        "ECLI:EU:C:2019:189": (8, ["CJEU"]),
        "ECLI:NL:RVS:2020:1": (9, ["Rechtspraak"]),  # legacy label, still RS
    }
    hook.get_first_return = lambda sql, parameters: found.get(parameters["val"])
    row = {
        ECLI: "ECLI:NL:HR:2024:3",
        RS_TITLE: "Some title",
        RS_CITING: "; ".join(
            list(found)
            + [
                "ECLI:CE:ECHR:2019:0101JUD001234517",
                "ECLI:NL:HR:2099:1",
                "ECLI:BE:CASS:2019:ARR.1",
            ]
        ),
    }

    assert processor.upload_row(row) == 1

    calls = [params for _, params in client._get_conn().executed[3:]]
    flags = {p["target_case_id"] or p["target_ecli_raw"]: p["is_cross_jurisdiction"] for p in calls}
    assert flags == {
        7: False,
        8: True,
        9: False,
        "ECLI:CE:ECHR:2019:0101JUD001234517": True,
        "ECLI:NL:HR:2099:1": False,
        "ECLI:BE:CASS:2019:ARR.1": True,  # a foreign court: outside every collection
    }


def test_rs_processor_writes_no_citation_rows_when_citations_outgoing_absent(client):
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {ECLI: "ECLI:NL:HR:2024:4", RS_TITLE: "Some title"}

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    assert len(conn.executed) == 3  # case + rs_document + case_text only


def test_rs_processor_writes_one_law_reference_per_legislation(client, monkeypatch):
    """Flag off (the default): the base branch's statements, no act lookup."""
    monkeypatch.delenv("RS_RESOLVE_BWB_ENABLED", raising=False)
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {
        ECLI: "ECLI:NL:HR:2024:5",
        RS_TITLE: "Some title",
        RS_LEGISLATIONS: "art. 6:162 BW; art. 3:1 Awb",
        RS_BWB_ID: "BWBR0005289",
    }

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    assert len(conn.executed) == 5  # case + rs_document + case_text + 2 law refs
    law_ref_params = [params for _, params in conn.executed[3:5]]
    assert {p["raw_reference"] for p in law_ref_params} == {"art. 6:162 BW", "art. 3:1 Awb"}
    assert all(p["raw_resource"] == "BWBR0005289" for p in law_ref_params)
    assert all(p["source_dataset"] == "rs_lido_sqlite" for p in law_ref_params)
    assert not any("FROM cle_v2.legislation" in sql for sql, _ in conn.executed)


def test_rs_processor_resolves_law_references_with_the_flag_on(client, monkeypatch):
    monkeypatch.setenv("RS_RESOLVE_BWB_ENABLED", "true")
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {
        ECLI: "ECLI:NL:HR:2024:5",
        RS_TITLE: "Some title",
        RS_LEGISLATIONS: "art. 6:162 BW; art. 3:1 Awb",
        RS_BWB_ID: "BWBR0005289",
    }

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    # case + rs_document + case_text + one act lookup (cached per BWB id) + 2 law refs
    assert len(conn.executed) == 6
    assert "FROM cle_v2.legislation" in conn.executed[3][0]
    law_ref_params = [params for _, params in conn.executed[4:6]]
    assert {p["raw_reference"] for p in law_ref_params} == {"art. 6:162 BW", "art. 3:1 Awb"}
    assert all(p["raw_resource"] == "BWBR0005289" for p in law_ref_params)
    assert all(p["source_dataset"] == "rs_lido_sqlite" for p in law_ref_params)
    # The fake finds no act: unresolved rows, under uk_raw with its predicate.
    for sql, params in conn.executed[4:6]:
        assert "legislation_id" not in params
        assert "WHERE provision_id IS NULL AND legislation_id IS NULL" in sql


LIDO_URL = "http://linkeddata.overheid.nl/terms/bwb/id/{}/1710393/2013-01-01/2013-01-01"


# The base branch's (origin/feature/cross-dataset-linking) row derivation,
# copied verbatim: with RS_RESOLVE_BWB_ENABLED off the processor must match it.
_BASE_LAW_REFERENCE_BLOCK = """        bwb_id = row.get(RS_BWB_ID) or None
        return [
            {
                "raw_reference": legislation,
                "raw_resource": bwb_id,
                "source_dataset": "rs_lido_sqlite",
            }
            for legislation in (_split_set(row.get(RS_LEGISLATIONS)) or [])
        ]"""


def _base_law_reference_rows(row):
    bwb_id = row.get(RS_BWB_ID) or None
    return [
        {
            "raw_reference": legislation,
            "raw_resource": bwb_id,
            "source_dataset": "rs_lido_sqlite",
        }
        for legislation in (row_processors_module._split_set(row.get(RS_LEGISLATIONS)) or [])
    ]


# Illustrative rows (made-up label ids), not real case data.
_FLAG_OFF_ROWS = [
    {RS_LEGISLATIONS: LIDO_URL.format("BWBR0005290"), RS_BWB_ID: ""},
    {RS_LEGISLATIONS: LIDO_URL.format("BWBR0005290"), RS_BWB_ID: "BWBR0001854"},
    {RS_LEGISLATIONS: "art. 8 EVRM; " + LIDO_URL.format("BWBR0005537"), RS_BWB_ID: None},
    {RS_LEGISLATIONS: "art. 8 EVRM", RS_BWB_ID: "BWBR0001854"},
    {RS_LEGISLATIONS: "", RS_BWB_ID: "BWBR0001854"},
    {RS_BWB_ID: "BWBR0001854"},
]


@pytest.mark.parametrize("flag", [None, "", "false", "0", "off"])
def test_rs_law_reference_rows_match_the_base_with_the_flag_off(client, monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("RS_RESOLVE_BWB_ENABLED", raising=False)
    else:
        monkeypatch.setenv("RS_RESOLVE_BWB_ENABLED", flag)
    processor = PostgresRSProcessor(path="unused", client=client)

    for row in _FLAG_OFF_ROWS:
        assert processor._law_reference_rows(row, case_id=1) == _base_law_reference_rows(row)


def test_rs_law_reference_flag_off_block_is_the_base_text():
    """The flag-off block is the base text, so caselaw-coolify's image
    compatibility patch (which rewrites exactly this text) still applies."""
    import inspect

    source = inspect.getsource(row_processors_module)
    assert source.count(_BASE_LAW_REFERENCE_BLOCK) == 1
    assert '"/bwb/id/" in' not in source  # that patch's upstream marker


def test_rs_law_reference_flag_off_writes_the_base_statements(client, monkeypatch):
    monkeypatch.delenv("RS_RESOLVE_BWB_ENABLED", raising=False)
    monkeypatch.setattr(client, "bwb_legislation_id", lambda bwb: 77)
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {RS_LEGISLATIONS: LIDO_URL.format("BWBR0005290"), RS_BWB_ID: ""}

    for law_reference in processor._law_reference_rows(row, case_id=5):
        client.upsert_law_reference(case_id=5, **law_reference)

    ((sql, params),) = client._get_conn().executed
    assert params == {
        "case_id": 5,
        "raw_resource": None,
        "raw_reference": LIDO_URL.format("BWBR0005290"),
        "role": "cited",
        "source_dataset": "rs_lido_sqlite",
    }
    assert "legislation_id IS NULL" in sql


@pytest.fixture
def resolve_bwb(monkeypatch):
    monkeypatch.setenv("RS_RESOLVE_BWB_ENABLED", "true")


def test_rs_law_reference_takes_the_bwb_id_from_each_lido_url(client, resolve_bwb):
    """Illustrative LiDO URLs (made-up label ids), not real case data."""
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {
        RS_LEGISLATIONS: "; ".join(
            [LIDO_URL.format("BWBR0005290"), LIDO_URL.format("BWBR0005537"), "art. 8 EVRM"]
        ),
        RS_BWB_ID: "",
    }

    rows = processor._law_reference_rows(row, case_id=1)

    assert [r["raw_resource"] for r in rows] == ["BWBR0005290", "BWBR0005537"]
    assert all(r["resolve_legislation"] is True for r in rows)


def test_rs_law_reference_url_wins_over_the_case_bwb_id(client, resolve_bwb):
    processor = PostgresRSProcessor(path="unused", client=client)
    row = {RS_LEGISLATIONS: LIDO_URL.format("BWBR0005290"), RS_BWB_ID: "BWBR0001854"}

    rows = processor._law_reference_rows(row, case_id=1)

    assert [r["raw_resource"] for r in rows] == ["BWBR0005290"]


def test_rs_law_reference_resolved_row_carries_legislation_id(client, monkeypatch):
    monkeypatch.setattr(
        client, "bwb_legislation_id", lambda bwb: 77 if bwb == "BWBR0005290" else None
    )

    client.upsert_law_reference(
        case_id=5,
        raw_reference="x",
        raw_resource="BWBR0005290",
        source_dataset="rs_lido_sqlite",
        resolve_legislation=True,
    )
    client.upsert_law_reference(
        case_id=5,
        raw_reference="y",
        raw_resource="BWBR0009999",
        source_dataset="rs_lido_sqlite",
        resolve_legislation=True,
    )

    conn = client._get_conn()
    (resolved_sql, resolved), (unresolved_sql, unresolved) = conn.executed
    assert resolved["legislation_id"] == 77
    assert "WHERE NOT EXISTS" in resolved_sql and "ON CONFLICT DO NOTHING" in resolved_sql
    assert "legislation_id" not in unresolved
    assert "legislation_id IS NULL AND raw_resource IS NOT NULL" in unresolved_sql


def test_rs_law_reference_not_resolved_unless_asked(client, monkeypatch):
    monkeypatch.setattr(client, "bwb_legislation_id", lambda bwb: 77)

    client.upsert_law_reference(case_id=5, raw_reference="x", raw_resource="BWBR0005290")

    conn = client._get_conn()
    assert "legislation_id" not in conn.executed[0][1]


def test_rs_processor_upload_rows_writes_citations_per_row_in_batch(client, hook):
    processor = PostgresRSProcessor(path="unused", client=client)
    hook.get_first_return = None  # nothing resolves -> all unresolved raw ECLIs
    rows = [
        {ECLI: "ECLI:NL:HR:2024:30", RS_TITLE: "A", RS_CITING: "ECLI:NL:HR:2024:200"},
        {ECLI: "ECLI:NL:HR:2024:31", RS_TITLE: "B"},
    ]

    result = processor.upload_rows(rows)

    conn = client._get_conn()
    assert result == 2
    # bulk cases + bulk rs_document + bulk case_text + 1 citation (row 2 has
    # none), then the cases enrichment (case_enrichment.enrich_rs)
    assert len(conn.executed) == 4 + RS_ENRICHMENT_STATEMENTS
    _, citation_params = conn.executed[3]
    assert citation_params["target_ecli_raw"] == "ECLI:NL:HR:2024:200"


# --- Cellar processor: delegates to data_loading/cjeu_loader.py -------------


def test_celex_processor_upload_row_writes_one_case_in_one_transaction(client):
    processor = PostgresCelexProcessor(path="unused", client=client)
    row = {CELLAR_CELEX: "62024CJ0001", ECLI: "ECLI:EU:C:2024:1"}

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    assert conn.commit_count == 2  # CELEX ownership read, then the write
    statements = [sql for sql, _ in conn.executed]
    assert any("INSERT INTO cle_v2.cases" in sql for sql in statements)
    assert "INSERT INTO cle_v2.cjeu_document" in statements[-1]


def test_celex_processor_upload_row_rolls_back_on_failure(client, redirect_failure_log):
    processor = PostgresCelexProcessor(path="unused", client=client)
    row = {CELLAR_CELEX: "62024CJ0002", ECLI: "ECLI:EU:C:2024:2"}

    conn = client._get_conn()
    conn.executed.clear()
    conn.fail_next_execute = True  # the CELEX ownership read

    with pytest.raises(RuntimeError):
        processor.upload_row(row)
    assert conn.commit_count == 0


# --- ECHR processor: 2 statements (case + echr_document) ---------------------


def test_item_id_processor_upload_row_commits_once(client):
    processor = PostgresItemIdProcessor(path="unused", client=client)
    row = {ECHR_DOCUMENT_ID: "001-12345"}

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    assert conn.commit_count == 1
    assert len(conn.executed) == 2


def test_item_id_processor_normalizes_hudoc_language_to_iso2(client):
    processor = PostgresItemIdProcessor(path="unused", client=client)

    assert (
        processor._detail_row({ECHR_DOCUMENT_ID: "001-12345", ECHR_LANGUAGE: "ENG"}, case_id=7)[
            "language"
        ]
        == "en"
    )
    assert (
        processor._detail_row({ECHR_DOCUMENT_ID: "001-12346", ECHR_LANGUAGE: "FRE"}, case_id=8)[
            "language"
        ]
        == "fr"
    )


def test_item_id_processor_upload_row_rolls_back_on_failure(client, redirect_failure_log):
    processor = PostgresItemIdProcessor(path="unused", client=client)
    row = {ECHR_DOCUMENT_ID: "001-99999"}

    conn = client._get_conn()
    conn.fail_next_execute = True

    result = processor.upload_row(row)

    assert result == 0
    assert conn.commit_count == 0
    assert conn.rollback_count == 1


def test_item_id_processor_groups_language_variants_by_ecli(client):
    processor = PostgresItemIdProcessor(path="unused", client=client)
    rows = [
        {
            ECHR_DOCUMENT_ID: "001-fre",
            ECLI: "ECLI:CE:ECHR:2026:1",
            ECHR_LANGUAGE: "FRE",
            ECHR_DOCUMENT_TYPE: "JUD",
        },
        {
            ECHR_DOCUMENT_ID: "001-eng",
            ECLI: "ECLI:CE:ECHR:2026:1",
            ECHR_LANGUAGE: "ENG",
            ECHR_DOCUMENT_TYPE: "JUD",
        },
    ]

    assert processor.upload_rows(rows) == 2
    conn = client._get_conn()
    assert conn.commit_count == 1
    # lookups, one case, two document variants, the case enrichment
    assert len(conn.executed) == ECHR_LOOKUP_STATEMENTS + 4
    _, case_params = conn.executed[ECHR_LOOKUP_STATEMENTS]
    assert case_params["item_id"] == "001-eng"
    assert case_params["ecli"] == "ECLI:CE:ECHR:2026:1"
    detail_case_ids = {
        params["case_id"] for _, params in conn.executed[ECHR_LOOKUP_STATEMENTS + 1 : -1]
    }
    assert len(detail_case_ids) == 1
    enrichment_sql, enrichment_params = conn.executed[-1]
    assert "UPDATE cle_v2.cases k SET" in enrichment_sql
    assert enrichment_params[0] == "judgment"


def test_item_id_processor_groups_ecli_less_variants_by_appno_and_reference_date(client):
    processor = PostgresItemIdProcessor(path="unused", client=client)
    rows = [
        {
            ECHR_DOCUMENT_ID: "001-fre",
            ECHR_APPLICANTS: "12345/26",
            ECHR_REFERENCE_DATE: "2026-07-03",
            ECHR_LANGUAGE: "FRE",
        },
        {
            ECHR_DOCUMENT_ID: "001-eng",
            ECHR_APPLICANTS: "12345/26",
            ECHR_REFERENCE_DATE: "2026-07-03",
            ECHR_LANGUAGE: "ENG",
        },
    ]

    assert processor.upload_rows(rows) == 2
    conn = client._get_conn()
    assert len(conn.executed) == ECHR_LOOKUP_STATEMENTS + 4
    _, case_params = conn.executed[ECHR_LOOKUP_STATEMENTS]
    assert case_params["item_id"] == "001-eng"
    assert case_params["ecli"] is None


# --- Batched path: upload_rows ----------------------------------------------


def test_rs_processor_upload_rows_uses_three_bulk_statements(client):
    processor = PostgresRSProcessor(path="unused", client=client)
    rows = [
        {ECLI: "ECLI:NL:HR:2024:10", RS_TITLE: "A"},
        {ECLI: "ECLI:NL:HR:2024:11", RS_TITLE: "B"},
        {ECLI: "ECLI:NL:HR:2024:12", RS_TITLE: "C"},
    ]

    result = processor.upload_rows(rows)

    conn = client._get_conn()
    assert result == 3
    # one bulk statement per table (cases, rs_document, case_text), then the
    # cases enrichment in its own transaction
    assert len(conn.executed) == 3 + RS_ENRICHMENT_STATEMENTS
    assert conn.commit_count == 2
    assert "UPDATE cle_v2.cases k SET" in conn.executed[-1][0]


def test_upload_rows_collapses_duplicate_keys_to_last_occurrence(client):
    processor = PostgresRSProcessor(path="unused", client=client)
    rows = [
        {ECLI: "ECLI:NL:HR:2024:20", RS_TITLE: "first"},
        {ECLI: "ECLI:NL:HR:2024:20", RS_TITLE: "second"},
    ]

    result = processor.upload_rows(rows)

    conn = client._get_conn()
    assert result == 1
    _, params = conn.executed[0]
    assert params["title_0"] == "second"
    assert "title_1" not in params


def test_upload_rows_skips_rows_without_key_and_handles_empty(client):
    processor = PostgresCelexProcessor(path="unused", client=client)
    assert processor.upload_rows([{}, {CELLAR_CELEX: ""}]) == 0
    assert client._conn is None  # nothing valid -> no connection opened


def test_echr_group_failure_is_reported_without_splitting_conceptual_case(
    client, redirect_failure_log
):
    processor = PostgresItemIdProcessor(path="unused", client=client)
    rows = [
        {ECHR_DOCUMENT_ID: "001-11111"},
        {ECHR_DOCUMENT_ID: "001-22222"},
    ]

    conn = client._get_conn()
    conn.fail_next_execute = True  # bulk cases upsert fails, then row path runs

    result = processor.upload_rows(rows)

    assert result == 1
    assert conn.rollback_count == 1
    assert conn.commit_count == 1
    assert "001-11111" in redirect_failure_log.read_text()
