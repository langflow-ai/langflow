"""Tests for the skipped authorization-audit result expansion."""

from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.cp03a2b3c4d5_allow_skipped_authz_audit_results")

_CONSTRAINT_NAME = "ck_authz_audit_log_result_enum"
_NAMING_CONVENTION = {"ck": "ck_%(table_name)s_%(constraint_name)s"}
_RENDERED_CONSTRAINT_NAME = f"ck_authz_audit_log_{_CONSTRAINT_NAME}"


def _make_engine(naming_convention):
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData(naming_convention=naming_convention)
    sa.Table(
        "authz_audit_log",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.CheckConstraint(
            "result IN ('allow', 'deny', 'owner_override')",
            name=_CONSTRAINT_NAME,
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


@pytest.mark.parametrize(
    ("naming_convention", "expected_constraint_name"),
    [
        pytest.param(None, _CONSTRAINT_NAME, id="literal-name"),
        pytest.param(_NAMING_CONVENTION, _RENDERED_CONSTRAINT_NAME, id="langflow-convention"),
    ],
)
def test_upgrade_allows_skip_without_weakening_other_result_validation(naming_convention, expected_constraint_name):
    engine = _make_engine(naming_convention)
    audit_log = sa.table("authz_audit_log", sa.column("result", sa.String()))

    _run_upgrade(engine)
    _run_upgrade(engine)

    with engine.begin() as conn:
        conn.execute(sa.insert(audit_log).values(result="skip"))

    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.insert(audit_log).values(result="unexpected"))

    result_checks = [
        check
        for check in sa.inspect(engine).get_check_constraints("authz_audit_log")
        if "result IN" in (check.get("sqltext") or "")
    ]
    assert len(result_checks) == 1
    result_check = result_checks[0]
    assert result_check["name"] == expected_constraint_name
    assert "'skip'" in result_check["sqltext"]

    _MIGRATION.downgrade()
    with engine.begin() as conn:
        conn.execute(sa.insert(audit_log).values(result="skip"))


def test_upgrade_reuses_convention_rendered_constraint_name(monkeypatch):
    class FakeBatchOperations:
        def __init__(self):
            self.dropped = []
            self.created = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def f(self, name):
            return f"fixed:{name}"

        def drop_constraint(self, name, *, type_):
            self.dropped.append((name, type_))

        def create_check_constraint(self, name, condition):
            self.created.append((name, condition))

    class FakeOperations:
        def __init__(self, batch):
            self.batch = batch

        def get_bind(self):
            return object()

        def batch_alter_table(self, table_name, *, schema):
            assert table_name == "authz_audit_log"
            assert schema is None
            return self.batch

    checks = [
        {
            "name": _RENDERED_CONSTRAINT_NAME,
            "sqltext": "result IN ('allow', 'deny', 'owner_override')",
        }
    ]
    inspector = type("Inspector", (), {"get_check_constraints": lambda _self, _table: checks})()
    batch = FakeBatchOperations()
    monkeypatch.setattr(_MIGRATION.sa, "inspect", lambda _conn: inspector)
    monkeypatch.setattr(_MIGRATION, "op", FakeOperations(batch))

    _MIGRATION.upgrade()

    fixed_name = f"fixed:{_RENDERED_CONSTRAINT_NAME}"
    assert batch.dropped == [(fixed_name, "check")]
    assert batch.created == [(fixed_name, _MIGRATION._RESULT_CHECK)]


def test_migration_follows_role_grant_backfill():
    assert _MIGRATION.down_revision == "cp02a2b3c4d5"
