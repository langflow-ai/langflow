from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "e6f9a2b4c8d1"
_REVISION = "f194a1b2c3d4"
_TRIGGER = "trg_flow_lock_project_for_mutation"


def test_migration_accepts_metadata_created_receipt_table_and_installs_guard(db_url):  # noqa: F811
    """Fresh metadata creates the receipt table before Alembic installs the PG guard."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            ProjectReplacementOperation.__table__.create(connection, checkfirst=True)

        command.upgrade(config, _REVISION)

        with engine.connect() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("project_replacement_operation")}
            assert {
                "project_id",
                "operation_id",
                "request_digest",
                "result",
                "project_user_id",
                "workspace_id",
                "created_at",
            } <= columns
            if connection.dialect.name == "postgresql":
                installed = connection.execute(
                    text(
                        "SELECT 1 FROM pg_trigger WHERE tgname = :trigger_name "
                        "AND tgrelid = 'flow'::regclass AND NOT tgisinternal"
                    ),
                    {"trigger_name": _TRIGGER},
                ).first()
                assert installed is not None
    finally:
        engine.dispose()


def test_postgres_flow_dml_waits_for_replacement_project_lock(db_url):  # noqa: F811
    """Flow DML takes the same Folder row lock as an atomic replacement."""
    if not db_url.startswith("postgresql"):
        pytest.skip("the shared flow write trigger only exists on PostgreSQL")

    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _REVISION)

    engine = create_engine(_engine_url(db_url))
    owner_id, project_id, original_flow_id, inserted_flow_id = (uuid4() for _ in range(4))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "user" '
                    "(id, username, password, is_active, is_superuser, create_at, updated_at) "
                    "VALUES (:id, :username, 'test', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": owner_id, "username": f"lock-test-{owner_id}"},
            )
            connection.execute(
                text("INSERT INTO folder (id, name, user_id) VALUES (:id, :name, :user_id)"),
                {"id": project_id, "name": f"lock-test-{project_id}", "user_id": owner_id},
            )
            connection.execute(
                text("INSERT INTO flow (id, name, folder_id, user_id) VALUES (:id, :name, :folder_id, :user_id)"),
                {
                    "id": original_flow_id,
                    "name": "original-flow",
                    "folder_id": project_id,
                    "user_id": owner_id,
                },
            )

        mutations = [
            (
                "INSERT INTO flow (id, name, folder_id, user_id) "
                "VALUES (:id, :name, :folder_id, :user_id)",
                {
                    "id": inserted_flow_id,
                    "name": "inserted-flow",
                    "folder_id": project_id,
                    "user_id": owner_id,
                },
            ),
            (
                "UPDATE flow SET description = 'updated' WHERE id = :id",
                {"id": original_flow_id},
            ),
            ("DELETE FROM flow WHERE id = :id", {"id": original_flow_id}),
        ]

        lock_connection = engine.connect()
        lock_transaction = lock_connection.begin()
        try:
            lock_connection.execute(
                text("SELECT id FROM folder WHERE id = :project_id FOR UPDATE"),
                {"project_id": project_id},
            )
            for statement, parameters in mutations:
                with engine.connect() as worker:
                    worker_transaction = worker.begin()
                    try:
                        worker.execute(text("SET LOCAL lock_timeout = '250ms'"))
                        with pytest.raises(DBAPIError) as error:
                            worker.execute(text(statement), parameters)
                        assert getattr(error.value.orig, "sqlstate", None) == "55P03"
                    finally:
                        worker_transaction.rollback()
        finally:
            lock_transaction.rollback()
            lock_connection.close()

        for statement, parameters in mutations:
            with engine.begin() as connection:
                connection.execute(text(statement), parameters)

        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT id, description FROM flow WHERE folder_id = :project_id"),
                {"project_id": project_id},
            ).all()
            assert rows == [(inserted_flow_id, None)]
    finally:
        engine.dispose()
