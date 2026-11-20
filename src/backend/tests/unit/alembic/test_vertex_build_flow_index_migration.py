"""Structure tests for the vertex_build flow-scoped read index.

Runs on sqlite and (when configured) postgres.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PREVIOUS_REVISION = "7a4c2e9b6d15"  # pragma: allowlist secret
_INDEX = "ix_vertex_build_flow_id_id_timestamp"
_EXPECTED_COLUMNS = ["flow_id", "id", "timestamp"]
_WITNESS_TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _vertex_build_index_columns(connection) -> dict[str, list[str]]:
    return {
        index["name"]: list(index["column_names"])
        for index in inspect(connection).get_indexes("vertex_build")
        if index["name"] == _INDEX
    }


def _insert_witness(connection) -> None:
    build_id = uuid.uuid4()
    flow_id = uuid.uuid4()
    is_postgres = connection.dialect.name == "postgresql"
    connection.execute(
        text(
            "INSERT INTO vertex_build (build_id, timestamp, id, valid, flow_id)"
            " VALUES (:build_id, :timestamp, 'witness-vertex', :valid, :flow_id)"
        ),
        {
            "build_id": str(build_id) if is_postgres else build_id.hex,
            "flow_id": str(flow_id) if is_postgres else flow_id.hex,
            # PostgreSQL stores this column as timestamptz and takes the aware
            # value as it is. SQLite has no timezone type, so it gets the same
            # instant as naive UTC.
            "timestamp": _WITNESS_TIMESTAMP if is_postgres else _WITNESS_TIMESTAMP.replace(tzinfo=None),
            "valid": True,
        },
    )


def _witness_count(connection) -> int:
    return connection.execute(text("SELECT count(*) FROM vertex_build WHERE id = 'witness-vertex'")).scalar_one()


def test_vertex_build_metadata_index():
    """The ORM metadata must declare the index the migration creates."""
    indexes = {index.name: index for index in VertexBuildTable.__table__.indexes}
    assert _INDEX in indexes
    assert [column.name for column in indexes[_INDEX].columns] == _EXPECTED_COLUMNS
    assert not indexes[_INDEX].unique


def test_vertex_build_index_exists_at_head(db_url):  # noqa: F811
    """The flow-scoped read path must be indexed on the columns it filters and sorts by."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert _vertex_build_index_columns(connection) == {_INDEX: _EXPECTED_COLUMNS}
    finally:
        engine.dispose()


def test_vertex_build_index_upgrade_is_idempotent(db_url):  # noqa: F811
    """Re-running the upgrade over an existing index must not fail."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")
    # Rewind only the version stamp, leaving the index present so upgrade
    # actually runs again and exercises its existing-index guard.
    command.stamp(alembic_cfg, _PREVIOUS_REVISION)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert _vertex_build_index_columns(connection) == {_INDEX: _EXPECTED_COLUMNS}
    finally:
        engine.dispose()


def test_vertex_build_index_roundtrip_preserves_rows(db_url):  # noqa: F811
    """Downgrading and re-upgrading must only add and drop the index, never rows."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            _insert_witness(connection)

        command.downgrade(alembic_cfg, _PREVIOUS_REVISION)
        with engine.connect() as connection:
            assert _vertex_build_index_columns(connection) == {}
            assert _witness_count(connection) == 1

        command.upgrade(alembic_cfg, "head")
        with engine.connect() as connection:
            assert _vertex_build_index_columns(connection) == {_INDEX: _EXPECTED_COLUMNS}
            assert _witness_count(connection) == 1
    finally:
        engine.dispose()


def test_vertex_build_index_recovers_failed_concurrent_build(db_url):  # noqa: F811
    """A failed concurrent build must be replaced by a valid read-path index."""
    if not db_url.startswith("postgresql"):
        pytest.skip("Only PostgreSQL leaves invalid indexes after concurrent builds")
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(_engine_url(db_url), isolation_level="AUTOCOMMIT")
    validity = text(
        f"SELECT indisvalid FROM pg_index WHERE indexrelid = '{_INDEX}'::regclass"  # noqa: S608
    )
    try:
        with engine.connect() as connection:
            _insert_witness(connection)
            _insert_witness(connection)
            connection.execute(text("DROP INDEX CONCURRENTLY ix_vertex_build_flow_id_id_timestamp"))
            # The two witness rows share a vertex id, so this real concurrent
            # build fails and leaves the same unusable index state as an
            # interrupted build.
            with pytest.raises(IntegrityError):
                connection.execute(
                    text("CREATE UNIQUE INDEX CONCURRENTLY ix_vertex_build_flow_id_id_timestamp ON vertex_build (id)")
                )
            assert connection.execute(validity).scalar_one() is False

        command.stamp(alembic_cfg, _PREVIOUS_REVISION)
        command.upgrade(alembic_cfg, "head")
        with engine.connect() as connection:
            assert _vertex_build_index_columns(connection) == {_INDEX: _EXPECTED_COLUMNS}
            assert connection.execute(validity).scalar_one() is True
            assert _witness_count(connection) == 2
    finally:
        engine.dispose()


def test_vertex_build_index_downgrade_is_idempotent(db_url):  # noqa: F811
    """Downgrading when the index is already absent must not fail."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, _PREVIOUS_REVISION)
    # Stamp forward again without recreating the index, so downgrade runs a
    # second time against a table that no longer carries it.
    command.stamp(alembic_cfg, "head")
    command.downgrade(alembic_cfg, _PREVIOUS_REVISION)

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert _vertex_build_index_columns(connection) == {}
    finally:
        engine.dispose()
