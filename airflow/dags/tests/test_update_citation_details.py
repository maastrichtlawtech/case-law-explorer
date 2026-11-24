import importlib
import inspect
import sys

import pytest
from rechtspraak_extractor.rechtspraak import get_rechtspraak


class _DAG:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


if not hasattr(sys.modules["airflow"], "DAG"):
    sys.modules["airflow"].DAG = _DAG


@pytest.fixture
def load_dag(monkeypatch):
    def load(pool=None):
        if pool is None:
            monkeypatch.delenv("RECHTSPRAAK_API_POOL", raising=False)
        else:
            monkeypatch.setenv("RECHTSPRAAK_API_POOL", pool)
        import update_citation_details

        return importlib.reload(update_citation_details)

    return load


def test_pinned_extractor_has_no_ecli_list_argument():
    # The reason extract_missing_eclis can't call get_rechtspraak(eclis=...).
    params = inspect.signature(get_rechtspraak).parameters
    assert "eclis" not in params
    assert {"max_ecli", "sd", "ed", "save_file"} <= set(params)


def test_missing_eclis_fail_before_any_request(load_dag, monkeypatch, tmp_path):
    module = load_dag()

    def no_request(*args, **kwargs):
        raise AssertionError("must not reach the Rechtspraak API")

    monkeypatch.setattr(module, "get_rechtspraak", no_request)
    monkeypatch.setattr(module, "get_rechtspraak_metadata", no_request)
    monkeypatch.setattr(module, "get_citations", no_request)

    with pytest.raises(module.UnsupportedEcliListFetch, match="2 ECLIs"):
        module.extract_missing_eclis(
            ["ECLI:NL:HR:2026:1", "ECLI:NL:HR:2026:2"],
            output_path=str(tmp_path / "out.csv"),
        )


def test_no_missing_eclis_is_a_no_op(load_dag, tmp_path):
    module = load_dag()
    assert module.extract_missing_eclis([], output_path=str(tmp_path / "out.csv")) is None


def test_task_uses_the_default_pool_unless_configured(load_dag):
    task = load_dag().update_citation_details_task
    assert "pool" not in task.kwargs


def test_task_joins_the_configured_rechtspraak_pool(load_dag):
    task = load_dag(pool="rechtspraak_api").update_citation_details_task
    assert task.kwargs["pool"] == "rechtspraak_api"
