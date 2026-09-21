"""Constraint-name parity for the ``flow_version`` ``version_number >= 1`` CHECK.

The model marks the name with ``conv()`` and the migration with ``op.f()`` so both create paths
render ``ck_flow_version_version_number_positive`` under the ``ck_%(table_name)s_%(constraint_name)s``
convention that ``langflow/alembic/env.py`` installs. Databases created before that fix carry a
legacy name and must be left untouched.
"""

from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.services.database.models.flow_version.model import VERSION_NUMBER_CHECK_NAME, FlowVersion

from .test_migration_execution import _engine_url, db_url  # noqa: F401

_MIGRATION = importlib.import_module("langflow.alembic.versions.7d327cfafab6_add_flow_history_table")
TABLE_NAME = "flow_version"
# Mirrors NAMING_CONVENTION in ``langflow/alembic/env.py`` (env.py cannot be imported: it runs migrations on import).
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
# Fresh installs created the table via create_all before env.py installed the convention.
_LEGACY_PLAIN_NAME = "check_version_number_positive"
# Upgraded installs created it via op.create_table, which prefixed the plain string.
_LEGACY_DOUBLED_NAME = f"ck_{TABLE_NAME}_{_LEGACY_PLAIN_NAME}"


def _convention_operations(connection: sa.Connection) -> Operations:
    """Build Operations the way env.py does: create_table inherits the naming convention."""
    return Operations(
        MigrationContext.configure(
            connection,
            opts={"target_metadata": sa.MetaData(naming_convention=_NAMING_CONVENTION)},
        )
    )


def _scratch_metadata(*, under_convention: bool) -> sa.MetaData:
    """Return a MetaData holding stub ``user`` and ``flow`` tables so flow_version's foreign keys resolve."""
    metadata = sa.MetaData(naming_convention=_NAMING_CONVENTION) if under_convention else sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("flow", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    return metadata


def _pre_fix_flow_version_table(metadata: sa.MetaData) -> sa.Table:
    """Rebuild flow_version as the pre-fix model and migration declared it: a plain-string CHECK name."""
    return sa.Table(
        TABLE_NAME,
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("flow_id", sa.Uuid(), sa.ForeignKey("flow.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("flow_id", "version_number", name="unique_flow_version_number"),
        sa.CheckConstraint("version_number >= 1", name=_LEGACY_PLAIN_NAME),
    )


def _reflected_check_names(connection: sa.Connection) -> set[str]:
    return {constraint["name"] for constraint in sa.inspect(connection).get_check_constraints(TABLE_NAME)}


@pytest.mark.parametrize("create_path", ["migration", "model_without_convention", "model_under_convention"])
def test_flow_version_check_name_is_identical_across_create_paths(db_url, create_path, monkeypatch):  # noqa: F811
    """Every way the table gets created must emit the one canonical CHECK name."""
    engine = sa.create_engine(_engine_url(db_url))
    try:
        if create_path == "migration":
            _scratch_metadata(under_convention=False).create_all(engine)
            with engine.begin() as connection:
                monkeypatch.setattr(_MIGRATION, "op", _convention_operations(connection))
                _MIGRATION.upgrade()
        else:
            metadata = _scratch_metadata(under_convention=create_path == "model_under_convention")
            FlowVersion.__table__.to_metadata(metadata)
            metadata.create_all(engine)

        with engine.connect() as connection:
            assert _reflected_check_names(connection) == {VERSION_NUMBER_CHECK_NAME}
    finally:
        engine.dispose()


@pytest.mark.parametrize("legacy_name", [_LEGACY_PLAIN_NAME, _LEGACY_DOUBLED_NAME])
def test_migration_leaves_legacy_check_names_untouched(db_url, legacy_name, monkeypatch):  # noqa: F811
    """Existing databases keep whichever legacy name they were created with; nothing renames or duplicates it."""
    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = _scratch_metadata(under_convention=legacy_name == _LEGACY_DOUBLED_NAME)
        _pre_fix_flow_version_table(metadata)
        metadata.create_all(engine)

        with engine.begin() as connection:
            assert _reflected_check_names(connection) == {legacy_name}

            monkeypatch.setattr(_MIGRATION, "op", _convention_operations(connection))
            _MIGRATION.upgrade()
            _MIGRATION.upgrade()

            assert _reflected_check_names(connection) == {legacy_name}
    finally:
        engine.dispose()
