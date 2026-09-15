"""Portable migration coverage for the native team-sharing contract."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import (
    _create_pg_test_database,
    _drop_pg_test_database,
    _engine_url,
    _make_alembic_cfg,
)

_PRIOR_REVISION = "c6d8e0f2a4b7"  # pragma: allowlist secret
_REVISION = "bf6c22022777"  # pragma: allowlist secret


@pytest.fixture
def authz_database_url(tmp_path) -> str:
    raw = os.getenv("LANGFLOW_AUTHZ_TEST_DATABASE_URI")
    if raw is None:
        return f"sqlite+aiosqlite:///{tmp_path / 'authz-migration.db'}"
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    return raw


def _constraint_names(inspector, table_name: str) -> set[str]:
    return {str(item["name"]) for item in inspector.get_check_constraints(table_name)}


@pytest.fixture
def merge_database_url(authz_database_url, tmp_path):
    if authz_database_url.startswith("postgresql"):
        name = f"authz_merge_{uuid4().hex}"
        try:
            yield _create_pg_test_database(authz_database_url, name)
        finally:
            _drop_pg_test_database(authz_database_url, name)
    else:
        yield f"sqlite+aiosqlite:///{tmp_path / 'merge.db'}"


@pytest.mark.parametrize("starting_revision", [_REVISION, "d7e9f1a3b5c8", "e8a9b0c1d2f3", "b4c7d2e8f1a3"])
def test_upstream_merge_upgrades_both_existing_heads(merge_database_url, starting_revision):
    """Both released branches converge without losing existing canonical team rows."""
    config = _make_alembic_cfg(merge_database_url)
    command.upgrade(config, starting_revision)
    team_id = str(uuid4())
    engine = create_engine(_engine_url(merge_database_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO authz_team "
                    "(id, team_name, adom_name, is_active, created_at, updated_at) "
                    "VALUES (:id, :name, :name, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": team_id, "name": f"merge-{team_id}"},
            )
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert "is_environment_managed" in {c["name"] for c in inspector.get_columns("variable")}
        assert "role" in {c["name"] for c in inspector.get_columns("authz_team_member")}
        assert {"connection", "authz_team_member_grant"} <= set(inspector.get_table_names())
        assert "revision" in {c["name"] for c in inspector.get_columns("authz_share")}
        for table in ("flow", "folder"):
            assert "edit_revision" in {c["name"] for c in inspector.get_columns(table)}
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == [
                "f2a4c6e8b0d1"
            ]
            assert (
                connection.execute(
                    text("SELECT team_name FROM authz_team WHERE id = :id"), {"id": team_id}
                ).scalar_one()
                == f"merge-{team_id}"
            )
    finally:
        engine.dispose()


def test_team_sharing_migration_backfills_and_round_trips(authz_database_url: str):
    """Upgrade seeded legacy data, verify schema parity, and prove downgrade safety."""
    alembic_cfg = _make_alembic_cfg(authz_database_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    team_id = str(uuid4())
    engine = create_engine(_engine_url(authz_database_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO authz_team "
                    "(id, team_name, adom_name, description, is_active, created_at, updated_at) "
                    "VALUES (:id, :team_name, :adom_name, NULL, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "id": team_id,
                    "team_name": f"legacy-{team_id}",
                    "adom_name": f"legacy-{team_id}",
                },
            )

        command.upgrade(alembic_cfg, _REVISION)
        inspector = inspect(engine)
        assert "inactivation_reason" in {column["name"] for column in inspector.get_columns("authz_team")}
        assert {"role", "updated_at"} <= {column["name"] for column in inspector.get_columns("authz_team_member")}
        assert {"revision", "updated_at"} <= {column["name"] for column in inspector.get_columns("authz_share")}
        assert "edit_revision" in {column["name"] for column in inspector.get_columns("flow")}
        assert "edit_revision" in {column["name"] for column in inspector.get_columns("folder")}
        assert any(
            name.endswith("ck_authz_team_inactivation_reason") for name in _constraint_names(inspector, "authz_team")
        )
        assert any(
            name.endswith("ck_authz_team_member_role") for name in _constraint_names(inspector, "authz_team_member")
        )
        assert any(
            name.endswith("ck_authz_share_revision_positive") for name in _constraint_names(inspector, "authz_share")
        )
        assert "ix_authz_team_member_team_role" in {
            index["name"] for index in inspector.get_indexes("authz_team_member")
        }
        with engine.connect() as connection:
            reason = connection.execute(
                text("SELECT inactivation_reason FROM authz_team WHERE id = :id"), {"id": team_id}
            ).scalar_one()
        assert reason == "manual"

        command.downgrade(alembic_cfg, _PRIOR_REVISION)
        inspector = inspect(engine)
        assert "inactivation_reason" not in {column["name"] for column in inspector.get_columns("authz_team")}
        assert "role" not in {column["name"] for column in inspector.get_columns("authz_team_member")}
        assert "revision" not in {column["name"] for column in inspector.get_columns("authz_share")}

        # Leave a reusable CI database at the candidate head for the real
        # service tests that run after this migration check. The deliberately
        # invalid legacy fixture must survive the round trip, but it must not
        # leak into those readiness tests: production requires operators to
        # repair or retire such teams before collaboration becomes ready.
        command.upgrade(alembic_cfg, "head")
        with engine.begin() as connection:
            deleted = connection.execute(text("DELETE FROM authz_team WHERE id = :id"), {"id": team_id})
            assert deleted.rowcount == 1
    finally:
        engine.dispose()
