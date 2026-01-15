"""Integration tests for PostgreSQL driver compatibility.

This test suite validates that DateTime(timezone=True) works with:
- asyncpg (async PostgreSQL driver)
- psycopg (modern async/sync driver)

These tests only run on PostgreSQL databases.

Related to: Migration c8613607a100_add_timezone_support_for_asyncpg
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.user.model import User
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import select

pytestmark = pytest.mark.skipif(
    not os.getenv("LANGFLOW_DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL-specific driver compatibility tests",
)

SCHEMA_VALIDATION_QUERY = """
    SELECT column_name, data_type, udt_name
    FROM information_schema.columns
    WHERE table_name = 'user'
    AND column_name IN ('create_at', 'updated_at', 'last_login_at')
    ORDER BY column_name
"""


def _create_test_user(
    *,
    username_prefix: str = "test",
    with_login: bool = False,
    created_at: datetime | None = None,
) -> User:
    """Create a test user with timezone-aware datetimes."""
    now = created_at or datetime.now(timezone.utc)
    return User(
        id=uuid4(),
        username=f"{username_prefix}_{uuid4()}",
        password="hashed_password",  # noqa: S106
        is_active=True,
        is_superuser=False,
        create_at=now,
        updated_at=now,
        last_login_at=now if with_login else None,
    )


def _get_postgres_url(driver: str) -> str:
    """Get PostgreSQL URL with specified driver."""
    url = os.getenv("LANGFLOW_DATABASE_URL", "")
    if not url or not url.startswith("postgresql"):
        pytest.skip("PostgreSQL database required for driver tests")

    base_url = url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")
    return base_url.replace("postgresql://", f"postgresql+{driver}://")


@pytest.fixture
def postgres_url_asyncpg() -> str:
    """Get PostgreSQL URL with asyncpg driver."""
    return _get_postgres_url("asyncpg")


@pytest.fixture
def postgres_url_psycopg() -> str:
    """Get PostgreSQL URL with psycopg driver."""
    return _get_postgres_url("psycopg")


async def _test_user_creation_with_driver(db_url: str, driver_name: str) -> None:
    """Test user creation with timezone-aware datetimes for a specific driver."""
    engine = create_async_engine(db_url, echo=False)

    try:
        async with AsyncSession(engine) as session:
            user = _create_test_user(username_prefix=f"test_{driver_name}", with_login=True)

            session.add(user)
            await session.commit()
            await session.refresh(user)

            assert user.id is not None
            assert user.create_at is not None
            assert user.create_at.tzinfo is not None
            assert user.create_at.tzinfo == timezone.utc

            stmt = select(User).where(User.id == user.id)
            result = await session.execute(stmt)
            db_user = result.scalars().first()

            assert db_user is not None
            assert db_user.create_at.tzinfo is not None
    finally:
        await engine.dispose()


async def _test_schema_validation_with_driver(db_url: str, driver_name: str) -> None:
    """Validate schema uses timestamptz with a specific driver."""
    engine = create_async_engine(db_url, echo=False)

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(SCHEMA_VALIDATION_QUERY))
            columns = result.fetchall()

            assert len(columns) > 0, "User table datetime columns not found"

            for column_name, data_type, udt_name in columns:
                assert udt_name == "timestamptz", (
                    f"{driver_name}: Column '{column_name}' should use timestamptz, "
                    f"but uses {udt_name} ({data_type}). Migration c8613607a100 may not be applied."
                )
    finally:
        await engine.dispose()


async def _test_bulk_insert_with_driver(db_url: str, driver_name: str, count: int = 5) -> None:
    """Test bulk insertion with timezone-aware datetimes for a specific driver."""
    engine = create_async_engine(db_url, echo=False)

    try:
        async with AsyncSession(engine) as session:
            users = [_create_test_user(username_prefix=f"test_{driver_name}_bulk_{i}") for i in range(count)]

            session.add_all(users)
            await session.commit()

            for user in users:
                await session.refresh(user)
                assert user.id is not None
                assert user.create_at.tzinfo is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_asyncpg_driver_creates_user_with_timezone_aware_datetime(postgres_url_asyncpg):
    """Test that asyncpg driver works with timezone-aware datetimes.

    Before the fix, asyncpg would reject datetime.now(timezone.utc) when
    inserting into TIMESTAMP WITHOUT TIME ZONE columns.
    """
    await _test_user_creation_with_driver(postgres_url_asyncpg, "asyncpg")


@pytest.mark.asyncio
async def test_psycopg_driver_creates_user_with_timezone_aware_datetime(postgres_url_psycopg):
    """Test that psycopg driver works with timezone-aware datetimes."""
    await _test_user_creation_with_driver(postgres_url_psycopg, "psycopg")


@pytest.mark.asyncio
async def test_asyncpg_driver_schema_validation(postgres_url_asyncpg):
    """Validate that asyncpg driver sees correct PostgreSQL schema."""
    await _test_schema_validation_with_driver(postgres_url_asyncpg, "asyncpg")


@pytest.mark.asyncio
async def test_psycopg_driver_schema_validation(postgres_url_psycopg):
    """Validate that psycopg driver sees correct PostgreSQL schema."""
    await _test_schema_validation_with_driver(postgres_url_psycopg, "psycopg")


@pytest.mark.asyncio
async def test_asyncpg_driver_bulk_insert(postgres_url_asyncpg):
    """Test bulk insertion with asyncpg driver."""
    await _test_bulk_insert_with_driver(postgres_url_asyncpg, "asyncpg")


@pytest.mark.asyncio
async def test_psycopg_driver_bulk_insert(postgres_url_psycopg):
    """Test bulk insertion with psycopg driver."""
    await _test_bulk_insert_with_driver(postgres_url_psycopg, "psycopg")


@pytest.mark.asyncio
async def test_asyncpg_datetime_storage_format(postgres_url_asyncpg):
    """Test that asyncpg stores datetimes with timezone information."""
    engine = create_async_engine(postgres_url_asyncpg, echo=False)

    try:
        async with AsyncSession(engine) as session:
            specific_time = datetime(2025, 11, 7, 12, 30, 45, tzinfo=timezone.utc)
            user = _create_test_user(username_prefix="test_asyncpg_format", created_at=specific_time)

            session.add(user)
            await session.commit()
            await session.refresh(user)

            result = await session.execute(
                text('SELECT create_at, pg_typeof(create_at) as type FROM "user" WHERE id = :user_id'),
                {"user_id": str(user.id)},
            )

            row = result.fetchone()
            assert row is not None

            db_datetime, pg_type = row
            assert pg_type == "timestamp with time zone"
            assert db_datetime == specific_time
    finally:
        await engine.dispose()
