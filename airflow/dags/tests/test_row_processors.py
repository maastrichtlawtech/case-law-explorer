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
    ECHR_DOCUMENT_ID,
    ECLI,
    RS_TITLE,
)

from .fakes import FakeHook


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


def test_rs_processor_upload_row_rolls_back_the_whole_row_on_mid_row_failure(client, redirect_failure_log):
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


# --- Cellar processor: 2 statements (case + cjeu_document) -------------------


def test_celex_processor_upload_row_commits_once(client):
    processor = PostgresCelexProcessor(path="unused", client=client)
    row = {CELLAR_CELEX: "62024CJ0001"}

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    assert conn.commit_count == 1
    assert len(conn.executed) == 2


def test_celex_processor_upload_row_rolls_back_on_failure(client, redirect_failure_log):
    processor = PostgresCelexProcessor(path="unused", client=client)
    row = {CELLAR_CELEX: "62024CJ0002"}

    conn = client._get_conn()
    conn.fail_next_execute = True

    result = processor.upload_row(row)

    assert result == 0
    assert conn.commit_count == 0
    assert conn.rollback_count == 1


# --- ECHR processor: 2 statements (case + echr_document) ---------------------


def test_item_id_processor_upload_row_commits_once(client):
    processor = PostgresItemIdProcessor(path="unused", client=client)
    row = {ECHR_DOCUMENT_ID: "001-12345"}

    result = processor.upload_row(row)

    conn = client._get_conn()
    assert result == 1
    assert conn.commit_count == 1
    assert len(conn.executed) == 2


def test_item_id_processor_upload_row_rolls_back_on_failure(client, redirect_failure_log):
    processor = PostgresItemIdProcessor(path="unused", client=client)
    row = {ECHR_DOCUMENT_ID: "001-99999"}

    conn = client._get_conn()
    conn.fail_next_execute = True

    result = processor.upload_row(row)

    assert result == 0
    assert conn.commit_count == 0
    assert conn.rollback_count == 1
