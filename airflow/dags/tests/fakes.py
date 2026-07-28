"""Fake PostgresHook/connection/cursor doubles for exercising PostgresCLEClient
without a live database."""


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        if self._conn.fail_next_execute:
            self._conn.fail_next_execute = False
            raise RuntimeError("simulated statement failure")
        self._conn.executed.append((sql, params))
        self._conn._returned_rows = self._fake_returning(sql, params or {})

    def _fake_returning(self, sql, params):
        """
        Fabricate RETURNING output without a real database: single-row
        upserts (upsert_case/upsert_citation, params like %(ecli)s) get one
        row with a fresh id; bulk upserts (bulk_upsert_cases, params like
        %(ecli_0)s, %(ecli_1)s, ...) get one row per numeric suffix found in
        params, echoing back whatever that row's non-id column(s) were.
        """
        lowered = sql.lower()
        if "returning" not in lowered:
            return []
        returned_cols = [c.strip().rstrip(";") for c in lowered.split("returning", 1)[1].split(",")]

        indices = sorted({int(key.rsplit("_", 1)[1]) for key in params if key.rsplit("_", 1)[-1].isdigit()})
        if not indices:
            row = tuple(self._alloc_id() if col == "id" else None for col in returned_cols)
            return [row]

        rows = []
        for i in indices:
            row = tuple(
                self._alloc_id() if col == "id" else params.get(f"{col}_{i}") for col in returned_cols
            )
            rows.append(row)
        return rows

    def _alloc_id(self):
        new_id = self._conn.next_id
        self._conn.next_id += 1
        return new_id

    def fetchone(self):
        return self._conn._returned_rows[0] if self._conn._returned_rows else None

    def fetchall(self):
        return self._conn._returned_rows


class FakeConnection:
    def __init__(self):
        self.closed = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.executed = []
        self.next_id = 1
        self.fail_next_execute = False
        self._returned_rows = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = 1


class FakeHook:
    """Stand-in for PostgresHook: hands out a new FakeConnection per get_conn()
    call, and records every one it created so tests can assert on reuse.

    get_first/get_records are the read-only helpers PostgresCLEClient's
    resolve_*/has_* methods use directly (they manage their own connection
    lifecycle in real Airflow, so PostgresCLEClient doesn't wrap them).
    Tests drive their return value via get_first_return/get_records_return,
    keyed by whatever they like -- by default a single value is returned
    for every call, which is enough for testing one lookup at a time.
    """

    def __init__(self, postgres_conn_id=None):
        self.postgres_conn_id = postgres_conn_id
        self.connections = []
        self.get_first_return = None
        self.get_first_calls = []
        self.get_records_return = []

    def get_conn(self):
        conn = FakeConnection()
        self.connections.append(conn)
        return conn

    def get_first(self, sql, parameters=None):
        self.get_first_calls.append((sql, parameters))
        return self.get_first_return

    def get_records(self, sql, parameters=None):
        return self.get_records_return
