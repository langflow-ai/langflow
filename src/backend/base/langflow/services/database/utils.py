from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from alembic.util.exc import CommandError
from lfx.log.logger import logger
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

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
            from langflow.services.deps import session_scope

            async with session_scope() as session:
                await session.exec(text("DROP TABLE alembic_version"))
            await database_service.run_migrations(fix=fix_migration)
        else:
            raise
    except Exception as exc:
        error_message = str(exc)
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in error_message:
            logger.exception(exc)
            raise
        await logger.adebug("Migration attempted to create existing table, skipping.")
    await logger.adebug("Database initialized")


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


def validate_non_empty_string(v: str, info: object) -> str:
    """Validate a string field is non-empty after stripping whitespace.

    Intended for use inside ``@field_validator`` methods on SQLModel/Pydantic
    models.  Raises ``ValueError`` with the field name if the value is blank.
    """
    stripped = v.strip()
    if not stripped:
        field = getattr(info, "field_name", "Field")
        msg = f"{field} must not be empty"
        raise ValueError(msg)
    return stripped


def validate_non_empty_string_optional(v: str | None, info: object) -> str | None:
    """Like :func:`validate_non_empty_string` but allows ``None`` (skip)."""
    if v is None:
        return v
    return validate_non_empty_string(v, info)


def normalize_string_or_none(v: str | None) -> str | None:
    """Strip whitespace from *v* and return ``None`` if the result is blank."""
    if v is None:
        return None
    stripped = v.strip()
    return stripped if stripped else None


def parse_uuid(value: UUID | str, *, field_name: str = "value") -> UUID:
    """Parse a UUID from a string or pass through a UUID.

    Raises ValueError if the string is empty or not a valid UUID.
    The *field_name* parameter is included in the error message for context.
    """
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            msg = f"{field_name} must not be empty"
            raise ValueError(msg)
        try:
            return UUID(stripped)
        except ValueError as exc:
            msg = f"{field_name} is not a valid UUID: {stripped!r}"
            raise ValueError(msg) from exc
    msg = f"{field_name} must be a UUID or string, got {type(value).__name__}"
    raise TypeError(msg)


@dataclass
class Result:
    name: str
    type: str
    success: bool


@dataclass
class TableResults:
    table_name: str
    results: list[Result]
