"""Opt-in execution for audited, independent UPDATE statements."""

from sqlalchemy.sql.dml import Update

from langflow.services.deps import get_db_service


async def execute_independent_update(statement: Update) -> int:
    """Execute one complete atomic update and return its affected-row count.

    Only callers with no surrounding reads, writes, or rollback dependency may
    use this helper. On PostgreSQL READ COMMITTED, the statement commits in the
    driver; a later Python error or cancellation cannot undo it. Never retry an
    ambiguous execution failure here. SQLite and other isolation levels retain
    an explicit transaction. Connection close restores pooled isolation state.
    """
    if not isinstance(statement, Update):
        msg = "An independent write must be a SQLAlchemy UPDATE statement"
        raise TypeError(msg)
    engine = get_db_service().engine
    async with engine.connect() as connection:
        # get_isolation_level() itself starts a transaction/SHOW/ROLLBACK with
        # asyncpg, costing more round trips than this optimization saves. Use
        # SQLAlchemy's initialized default plus its configured engine override.
        # Fail closed if a future dialect no longer exposes that override.
        configured = getattr(connection.dialect, "_on_connect_isolation_level", "unknown")
        isolation = connection.sync_connection.get_execution_options().get("isolation_level") or configured
        isolation = isolation or connection.default_isolation_level
        if connection.dialect.name == "postgresql" and isolation == "READ COMMITTED":
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            result = await connection.execute(statement)
        else:
            async with connection.begin():
                result = await connection.execute(statement)
        return result.rowcount
