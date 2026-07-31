"""Tests for the skipped authorization-audit result expansion."""

from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.cp03a2b3c4d5_allow_skipped_authz_audit_results")


def _make_engine():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "authz_audit_log",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.CheckConstraint(
            "result IN ('allow', 'deny', 'owner_override')",
            name="ck_authz_audit_log_result_enum",
        ),
    )
    metadata.create_all(engine)
    return engine


def _run_upgrade(engine) -> None:
    with engine.begin() as conn:
        original_op = _MIGRATION.op
        try:
            _MIGRATION.op = Operations(MigrationContext.configure(conn))
            _MIGRATION.upgrade()
        finally:
            _MIGRATION.op = original_op


def test_upgrade_allows_skip_without_weakening_other_result_validation():
    engine = _make_engine()
    audit_log = sa.table("authz_audit_log", sa.column("result", sa.String()))

    _run_upgrade(engine)
    _run_upgrade(engine)

    with engine.begin() as conn:
        conn.execute(sa.insert(audit_log).values(result="skip"))

    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.insert(audit_log).values(result="unexpected"))

    checks = sa.inspect(engine).get_check_constraints("authz_audit_log")
    result_check = next(check for check in checks if check["name"] == "ck_authz_audit_log_result_enum")
    assert "'skip'" in result_check["sqltext"]

    _MIGRATION.downgrade()
    with engine.begin() as conn:
        conn.execute(sa.insert(audit_log).values(result="skip"))


def test_migration_follows_role_grant_backfill():
    assert _MIGRATION.down_revision == "cp02a2b3c4d5"
