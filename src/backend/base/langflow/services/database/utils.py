from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from alembic.util.exc import CommandError
from loguru import logger
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.utils import constants

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


def truncate_json(data, *, max_size: int = constants.MAX_TEXT_LENGTH):
    def calculate_size(data):
        return len(json.dumps(data))

    def shrink_to_size(data, remaining_size):
        if isinstance(data, dict):
            truncated = {}
            for key, value in data.items():
                key_size = len(json.dumps(key))
                if remaining_size - key_size <= 0:
                    break
                truncated[key] = shrink_to_size(value, remaining_size - key_size)
                remaining_size -= len(json.dumps({key: value})) - key_size
            return truncated

        if isinstance(data, list):
            truncated = []
            for item in data:
                if remaining_size <= len('""'):
                    break
                truncated.append(shrink_to_size(item, remaining_size))
                remaining_size -= len(json.dumps(item)) + 1
            return truncated

        if isinstance(data, str):
            max_string_length = max(remaining_size - 2, 0)
            return data[:max_string_length] + "…" if max_string_length > 0 else "…"

        return data

    try:
        json.dumps(data)
        is_serialized = True
    except Exception:  # noqa: BLE001
        is_serialized = False

    if calculate_size(data) <= max_size or not is_serialized:
        return data

    return shrink_to_size(data, max_size)


async def initialize_database(*, fix_migration: bool = False) -> None:
    logger.debug("Initializing database")
    from langflow.services.deps import get_db_service

    database_service: DatabaseService = get_db_service()
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
            logger.exception(msg)
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
        async with session_getter(database_service) as session:
            await session.exec(text("DROP TABLE alembic_version"))
        await database_service.run_migrations(fix=fix_migration)
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            logger.exception(exc)
        raise
    logger.debug("Database initialized")


@asynccontextmanager
async def session_getter(db_service: DatabaseService):
    try:
        session = AsyncSession(db_service.engine, expire_on_commit=False)
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
