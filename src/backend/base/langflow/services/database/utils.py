from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from alembic.util.exc import CommandError
from lfx.log.logger import logger
from sqlalchemy import Index, Select, inspect, select, tuple_, update
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from sqlalchemy import ColumnElement, Insert, Table
    from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession

    from langflow.services.database.service import DatabaseService


SKIP_ON_MYSQL_INFO_KEY = "langflow_skip_on_mysql"


def _is_not_mysql(_ddl: object, _target: object, bind: object, **kw: object) -> bool:
    dialect = kw.get("dialect") or getattr(bind, "dialect", None)
    # SQLAlchemy uses the "mysql" dialect name for MariaDB as well.
    return getattr(dialect, "name", None) != "mysql"


def skip_index_on_mysql(index: Index) -> Index:
    """Keep a PostgreSQL/SQLite-only index (e.g. an expression index) off MySQL/MariaDB.

    MariaDB cannot create expression indexes such as ``lower(col)`` or
    ``json_col->>'key'``. ``ddl_if`` skips the CREATE INDEX there, and the
    ``info`` marker lets ``alembic/env.py`` skip the index during autogenerate,
    so ``alembic check`` does not report it as missing.
    """
    index.info[SKIP_ON_MYSQL_INFO_KEY] = True
    return index.ddl_if(callable_=_is_not_mysql)


def materialize_subquery(stmt: Select) -> Select:
    """Wrap a LIMIT/OFFSET subquery so it can feed ``IN``/``NOT IN`` on MySQL/MariaDB.

    MariaDB rejects ``col IN (SELECT ... LIMIT n)`` (error 1235). Selecting from
    a derived table is accepted everywhere and is equivalent on PostgreSQL and
    SQLite. Because the derived table has a LIMIT/OFFSET it is always
    materialized, which also avoids MySQL's "can't specify target table for
    update in FROM clause" (error 1093) when a DELETE reads its own table.
    """
    derived = stmt.subquery()
    return select(*derived.c)


async def update_returning(
    session: SAAsyncSession,
    model: type[Any],
    *where: ColumnElement[bool],
    values: Mapping[str, Any],
) -> list[Any]:
    """Run ``UPDATE model SET values WHERE where`` and return the updated ORM rows.

    Uses ``UPDATE ... RETURNING`` where the dialect supports it (PostgreSQL,
    SQLite). MariaDB and MySQL do not, so there the matching rows are locked
    with ``SELECT ... FOR UPDATE``, updated by primary key and read back in the
    same transaction. The lock keeps it as atomic as the single statement: a
    concurrent writer waits for this transaction and then re-evaluates its own
    WHERE clause against the committed values.
    """
    if session.get_bind().dialect.update_returning:
        statement = (
            update(model)
            .where(*where)
            .values(**values)
            .returning(model)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
        return list((await session.execute(statement)).scalars().all())

    primary_key = inspect(model).primary_key
    keys = (await session.execute(select(*primary_key).where(*where).with_for_update())).all()
    if not keys:
        return []
    if len(primary_key) == 1:
        by_key = primary_key[0].in_([key[0] for key in keys])
    else:
        by_key = tuple_(*primary_key).in_([tuple(key) for key in keys])
    await session.execute(update(model).where(by_key).values(**values).execution_options(synchronize_session=False))
    reread = select(model).where(by_key).execution_options(populate_existing=True)
    return list((await session.execute(reread)).scalars().all())


def _dialect_insert(dialect_name: str) -> Callable[[Table], Insert]:
    """Return the dialect ``insert()`` construct that supports upserts."""
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect_name == "mysql":
        from sqlalchemy.dialects.mysql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


def upsert(
    dialect_name: str,
    table: Any,
    values: Mapping[str, Any],
    *,
    index_elements: Sequence[str],
    set_: Callable[[Any], Mapping[str, Any]],
) -> Insert:
    """Build an INSERT that updates the existing row when ``index_elements`` conflict.

    ``set_`` receives the proposed row (``excluded`` on PostgreSQL/SQLite,
    ``inserted`` on MySQL/MariaDB, which use ``ON DUPLICATE KEY UPDATE``) and
    returns the column assignments.
    """
    statement = _dialect_insert(dialect_name)(table).values(**values)
    if dialect_name == "mysql":
        return statement.on_duplicate_key_update(dict(set_(statement.inserted)))
    return statement.on_conflict_do_update(index_elements=list(index_elements), set_=dict(set_(statement.excluded)))


def insert_ignoring_conflicts(
    dialect_name: str,
    table: Any,
    rows: Sequence[Mapping[str, Any]],
    *,
    index_elements: Sequence[str] | None = None,
) -> Insert:
    """Build an INSERT that skips rows that conflict with an existing one.

    MySQL/MariaDB have no ``ON CONFLICT DO NOTHING``. Assigning a key column to
    itself on duplicate key is the no-op equivalent; ``INSERT IGNORE`` is not
    used because it would also turn unrelated errors into warnings.
    """
    statement = _dialect_insert(dialect_name)(table).values(list(rows))
    if dialect_name == "mysql":
        key = next(iter(getattr(table, "__table__", table).primary_key.columns))
        return statement.on_duplicate_key_update({key.name: key})
    return statement.on_conflict_do_nothing(index_elements=list(index_elements) if index_elements else None)


async def initialize_database(*, fix_migration: bool = False) -> None:
    await logger.adebug("Initializing database")
    from langflow.services.deps import get_db_service

    database_service: DatabaseService = get_db_service()
    await database_service.ensure_postgresql_version()
    # Fail fast with a clear, actionable message when a SQLite path cannot be
    # opened (e.g. a relative LANGFLOW_DATABASE_URL whose parent directory does
    # not exist), instead of the opaque "Error creating DB and tables" below.
    # See issue #13634.
    from langflow.services.database.service import check_sqlite_database_path

    check_sqlite_database_path(database_service.database_url)
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


def require_non_empty(value: str | None, error_msg: str) -> str:
    """Return a stripped non-empty string, or raise ``ValueError``."""
    stripped = (value or "").strip()
    if not stripped:
        raise ValueError(error_msg)
    return stripped


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


def validate_non_empty_string_preserve_value(v: str, info: object) -> str:
    """Validate a string field is non-empty without normalizing its value."""
    if not v.strip():
        field = getattr(info, "field_name", "Field")
        msg = f"{field} must not be empty"
        raise ValueError(msg)
    return v


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
