"""Tests for deployment timestamp rewrite / server_default drop migration."""

import importlib

import sqlalchemy as sa
from sqlalchemy import create_engine

_MIGRATION = importlib.import_module("langflow.alembic.versions.a8f3c2d1e4b5_rewrite_deployment_sqlite_timestamps")


def test_sqlite_timestamp_rewrite_pads_whole_second_strings():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text("CREATE TABLE deployment (id BLOB PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        )
        conn.execute(
            sa.text(
                "INSERT INTO deployment (id, created_at, updated_at) VALUES "
                "(:id, '2026-07-09 21:00:00', '2026-07-09 21:00:00')"
            ),
            {"id": b"\x01" * 16},
        )
        _MIGRATION._rewrite_table_timestamps(conn, "deployment", ("created_at", "updated_at"))
        row = conn.execute(sa.text("SELECT quote(created_at), quote(updated_at) FROM deployment")).one()
        assert row[0] == "'2026-07-09 21:00:00.000000'"
        assert row[1] == "'2026-07-09 21:00:00.000000'"


def test_sqlite_timestamp_rewrite_preserves_existing_fractional_seconds():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text("CREATE TABLE deployment (id BLOB PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        )
        conn.execute(
            sa.text(
                "INSERT INTO deployment (id, created_at, updated_at) VALUES "
                "(:id, '2026-07-09 21:00:00.123456', '2026-07-09 21:00:00.654321')"
            ),
            {"id": b"\x02" * 16},
        )
        _MIGRATION._rewrite_table_timestamps(conn, "deployment", ("created_at", "updated_at"))
        row = conn.execute(sa.text("SELECT quote(created_at), quote(updated_at) FROM deployment")).one()
        assert row[0] == "'2026-07-09 21:00:00.123456'"
        assert row[1] == "'2026-07-09 21:00:00.654321'"


def test_drop_timestamp_server_defaults_clears_sqlite_current_timestamp(monkeypatch):
    """batch_alter_table must remove DEFAULT CURRENT_TIMESTAMP from timestamp columns."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE deployment ("
                "id BLOB PRIMARY KEY, "
                "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        before = {c["name"]: c.get("default") for c in inspect(conn).get_columns("deployment")}
        assert before["created_at"] == "CURRENT_TIMESTAMP"
        assert before["updated_at"] == "CURRENT_TIMESTAMP"

        ops = Operations(MigrationContext.configure(conn))
        monkeypatch.setattr(_MIGRATION, "op", ops)
        _MIGRATION._drop_timestamp_server_defaults(conn, "deployment", ("created_at", "updated_at"))

        after = {c["name"]: c.get("default") for c in inspect(conn).get_columns("deployment")}
        assert after["created_at"] is None
        assert after["updated_at"] is None
        ddl = conn.execute(sa.text("SELECT sql FROM sqlite_master WHERE name='deployment'")).scalar()
        assert ddl is not None
        assert "DEFAULT" not in ddl.upper()


def test_upgrade_skips_data_rewrite_on_non_sqlite(monkeypatch):
    """upgrade() must not rewrite rows on PostgreSQL (schema default drop still runs)."""

    class _FakeConn:
        dialect = type("D", (), {"name": "postgresql"})()

    calls: list[tuple] = []

    def _fake_rewrite(conn, table_name, column_names):  # noqa: ARG001
        calls.append(("rewrite", table_name))

    def _fake_drop(conn, table_name, column_names):  # noqa: ARG001
        calls.append(("drop", table_name))

    monkeypatch.setattr(_MIGRATION.op, "get_bind", lambda: _FakeConn())
    monkeypatch.setattr(_MIGRATION, "_rewrite_table_timestamps", _fake_rewrite)
    monkeypatch.setattr(_MIGRATION, "_drop_timestamp_server_defaults", _fake_drop)
    _MIGRATION.upgrade()
    assert all(kind == "drop" for kind, _ in calls)
    assert {name for _, name in calls} == {
        "deployment",
        "deployment_provider_account",
        "flow_version_deployment_attachment",
    }
