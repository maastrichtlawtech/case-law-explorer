"""
Test scaffolding: puts airflow/dags on sys.path (DAGs import each other as
top-level packages -- data_loading.*, definitions.*) and stubs out the
`airflow` package tree so data_loading.clients.postgres's
`from airflow.providers.postgres.hooks.postgres import PostgresHook` succeeds
without a real Airflow install. Tests replace PostgresHook themselves with a
FakeHook (see fakes.py) to drive PostgresCLEClient without a live database.
"""

import os
import sys
import types

DAGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if DAGS_DIR not in sys.path:
    sys.path.insert(0, DAGS_DIR)


def _stub_package(name):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = []  # mark as a package so submodule imports resolve
        sys.modules[name] = module
    return sys.modules[name]


_stub_package("airflow")
_stub_package("airflow.providers")
_stub_package("airflow.providers.postgres")
_stub_package("airflow.providers.postgres.hooks")

if "airflow.providers.postgres.hooks.postgres" not in sys.modules:
    hooks_postgres = types.ModuleType("airflow.providers.postgres.hooks.postgres")

    class PostgresHook:  # placeholder; real tests monkeypatch this attribute
        def __init__(self, postgres_conn_id=None):
            self.postgres_conn_id = postgres_conn_id

        def get_conn(self):
            raise NotImplementedError("tests must monkeypatch PostgresHook/get_conn")

    hooks_postgres.PostgresHook = PostgresHook
    sys.modules["airflow.providers.postgres.hooks.postgres"] = hooks_postgres
