import pytest

from utils import database


class FakeCursor:
    def __init__(self, granted):
        self.granted = granted
        self.queries = []
        self.closed = False

    def execute(self, query, parameters):
        self.queries.append((query, parameters))

    def fetchone(self):
        return (self.granted,)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, granted):
        self.cursor_instance = FakeCursor(granted)
        self.autocommit = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_wom_refresh_lock_acquires_and_releases(monkeypatch):
    connection = FakeConnection(True)
    monkeypatch.setattr(
        database, "connect", lambda: connection
    )

    with database.wom_refresh_lock() as acquired:
        assert acquired is True
        assert connection.autocommit is True
        assert len(connection.cursor_instance.queries) == 1
        assert "pg_try_advisory_lock" in (
            connection.cursor_instance.queries[0][0]
        )

    queries = connection.cursor_instance.queries
    assert len(queries) == 2
    assert "pg_advisory_unlock" in queries[1][0]
    assert queries[0][1] == queries[1][1]
    assert connection.cursor_instance.closed
    assert connection.closed


def test_wom_refresh_lock_rejects_overlap(monkeypatch):
    connection = FakeConnection(False)
    monkeypatch.setattr(
        database, "connect", lambda: connection
    )

    with database.wom_refresh_lock() as acquired:
        assert acquired is False

    queries = connection.cursor_instance.queries
    assert len(queries) == 1
    assert "pg_try_advisory_lock" in queries[0][0]
    assert connection.cursor_instance.closed
    assert connection.closed


def test_wom_refresh_lock_releases_on_exception(monkeypatch):
    connection = FakeConnection(True)
    monkeypatch.setattr(
        database, "connect", lambda: connection
    )

    with pytest.raises(ValueError, match="test failure"):
        with database.wom_refresh_lock() as acquired:
            assert acquired is True
            raise ValueError("test failure")

    queries = connection.cursor_instance.queries
    assert len(queries) == 2
    assert "pg_advisory_unlock" in queries[1][0]
    assert connection.cursor_instance.closed
    assert connection.closed
