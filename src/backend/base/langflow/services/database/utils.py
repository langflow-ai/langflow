from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from alembic.util.exc import CommandError
from lfx.log.logger import logger
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.constants import POSTGRESQL_VERSION_REQUIRED_MESSAGE

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


async def initialize_database(*, fix_migration: bool = False) -> None:
    await logger.adebug("Initializing database")
    from langflow.services.deps import get_db_service

    database_service: DatabaseService = get_db_service()
    await database_service.ensure_postgresql_version()
    try:
        if database_service.settings_service.settings.database_connection_retry:
            await database_service.create_db_and_tables_with_retry()
        else:
            await database_service.create_db_and_tables()
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            msg = "Error creating DB and tables"
            await logger.aexception(msg)
            raise RuntimeError(msg) from exc
    try:
        await database_service.check_schema_health()
    except Exception as exc:
        msg = "Error checking schema health"
        logger.exception(msg)
        raise RuntimeError(msg) from exc
    try:
        await database_service.run_migrations(fix=fix_migration)
    except CommandError as exc:
        error_message = str(exc)
        if (
            "overlaps with other requested revisions" in error_message
            or "Can't locate revision identified by" in error_message
        ):
            # Wrong revision in the DB: delete alembic_version and re-run migrations
            logger.warning("Wrong revision in DB, deleting alembic_version table and running migrations again")
            async with session_getter(database_service) as session:
                await session.exec(text("DROP TABLE alembic_version"))
            await database_service.run_migrations(fix=fix_migration)
        elif _is_postgresql_nulls_syntax_error(exc):
            raise RuntimeError(POSTGRESQL_VERSION_REQUIRED_MESSAGE) from exc
        else:
            raise
    except Exception as exc:
        if _is_postgresql_nulls_syntax_error(exc):
            raise RuntimeError(POSTGRESQL_VERSION_REQUIRED_MESSAGE) from exc
        error_message = str(exc)
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in error_message:
            logger.exception(exc)
            raise
        await logger.adebug("Migration attempted to create existing table, skipping.")
    await logger.adebug("Database initialized")


def _is_postgresql_nulls_syntax_error(exc: BaseException) -> bool:
    """True if this exception is the UNIQUE NULLS DISTINCT syntax error (PostgreSQL < 15)."""
    msg = str(exc)
    return "NULLS" in msg and "syntax error" in msg.lower()


@asynccontextmanager
async def session_getter(db_service: DatabaseService):
    try:
        session = AsyncSession(db_service.engine, expire_on_commit=False)
        yield session
    except Exception:
        await logger.aexception("Session rollback because of exception")
        await session.rollback()
        raise
    finally:
        await session.close()


@dataclass
class Result:
    name: str
    type: str
    success: bool


@dataclass
class TableResults:
    table_name: str
    results: list[Result]
