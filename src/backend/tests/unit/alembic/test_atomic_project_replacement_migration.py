from uuid import uuid4

import pytest
from alembic import command
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from sqlalchemy import create_engine, insert, inspect, text
from sqlalchemy.exc import OperationalError

from .test_migration_execution import (  # noqa: F401
    _create_pg_test_database,
    _drop_pg_test_database,
    _engine_url,
    _make_alembic_cfg,
    _pg_url,
    db_url,
)

_PRIOR_REVISION = "f9d3b7a5c201"  # pragma: allowlist secret -- migration revision identifier
_REVISION = "f194a1b2c3d4"  # pragma: allowlist secret -- migration revision identifier

# Must match _lock_replacement_operation's pg_advisory_xact_lock call in api/v1/projects.py.
_REPLACEMENT_LOCK_SALT = 1944042026


def test_migration_accepts_metadata_created_receipt_table(db_url):  # noqa: F811
    """Fresh metadata creates the receipt table before Alembic runs against it."""
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
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# PostgreSQL-only lock-ordering coverage
#
# _replace_project_operation_once (api/v1/projects.py) acquires, in order: an
# advisory lock keyed on the project id, then FOR UPDATE on the project's
# Folder row, then FOR UPDATE on its existing Flow rows (ordered by id). These
# tests hold that same lock sequence open on one connection and probe from a
# second. SQLite has no row-level locking or advisory locks, so there is
# nothing to gate for it: these are skipped unless LANGFLOW_TEST_DATABASE_URI
# points at a real PostgreSQL instance, following db_url's own skip pattern.
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_engine():
    """A sync engine on a fresh PostgreSQL database migrated to head, or a skip."""
    base_url = _pg_url()
    if base_url is None:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
    db_name = f"lf_lock_test_{uuid4().hex[:10]}"
    test_url = _create_pg_test_database(base_url, db_name)
    command.upgrade(_make_alembic_cfg(test_url), "head")
    engine = create_engine(_engine_url(test_url))
    try:
        yield engine
    finally:
        engine.dispose()
        _drop_pg_test_database(base_url, db_name)


def _seed_two_projects(engine) -> dict[str, object]:
    """One project with a flow (the one under lock), and an unrelated project+flow."""
    ids = {
        "project_id": uuid4(),
        "flow_id": uuid4(),
        "other_project_id": uuid4(),
        "other_flow_id": uuid4(),
    }
    with engine.begin() as connection:
        connection.execute(insert(Folder.__table__).values(id=ids["project_id"], name=f"locked-{ids['project_id']}"))
        connection.execute(insert(Flow.__table__).values(id=ids["flow_id"], name="flow", folder_id=ids["project_id"]))
        connection.execute(
            insert(Folder.__table__).values(id=ids["other_project_id"], name=f"other-{ids['other_project_id']}")
        )
        connection.execute(
            insert(Flow.__table__).values(id=ids["other_flow_id"], name="other-flow", folder_id=ids["other_project_id"])
        )
    return ids


def _acquire_replacement_locks(connection, project_id) -> None:
    """Mirror _lock_replacement_operation plus the Folder/Flow FOR UPDATE loads."""
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, :salt))"),
        {"lock_key": f"project-replacement:{project_id}", "salt": _REPLACEMENT_LOCK_SALT},
    )
    connection.execute(text("SELECT id FROM folder WHERE id = :id FOR UPDATE"), {"id": str(project_id)})
    connection.execute(
        text("SELECT id FROM flow WHERE folder_id = :id ORDER BY id FOR UPDATE"), {"id": str(project_id)}
    )


def test_replacement_locks_block_conflicting_writes_but_not_a_different_project(pg_engine):
    """While the replacement lock sequence is held: in-project writes block and time out; others do not."""
    ids = _seed_two_projects(pg_engine)

    with pg_engine.connect() as holder:
        _acquire_replacement_locks(holder, ids["project_id"])

        # An ordinary content update to a flow already locked FOR UPDATE by the
        # replacement blocks on that row lock and times out.
        with pg_engine.connect() as racer:
            racer.execute(text("SET lock_timeout = '200ms'"))
            with pytest.raises(OperationalError) as update_exc:
                racer.execute(text("UPDATE flow SET name = 'raced' WHERE id = :id"), {"id": str(ids["flow_id"])})
            assert getattr(update_exc.value.orig, "sqlstate", None) == "55P03"
            racer.rollback()

        # A new flow inserted into the locked project takes FOR KEY SHARE on
        # the Folder row via its FK check, which conflicts with the FOR
        # UPDATE the replacement is holding on that same row.
        with pg_engine.connect() as racer:
            racer.execute(text("SET lock_timeout = '200ms'"))
            with pytest.raises(OperationalError) as insert_exc:
                racer.execute(insert(Flow.__table__).values(id=uuid4(), name="new-flow", folder_id=ids["project_id"]))
            assert getattr(insert_exc.value.orig, "sqlstate", None) == "55P03"
            racer.rollback()

        # A flow in a different project shares neither the locked Folder row
        # nor any locked Flow row, so it is not blocked at all.
        with pg_engine.connect() as unrelated:
            unrelated.execute(text("SET lock_timeout = '200ms'"))
            unrelated.execute(
                text("UPDATE flow SET name = 'unblocked' WHERE id = :id"), {"id": str(ids["other_flow_id"])}
            )
            unrelated.commit()

        holder.rollback()
