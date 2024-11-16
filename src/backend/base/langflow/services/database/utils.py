from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from alembic.util.exc import CommandError
from loguru import logger
from sqlmodel import Session, text
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


def initialize_database(*, fix_migration: bool = False) -> None:
    logger.debug("Initializing database")
    from langflow.services.deps import get_db_service

    database_service: DatabaseService = get_db_service()
    try:
        database_service.create_db_and_tables()
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            msg = "Error creating DB and tables"
            logger.exception(msg)
            raise RuntimeError(msg) from exc
    try:
        database_service.check_schema_health()
    except Exception as exc:
        msg = "Error checking schema health"
        logger.exception(msg)
        raise RuntimeError(msg) from exc
    try:
        database_service.run_migrations(fix=fix_migration)
    except CommandError as exc:
        # if "overlaps with other requested revisions" or "Can't locate revision identified by"
        # are not in the exception, we can't handle it
        if "overlaps with other requested revisions" not in str(
            exc
        ) and "Can't locate revision identified by" not in str(exc):
            raise
        # This means there's wrong revision in the DB
        # We need to delete the alembic_version table
        # and run the migrations again
        logger.warning("Wrong revision in DB, deleting alembic_version table and running migrations again")
        with session_getter(database_service) as session:
            session.exec(text("DROP TABLE alembic_version"))
        database_service.run_migrations(fix=fix_migration)
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            logger.exception(exc)
        raise
    logger.debug("Database initialized")


@contextmanager
def session_getter(db_service: DatabaseService):
    try:
        session = Session(db_service.engine)
        yield session
    except Exception:
        logger.exception("Session rollback because of exception")
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def async_session_getter(db_service: DatabaseService):
    try:
        session = AsyncSession(db_service.async_engine)
        yield session
    except Exception:
        logger.exception("Session rollback because of exception")
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
