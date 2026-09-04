import pytest
from data_loading.clients import postgres as postgres_module
from data_loading.clients.postgres import PostgresCLEClient

from .fakes import FakeHook


@pytest.fixture
def hook(monkeypatch):
    fake_hook = FakeHook()
    monkeypatch.setattr(postgres_module, "PostgresHook", lambda postgres_conn_id=None: fake_hook)
    return fake_hook


@pytest.fixture
def client(hook):
    return PostgresCLEClient()


# --- connection reuse (the original leak) -----------------------------------


def test_get_conn_is_cached_across_calls(client, hook):
    conn1 = client._get_conn()
    conn2 = client._get_conn()
    assert conn1 is conn2
    assert len(hook.connections) == 1


def test_multiple_upserts_share_one_connection(client, hook):
    case_id = client.upsert_case(ecli="ECLI:NL:HR:2024:1", title="t", source="Rechtspraak")
    client.upsert(table="rs_document", conflict_cols=["case_id"], values={"case_id": case_id})
    client.upsert_case_text(case_id=case_id, language="nl", source="RECHTSPRAAK", fulltext="text")

    assert len(hook.connections) == 1
    assert len(client._get_conn().executed) == 3


def test_get_conn_reopens_after_close(client, hook):
    first = client._get_conn()
    client.close()
    second = client._get_conn()

    assert first is not second
    assert len(hook.connections) == 2


# --- close() / context manager -----------------------------------------------


def test_close_releases_and_clears_connection(client):
    conn = client._get_conn()
    client.close()

    assert conn.closed == 1
    assert client._conn is None


def test_close_is_a_no_op_if_never_connected(client):
    client.close()  # must not raise
    assert client._conn is None


def test_context_manager_closes_on_normal_exit(hook):
    with PostgresCLEClient() as c:
        conn = c._get_conn()
        assert conn.closed == 0
    assert conn.closed == 1


def test_context_manager_closes_on_exception(hook):
    captured = {}
    with pytest.raises(ValueError):
        with PostgresCLEClient() as c:
            captured["conn"] = c._get_conn()
            raise ValueError("boom")
    assert captured["conn"].closed == 1


# --- autocommit behavior outside any transaction() ---------------------------


def test_execute_commits_immediately_when_not_in_a_transaction(client):
    client.upsert_case(ecli="ECLI:NL:HR:2024:2", source="Rechtspraak")
    assert client._get_conn().commit_count == 1


def test_execute_rolls_back_once_on_failure_outside_transaction(client):
    conn = client._get_conn()
    conn.fail_next_execute = True

    with pytest.raises(RuntimeError):
        client.upsert_case(ecli="ECLI:NL:HR:2024:3", source="Rechtspraak")

    assert conn.rollback_count == 1
    assert conn.commit_count == 0


# --- transaction(): grouped commit/rollback ----------------------------------


def test_transaction_commits_once_for_multiple_statements(client):
    with client.transaction():
        case_id = client.upsert_case(ecli="ECLI:NL:HR:2024:4", source="Rechtspraak")
        client.upsert(table="rs_document", conflict_cols=["case_id"], values={"case_id": case_id})
        client.upsert_case_text(case_id=case_id, language="nl", source="RECHTSPRAAK", fulltext="t")

    conn = client._get_conn()
    assert conn.commit_count == 1
    assert len(conn.executed) == 3


def test_transaction_rolls_back_exactly_once_on_mid_block_failure(client):
    conn = client._get_conn()

    with pytest.raises(RuntimeError):
        with client.transaction():
            client.upsert_case(ecli="ECLI:NL:HR:2024:5", source="Rechtspraak")
            conn.fail_next_execute = True
            client.upsert(table="rs_document", conflict_cols=["case_id"], values={"case_id": 1})

    # one statement succeeded, one failed -- the whole group must roll back,
    # exactly once (not once from _execute and again from transaction()).
    assert conn.rollback_count == 1
    assert conn.commit_count == 0
    assert client._tx_depth == 0


# --- has_lido_resolution(): the update_citations skip-check -----------------


def test_has_lido_resolution_true_when_row_found(client, hook):
    hook.get_first_return = (1,)
    assert client.has_lido_resolution("ECLI:NL:HR:2024:1") is True


def test_has_lido_resolution_false_when_no_row_found(client, hook):
    hook.get_first_return = None
    assert client.has_lido_resolution("ECLI:NL:HR:2024:2") is False


def test_has_lido_resolution_passes_the_ecli_as_a_parameter(client, hook):
    hook.get_first_return = None
    client.has_lido_resolution("ECLI:NL:HR:2024:3")
    (_, parameters) = hook.get_first_calls[-1]
    assert parameters == {"ecli": "ECLI:NL:HR:2024:3"}


def test_resolve_echr_language_by_item_id(client, hook):
    hook.get_first_return = ("fr",)

    assert client.resolve_echr_language_by_item_id("001-250884") == "fr"
    sql, parameters = hook.get_first_calls[-1]
    assert "echr_document" in sql
    assert parameters == {"val": "001-250884"}


def test_nested_transactions_only_commit_at_the_outermost_level(client):
    with client.transaction():
        client.upsert_case(ecli="ECLI:NL:HR:2024:6", source="Rechtspraak")
        with client.transaction():
            client.upsert(table="rs_document", conflict_cols=["case_id"], values={"case_id": 1})
        assert client._get_conn().commit_count == 0  # inner block must not have committed
    assert client._get_conn().commit_count == 1
