"""The client fixture's schema template must round-trip a live WAL-mode database."""

import sqlite3
from contextlib import closing

import pytest

from tests.database_template import DatabaseTemplate

MIGRATED_TABLES = {"alembic_version", "flow", "user"}


@pytest.fixture
def wal_source(tmp_path):
    """A migrated database whose committed pages still live only in its -wal file."""
    path = tmp_path / "source.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        # Keep committed pages out of the main file, as a live app connection does.
        connection.execute("PRAGMA wal_autocheckpoint=0")
        with connection:
            connection.execute("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO alembic_version VALUES ('head')")
            connection.execute('CREATE TABLE "user" (id INTEGER PRIMARY KEY)')
            connection.execute('CREATE TABLE flow (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES "user"(id))')
        assert path.with_name("source.db-wal").stat().st_size > 0
        yield path


def _tables(path):
    with closing(sqlite3.connect(path)) as connection:
        tables = {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return tables, version


def test_restore_returns_false_before_capture(tmp_path):
    assert DatabaseTemplate(tmp_path / "template.db").restore(tmp_path / "test.db") is False


def test_restores_wal_source_more_than_once(tmp_path, wal_source):
    template = DatabaseTemplate(tmp_path / "template.db")
    template.capture(wal_source)

    for name in ("first.db", "second.db"):
        destination = tmp_path / name
        assert template.restore(destination) is True
        assert _tables(destination) == (MIGRATED_TABLES, ("head",))


def test_template_is_readable_without_wal_sidecars(tmp_path, wal_source):
    template_path = tmp_path / "template.db"
    DatabaseTemplate(template_path).capture(wal_source)

    # Header bytes 18-19 hold the file format versions; 2 marks a WAL database.
    # Some SQLite builds (3.54.0) cannot open a WAL database read-only without
    # its -shm file, and a backup never leaves -wal/-shm files beside the copy.
    assert template_path.read_bytes()[18:20] == b"\x01\x01"
    assert [path.name for path in tmp_path.glob("template*")] == ["template.db"]
