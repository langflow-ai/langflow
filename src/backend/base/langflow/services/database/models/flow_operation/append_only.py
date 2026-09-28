"""Database triggers that keep ``flow_operation`` rows append-only.

History rows are written once and never changed. Application code never
updates or deletes them; these triggers make the database refuse it too, as
defence in depth against out-of-band writes from custom component code,
scripts, or manual queries:

- every ``UPDATE`` is rejected;
- on PostgreSQL, a ``DELETE`` is rejected while the row's flow still exists, so
  deleting a flow still cascades to its history, and ``TRUNCATE`` is rejected
  too, since row triggers do not fire for it. History maintenance, which
  deletes old rows of a flow that still exists, marks its own transaction with
  ``SET LOCAL`` (see ``delete_history_rows``) rather than disabling the trigger,
  which would lock the whole table against every flow's history until commit;
- on SQLite, every ``DELETE`` is rejected. The trigger cannot look at ``flow``
  the way PostgreSQL's does: SQLite re-checks every trigger that names a table
  when that table is rebuilt, and Alembic's ``batch_alter_table`` rebuilds
  ``flow`` by dropping it and renaming a copy, so a trigger naming ``flow``
  would make every future batch migration of ``flow`` fail. The code that does
  delete history (``delete_history_rows``) lifts the trigger inside its own
  transaction instead; SQLite DDL is transactional, so no other connection
  ever sees it missing.

This is hardening, not tamper-proofing: a role that can alter the schema, or
anyone holding the SQLite file, can drop the triggers. Replay still detects
damage they let through.

The same statements run from the model's ``after_create`` hook and from the
migration, so a database built either way has them. On SQLite, Alembic's
``batch_alter_table`` rebuilds a table by copying it and drops its triggers in
the process; any migration that batch-alters ``flow_operation`` must call
``create_statements`` again afterwards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.sql import Executable
    from sqlmodel.ext.asyncio.session import AsyncSession

TABLE = "flow_operation"
UPDATE_TRIGGER = "flow_operation_append_only_update"
DELETE_TRIGGER = "flow_operation_append_only_delete"
TRUNCATE_TRIGGER = "flow_operation_append_only_truncate"

_REJECT_CHANGE_FUNCTION = "flow_operation_reject_change"
_REJECT_DELETE_FUNCTION = "flow_operation_reject_orphaning_delete"

_CHANGE_MESSAGE = "flow_operation rows are append-only"
_DELETE_MESSAGE = "flow_operation rows can only be deleted together with their flow"
# Transaction-local marker set by history maintenance; it never outlives the
# transaction that sets it.
MAINTENANCE_SETTING = "langflow.flow_history_maintenance"
_SQLITE_DELETE_MESSAGE = "flow_operation rows can only be deleted by Langflow history maintenance"

_SQLITE_UPDATE_TRIGGER = f"""
    CREATE TRIGGER IF NOT EXISTS {UPDATE_TRIGGER}
    BEFORE UPDATE ON {TABLE}
    BEGIN
        SELECT RAISE(ABORT, '{_CHANGE_MESSAGE}');
    END
    """
_SQLITE_DELETE_TRIGGER = f"""
    CREATE TRIGGER IF NOT EXISTS {DELETE_TRIGGER}
    BEFORE DELETE ON {TABLE}
    BEGIN
        SELECT RAISE(ABORT, '{_SQLITE_DELETE_MESSAGE}');
    END
    """
_SQLITE_CREATE = (_SQLITE_UPDATE_TRIGGER, _SQLITE_DELETE_TRIGGER)

_POSTGRES_CREATE = (
    f"""
    CREATE OR REPLACE FUNCTION {_REJECT_CHANGE_FUNCTION}() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION '{_CHANGE_MESSAGE}';
    END;
    $$
    """,
    f"""
    CREATE OR REPLACE FUNCTION {_REJECT_DELETE_FUNCTION}() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        IF EXISTS (SELECT 1 FROM flow WHERE flow.id = OLD.flow_id)
            AND coalesce(current_setting('{MAINTENANCE_SETTING}', true), '') <> 'on' THEN
            RAISE EXCEPTION '{_DELETE_MESSAGE}';
        END IF;
        RETURN OLD;
    END;
    $$
    """,  # noqa: S608 -- built from module constants only
    f"DROP TRIGGER IF EXISTS {UPDATE_TRIGGER} ON {TABLE}",
    f"""
    CREATE TRIGGER {UPDATE_TRIGGER}
    BEFORE UPDATE ON {TABLE}
    FOR EACH ROW EXECUTE FUNCTION {_REJECT_CHANGE_FUNCTION}()
    """,
    f"DROP TRIGGER IF EXISTS {DELETE_TRIGGER} ON {TABLE}",
    f"""
    CREATE TRIGGER {DELETE_TRIGGER}
    BEFORE DELETE ON {TABLE}
    FOR EACH ROW EXECUTE FUNCTION {_REJECT_DELETE_FUNCTION}()
    """,
    f"DROP TRIGGER IF EXISTS {TRUNCATE_TRIGGER} ON {TABLE}",
    f"""
    CREATE TRIGGER {TRUNCATE_TRIGGER}
    BEFORE TRUNCATE ON {TABLE}
    FOR EACH STATEMENT EXECUTE FUNCTION {_REJECT_CHANGE_FUNCTION}()
    """,
)

_SQLITE_DROP = (
    f"DROP TRIGGER IF EXISTS {UPDATE_TRIGGER}",
    f"DROP TRIGGER IF EXISTS {DELETE_TRIGGER}",
)

_POSTGRES_DROP = (
    f"DROP TRIGGER IF EXISTS {TRUNCATE_TRIGGER} ON {TABLE}",
    f"DROP TRIGGER IF EXISTS {DELETE_TRIGGER} ON {TABLE}",
    f"DROP TRIGGER IF EXISTS {UPDATE_TRIGGER} ON {TABLE}",
    f"DROP FUNCTION IF EXISTS {_REJECT_DELETE_FUNCTION}()",
    f"DROP FUNCTION IF EXISTS {_REJECT_CHANGE_FUNCTION}()",
)


def drop_function_statements(dialect: str) -> tuple[str, ...]:
    """Return the statements that remove what outlives the table when it is dropped."""
    if dialect == "postgresql":
        return _POSTGRES_DROP[3:]
    return ()


def create_statements(dialect: str) -> tuple[str, ...]:
    """Return the statements that install the triggers on ``dialect``, idempotently."""
    if dialect == "sqlite":
        return _SQLITE_CREATE
    if dialect == "postgresql":
        return _POSTGRES_CREATE
    return ()


def drop_statements(dialect: str) -> tuple[str, ...]:
    """Return the statements that remove the triggers from ``dialect``."""
    if dialect == "sqlite":
        return _SQLITE_DROP
    if dialect == "postgresql":
        return _POSTGRES_DROP
    return ()


async def delete_history_rows(session: AsyncSession, statement: Executable) -> None:
    """Run a ``DELETE`` of ``flow_operation`` rows that Langflow itself decided on.

    On PostgreSQL the transaction is marked as maintenance for the statement.
    SQLite's trigger refuses every delete, so it is lifted for the statement
    and reinstated in the same transaction.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        await session.exec(text(f"SET LOCAL {MAINTENANCE_SETTING} = 'on'"))
        try:
            await session.exec(statement)
        finally:
            await session.exec(text(f"SET LOCAL {MAINTENANCE_SETTING} = 'off'"))
        return
    if dialect != "sqlite":
        await session.exec(statement)
        return
    await session.exec(text(f"DROP TRIGGER IF EXISTS {DELETE_TRIGGER}"))
    try:
        await session.exec(statement)
    finally:
        await session.exec(text(_SQLITE_DELETE_TRIGGER))
