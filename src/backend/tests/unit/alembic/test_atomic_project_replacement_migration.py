from uuid import uuid4

import pytest
from alembic import command
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "e6f9a2b4c8d1"  # pragma: allowlist secret -- migration revision identifier
_REVISION = "f194a1b2c3d4"  # pragma: allowlist secret -- migration revision identifier
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
                "INSERT INTO flow (id, name, folder_id, user_id) VALUES (:id, :name, :folder_id, :user_id)",
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


def test_postgres_replacement_retries_flow_project_lock_inversion(db_url, monkeypatch):  # noqa: F811
    """Retry an actual deadlock against the migration's shared Folder trigger."""
    if not db_url.startswith("postgresql"):
        pytest.skip("PostgreSQL detects this row-lock cycle")

    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from langflow.api.v1 import projects
    from langflow.api.v1.schemas.replacement_operations import ProjectReplacementRequest
    from langflow.services.database.models.user.model import User
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    command.upgrade(_make_alembic_cfg(db_url), _REVISION)
    engine = create_engine(_engine_url(db_url))
    owner_id, project_id, flow_id = (uuid4() for _ in range(3))
    flow_locked, folder_locked = Event(), Event()
    attempts = 0
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "user" '
                    "(id, username, password, is_active, is_superuser, create_at, updated_at) "
                    "VALUES (:id, :username, 'test', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": owner_id, "username": f"retry-{owner_id}"},
            )
            connection.execute(
                text(
                    "INSERT INTO folder (id, name, description, user_id) VALUES (:id, 'retry-project', 'old', :owner)"
                ),
                {"id": project_id, "owner": owner_id},
            )
            connection.execute(
                text("INSERT INTO flow (id, name, folder_id, user_id) VALUES (:id, 'retry-flow', :folder, :owner)"),
                {"id": flow_id, "folder": project_id, "owner": owner_id},
            )

        def ordinary_edit():
            with engine.begin() as connection:
                connection.execute(text("SET LOCAL deadlock_timeout = '5s'"))
                connection.execute(text("SET LOCAL statement_timeout = '10s'"))
                connection.execute(text("SELECT id FROM flow WHERE id = :id FOR UPDATE"), {"id": flow_id})
                flow_locked.set()
                assert folder_locked.wait(timeout=10)
                # The migration trigger now waits for the replacement's Folder lock.
                connection.execute(
                    text("UPDATE flow SET description = 'ordinary edit' WHERE id = :id"), {"id": flow_id}
                )

        async def replacement_attempt(*, session, **_kwargs):
            nonlocal attempts
            attempts += 1
            await session.execute(text("SET LOCAL deadlock_timeout = '50ms'"))
            await session.execute(text("SET LOCAL statement_timeout = '10s'"))
            await session.execute(text("SELECT id FROM folder WHERE id = :id FOR UPDATE"), {"id": project_id})
            prior = (
                await session.execute(text("SELECT description FROM folder WHERE id = :id"), {"id": project_id})
            ).scalar_one()
            assert prior == "old", "the aborted attempt must roll back its project mutation"
            await session.execute(
                text("UPDATE folder SET description = 'replacement' WHERE id = :id"), {"id": project_id}
            )
            folder_locked.set()
            # First attempt waits for ordinary_edit's Flow lock: a real cycle.
            await session.execute(text("UPDATE flow SET description = 'replacement' WHERE id = :id"), {"id": flow_id})
            await session.commit()
            return "committed"

        monkeypatch.setattr(projects, "_replace_project_operation_once", replacement_attempt)

        async def run_replacement():
            async_engine = create_async_engine(db_url)
            try:
                async with AsyncSession(async_engine, expire_on_commit=False) as session:
                    return await projects.replace_project_operation(
                        session=session,
                        project_id=project_id,
                        operation_id=uuid4(),
                        request_body=ProjectReplacementRequest(description="replacement", flows=[]),
                        current_user=User(id=owner_id, username="retry-user", password=uuid4().hex),
                        storage_service=None,
                    )
            finally:
                await async_engine.dispose()

        with ThreadPoolExecutor(max_workers=1) as pool:
            edit = pool.submit(ordinary_edit)
            assert flow_locked.wait(timeout=10)
            assert asyncio.run(run_replacement()) == "committed"
            edit.result(timeout=10)
        assert attempts == 2
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT description FROM folder WHERE id = :id"), {"id": project_id}
                ).scalar_one()
                == "replacement"
            )
            assert (
                connection.execute(text("SELECT description FROM flow WHERE id = :id"), {"id": flow_id}).scalar_one()
                == "replacement"
            )
    finally:
        folder_locked.set()
        engine.dispose()
