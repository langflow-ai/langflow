"""Tests for the spanstatus/spantype legacy-uppercase enum relabel migration.

Pure tests (revision chain, relabel-map correctness, postgres guard) run
everywhere. The functional relabel tests require a real PostgreSQL instance and
are skipped unless ``LANGFLOW_TEST_DATABASE_URI`` is set.
"""

from __future__ import annotations

import importlib
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.services.database.models.traces.model import SpanKind, SpanStatus, SpanType

_MIGRATION = importlib.import_module(
    "langflow.alembic.versions.c3e7a1b9d2f4_normalize_legacy_uppercase_span_enum_labels"
)


# ---------------------------------------------------------------------------
# Pure tests (no database required)
# ---------------------------------------------------------------------------


def test_revision_chain_follows_current_head():
    """Migration chains directly on top of the flow:create backfill head."""
    assert _MIGRATION.revision == "c3e7a1b9d2f4"  # pragma: allowlist secret
    assert _MIGRATION.down_revision == "4f0d2c9a8b7e"  # pragma: allowlist secret


def test_relabel_map_matches_span_status_enum():
    """The spanstatus mapping equals {NAME: value} for the live SpanStatus enum."""
    expected = {member.name: member.value for member in SpanStatus}
    assert _MIGRATION._ENUM_RELABELS["spanstatus"] == expected
    # Every entry is a genuine case repair: the uppercase name differs from the value.
    for name, value in expected.items():
        assert name != value, f"SpanStatus.{name} no longer needs relabeling"


def test_relabel_map_matches_span_type_enum():
    """The spantype mapping equals {NAME: value} for the live SpanType enum."""
    expected = {member.name: member.value for member in SpanType}
    assert _MIGRATION._ENUM_RELABELS["spantype"] == expected
    for name, value in expected.items():
        assert name != value, f"SpanType.{name} no longer needs relabeling"


def test_spankind_is_excluded_because_name_equals_value():
    """SpanKind must NOT be relabeled — its labels already match in every creation path."""
    assert "spankind" not in _MIGRATION._ENUM_RELABELS
    # Guard the assumption that justifies the exclusion.
    for member in SpanKind:
        assert member.name == member.value, "SpanKind drifted; it may now need relabeling"


def test_only_known_enum_types_are_touched():
    """No surprise enum types — only spanstatus and spantype are in scope."""
    assert set(_MIGRATION._ENUM_RELABELS) == {"spanstatus", "spantype"}


def test_upgrade_is_noop_on_non_postgres(monkeypatch):
    """Non-PostgreSQL backends have no named enum types, so relabel is never invoked."""
    calls: list = []
    fake_conn = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    monkeypatch.setattr(_MIGRATION.op, "get_bind", lambda: fake_conn)
    monkeypatch.setattr(_MIGRATION, "_rename_labels", lambda *a, **k: calls.append((a, k)))

    _MIGRATION.upgrade()

    assert calls == [], "relabel should not run on non-postgresql dialects"


def test_upgrade_invokes_relabel_on_postgres(monkeypatch):
    """On PostgreSQL the relabel runs against the bound connection with the full map."""
    calls: list = []
    fake_conn = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    monkeypatch.setattr(_MIGRATION.op, "get_bind", lambda: fake_conn)
    monkeypatch.setattr(_MIGRATION, "_rename_labels", lambda conn, relabels: calls.append((conn, relabels)))

    _MIGRATION.upgrade()

    assert len(calls) == 1
    conn, relabels = calls[0]
    assert conn is fake_conn
    assert relabels is _MIGRATION._ENUM_RELABELS


def test_downgrade_is_a_noop():
    """Downgrade is intentionally inert — it must not touch the bind at all."""
    # A no-op downgrade never calls op.get_bind(); calling it directly must not raise.
    assert _MIGRATION.downgrade() is None


# ---------------------------------------------------------------------------
# Functional tests (require a real PostgreSQL database)
# ---------------------------------------------------------------------------


def _sync_pg_url() -> str | None:
    """Return a sync psycopg PostgreSQL URL from the environment, or None."""
    url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url:
        return None
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


@pytest.fixture
def pg_connection():
    """Yield a PostgreSQL connection inside a transaction that is always rolled back.

    All DDL here (CREATE TYPE / ALTER TYPE) is transactional in PostgreSQL, so the
    rollback leaves no residue and tests never collide even on a shared database.
    """
    url = _sync_pg_url()
    if url is None:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
    engine = sa.create_engine(url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def _make_enum(conn, type_name: str, labels: list[str]) -> None:
    quoted = ", ".join(f"'{label}'" for label in labels)
    conn.execute(sa.text(f"CREATE TYPE {type_name} AS ENUM ({quoted})"))


def test_relabel_converts_uppercase_type_to_lowercase(pg_connection):
    """A type created with UPPERCASE labels is relabeled to the canonical lowercase set."""
    type_name = f"relabel_status_{uuid4().hex[:8]}"
    _make_enum(pg_connection, type_name, ["UNSET", "OK", "ERROR"])

    _MIGRATION._rename_labels(pg_connection, {type_name: _MIGRATION._ENUM_RELABELS["spanstatus"]})

    assert _MIGRATION._existing_labels(pg_connection, type_name) == {"unset", "ok", "error"}


def test_relabel_insert_roundtrip_with_savepoints(pg_connection):
    """End-to-end: lowercase insert fails pre-fix, succeeds post-fix (savepoint-isolated)."""
    type_name = f"relabel_rt_{uuid4().hex[:8]}"
    table_name = f"rt_{uuid4().hex[:8]}"
    _make_enum(pg_connection, type_name, ["UNSET", "OK", "ERROR"])
    pg_connection.execute(sa.text(f"CREATE TABLE {table_name} (s {type_name})"))

    # Pre-fix: PostgreSQL rejects the lowercase label inside an isolated savepoint.
    sp = pg_connection.begin_nested()
    with pytest.raises(sa.exc.DBAPIError):
        pg_connection.execute(sa.text(f"INSERT INTO {table_name} (s) VALUES ('ok')"))  # noqa: S608
    sp.rollback()

    # Apply the migration's relabel.
    _MIGRATION._rename_labels(pg_connection, {type_name: _MIGRATION._ENUM_RELABELS["spanstatus"]})

    # Post-fix: the same insert now succeeds and round-trips.
    pg_connection.execute(sa.text(f"INSERT INTO {table_name} (s) VALUES ('ok')"))  # noqa: S608
    stored = pg_connection.execute(sa.text(f"SELECT s FROM {table_name}")).scalar()  # noqa: S608
    assert stored == "ok"


def test_relabel_is_idempotent_on_already_lowercase_type(pg_connection):
    """Running the relabel against an already-correct type changes nothing and never errors."""
    type_name = f"relabel_lower_{uuid4().hex[:8]}"
    _make_enum(pg_connection, type_name, ["unset", "ok", "error"])

    # Run twice — both must be no-ops.
    for _ in range(2):
        _MIGRATION._rename_labels(pg_connection, {type_name: _MIGRATION._ENUM_RELABELS["spanstatus"]})

    assert _MIGRATION._existing_labels(pg_connection, type_name) == {"unset", "ok", "error"}


def test_relabel_skips_absent_type(pg_connection):
    """A mapping for a type that doesn't exist is silently skipped (no error)."""
    missing = f"relabel_missing_{uuid4().hex[:8]}"
    # Should not raise even though the type was never created.
    _MIGRATION._rename_labels(pg_connection, {missing: _MIGRATION._ENUM_RELABELS["spanstatus"]})
    assert _MIGRATION._existing_labels(pg_connection, missing) == set()
