"""The flow history migration and the append-only triggers it installs."""

from __future__ import annotations

from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_operation.append_only import (
    DELETE_TRIGGER,
    MAINTENANCE_SETTING,
    TRUNCATE_TRIGGER,
    UPDATE_TRIGGER,
)
from langflow.services.database.models.user.model import User
from langflow.services.database.service import SQLModel
from sqlmodel import Session

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

HISTORY_REVISION = "e3a7b9c1d5f2"  # pragma: allowlist secret
PREVIOUS_REVISION = "d4f1a6c8e2b7"  # pragma: allowlist secret


@pytest.fixture
def engine(db_url):  # noqa: F811
    engine = sa.create_engine(_engine_url(db_url))
    try:
        yield engine
    finally:
        engine.dispose()


def _trigger_names(engine: sa.Engine) -> set[str]:
    with engine.connect() as conn:
        if conn.dialect.name == "sqlite":
            rows = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type = 'trigger'"))
        else:
            rows = conn.execute(
                sa.text("SELECT tgname FROM pg_trigger WHERE tgrelid = 'flow_operation'::regclass AND NOT tgisinternal")
            )
        return {row[0] for row in rows}


def _expected_triggers(engine: sa.Engine) -> set[str]:
    if engine.dialect.name == "sqlite":
        return {UPDATE_TRIGGER, DELETE_TRIGGER}
    return {UPDATE_TRIGGER, DELETE_TRIGGER, TRUNCATE_TRIGGER}


def _flow_with_history(engine: sa.Engine):
    with Session(engine) as session:
        user = User(username=f"history-{uuid4().hex[:8]}", password="hashed-test-value")  # noqa: S106
        session.add(user)
        session.flush()
        flow = Flow.model_validate({"name": "history", "user_id": user.id, "data": {"nodes": [], "edges": []}})
        session.add(flow)
        session.flush()
        row = FlowOperation(
            flow_id=flow.id,
            start_revision=1,
            end_revision=1,
            ops={"version": 1, "operations": []},
            actor_user_ids=[str(user.id)],
            request_ids=[str(uuid4())],
        )
        session.add(row)
        session.commit()
        return flow.id, row.id


def test_upgrade_installs_the_append_only_triggers(db_url, engine):  # noqa: F811
    command.upgrade(_make_alembic_cfg(db_url), "head")

    assert _expected_triggers(engine) <= _trigger_names(engine)
    columns = {column["name"] for column in sa.inspect(engine).get_columns("flow")}
    assert {"latest_revision", "current_revision"} <= columns


def test_upgrade_over_tables_created_from_the_models(db_url, engine):  # noqa: F811
    # Langflow creates missing tables from the models before running migrations,
    # so every migration, including older ones that rebuild ``flow`` on SQLite,
    # runs with the triggers already in place.
    SQLModel.metadata.create_all(engine)

    command.upgrade(_make_alembic_cfg(db_url), "head")

    assert _expected_triggers(engine) <= _trigger_names(engine)


def test_the_triggers_refuse_updates_and_deletes_of_rows_whose_flow_exists(db_url, engine):  # noqa: F811
    command.upgrade(_make_alembic_cfg(db_url), "head")
    _, row_id = _flow_with_history(engine)
    row_filter = sa.bindparam("id", value=row_id, type_=sa.Uuid())

    for statement in (
        sa.text("UPDATE flow_operation SET end_revision = 2 WHERE id = :id").bindparams(row_filter),
        sa.text("DELETE FROM flow_operation WHERE id = :id").bindparams(row_filter),
    ):
        with engine.begin() as conn, pytest.raises(sa.exc.DatabaseError, match="flow_operation rows"):
            conn.execute(statement)

    if engine.dialect.name == "postgresql":
        with engine.begin() as conn, pytest.raises(sa.exc.DatabaseError, match="append-only"):
            conn.execute(sa.text("TRUNCATE flow_operation"))


def test_deleting_the_flow_on_postgresql_cascades_through_the_trigger(db_url, engine):  # noqa: F811
    if engine.dialect.name != "postgresql":
        pytest.skip("SQLite runs without foreign keys; cascade_delete_flow removes the rows")
    command.upgrade(_make_alembic_cfg(db_url), "head")
    flow_id, _ = _flow_with_history(engine)

    with engine.begin() as conn:
        conn.execute(
            sa.text("DELETE FROM flow WHERE id = :id").bindparams(sa.bindparam("id", flow_id, type_=sa.Uuid()))
        )

    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM flow_operation")).scalar() == 0


def test_rebuilding_the_flow_table_on_sqlite_keeps_working(db_url, engine):  # noqa: F811
    # Future migrations rebuild ``flow`` with batch_alter_table. SQLite re-checks
    # every trigger that names a table while it is rebuilt, so the history
    # triggers must not name ``flow``.
    if engine.dialect.name != "sqlite":
        pytest.skip("only SQLite rebuilds tables to alter them")
    command.upgrade(_make_alembic_cfg(db_url), "head")
    _flow_with_history(engine)

    with engine.begin() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with operations.batch_alter_table("flow", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("rebuild_probe", sa.Integer(), nullable=True))

    assert _expected_triggers(engine) <= _trigger_names(engine)


def test_downgrade_drops_history_and_system_checkpoints_but_keeps_saved_versions(db_url, engine):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, "head")
    flow_id, _ = _flow_with_history(engine)
    flow_param = sa.bindparam("flow_id", flow_id, type_=sa.Uuid())
    with engine.begin() as conn:
        for version_number in (1, None):
            conn.execute(
                sa.text(
                    "INSERT INTO flow_version (id, flow_id, data, version_number, created_at, view_only) "
                    "VALUES (:id, :flow_id, '{}', :version_number, CURRENT_TIMESTAMP, false)"
                ).bindparams(sa.bindparam("id", uuid4(), type_=sa.Uuid()), flow_param, version_number=version_number)
            )

    command.downgrade(config, PREVIOUS_REVISION)

    inspector = sa.inspect(engine)
    assert "flow_operation" not in inspector.get_table_names()
    assert "latest_revision" not in {column["name"] for column in inspector.get_columns("flow")}
    version_number = next(c for c in inspector.get_columns("flow_version") if c["name"] == "version_number")
    assert version_number["nullable"] is False
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_number FROM flow_version")).scalars().all() == [1]

    command.upgrade(config, HISTORY_REVISION)
    assert _expected_triggers(engine) <= _trigger_names(engine)


def test_history_maintenance_may_delete_rows_of_a_flow_that_still_exists(db_url, engine):  # noqa: F811
    # Compaction deletes old rows while the flow lives on. It marks its own
    # transaction instead of disabling the trigger, which would lock the table
    # against every flow's history.
    if engine.dialect.name != "postgresql":
        pytest.skip("SQLite lifts its trigger inside the deleting transaction instead")
    command.upgrade(_make_alembic_cfg(db_url), "head")
    _, row_id = _flow_with_history(engine)
    delete = sa.text("DELETE FROM flow_operation WHERE id = :id").bindparams(
        sa.bindparam("id", value=row_id, type_=sa.Uuid())
    )

    with engine.begin() as conn:
        conn.execute(sa.text(f"SET LOCAL {MAINTENANCE_SETTING} = 'on'"))
        assert conn.execute(delete).rowcount == 1
    with engine.connect() as conn:
        assert conn.execute(sa.text(f"SELECT current_setting('{MAINTENANCE_SETTING}', true)")).scalar() in (None, "")
