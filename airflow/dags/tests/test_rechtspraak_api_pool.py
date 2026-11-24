import etl_factory
import pytest


class _RecordingOperator:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _RecordingOperator.created.append(self)


@pytest.fixture
def operators(monkeypatch):
    _RecordingOperator.created = []
    monkeypatch.setattr(etl_factory, "PythonOperator", _RecordingOperator)
    return _RecordingOperator.created


@pytest.mark.parametrize("value", [None, "", "  "])
def test_pool_is_off_unless_configured(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("RECHTSPRAAK_API_POOL", raising=False)
    else:
        monkeypatch.setenv("RECHTSPRAAK_API_POOL", value)
    assert etl_factory.get_rechtspraak_api_pool() is None


def test_pool_name_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("RECHTSPRAAK_API_POOL", etl_factory.RECHTSPRAAK_API_POOL)
    assert etl_factory.get_rechtspraak_api_pool() == "rechtspraak_api"


def test_monthly_task_joins_the_given_pool(operators):
    etl_factory.build_monthly_task_group(
        None, "rechtspraak_etl", "RS", print, pool="rechtspraak_api"
    )
    assert operators[0].kwargs["pool"] == "rechtspraak_api"


def test_monthly_task_keeps_the_default_pool_without_one(operators):
    etl_factory.build_monthly_task_group(None, "echr_etl", "ECHR", print)
    assert "pool" not in operators[0].kwargs
