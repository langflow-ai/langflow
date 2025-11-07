"""Integration tests for PostgreSQL driver compatibility.

This test suite validates that DateTime(timezone=True) works with:
- asyncpg (async PostgreSQL driver)
- psycopg (modern async/sync driver)
- psycopg2 (legacy sync driver)

These tests only run on PostgreSQL databases.

Related to: Migration c8613607a100_add_timezone_support_for_asyncpg
GitHub Issue: Verizon case - asyncpg compatibility
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.user.model import User
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import select

# Mark all tests in this module as standalone (don't need app client)
# and skip if not using PostgreSQL
pytestmark = [
    pytest.mark.standalone,
    pytest.mark.skipif(
        not os.getenv("LANGFLOW_DATABASE_URL", "").startswith("postgresql"),
        reason="PostgreSQL-specific driver compatibility tests",
    ),
]


@pytest.fixture
def postgres_url_asyncpg():
    """Get PostgreSQL URL with asyncpg driver."""
    url = os.getenv("LANGFLOW_DATABASE_URL", "")
    if not url or not url.startswith("postgresql"):
        pytest.skip("PostgreSQL database required for driver tests")

    # Convert to asyncpg format
    return url.replace("postgresql://", "postgresql+asyncpg://").replace(
        "postgresql+psycopg://", "postgresql+asyncpg://"
    )


@pytest.fixture
def postgres_url_psycopg():
    """Get PostgreSQL URL with psycopg (v3) driver."""
    url = os.getenv("LANGFLOW_DATABASE_URL", "")
    if not url or not url.startswith("postgresql"):
        pytest.skip("PostgreSQL database required for driver tests")

    # Convert to psycopg format
    return url.replace("postgresql://", "postgresql+psycopg://").replace(
        "postgresql+asyncpg://", "postgresql+psycopg://"
    )


@pytest.mark.asyncio
async def test_asyncpg_driver_creates_user_with_timezone_aware_datetime(postgres_url_asyncpg):
    """Test that asyncpg driver works with timezone-aware datetimes.

    This test validates that the fix for the Verizon case works correctly.
    Before the fix, asyncpg would reject datetime.now(timezone.utc) when
    inserting into TIMESTAMP WITHOUT TIME ZONE columns.

    After the fix, with DateTime(timezone=True), asyncpg accepts timezone-aware
    datetimes because the column is TIMESTAMP WITH TIME ZONE.
    """
    engine = create_async_engine(postgres_url_asyncpg, echo=False)

    try:
        async with AsyncSession(engine) as session:
            now = datetime.now(timezone.utc)

            # Create user with timezone-aware datetime
            user = User(
                id=uuid4(),
                username=f"test_asyncpg_{uuid4()}",
                password="hashed_password",  # noqa: S106
                is_active=True,
                is_superuser=False,
                create_at=now,
                updated_at=now,
                last_login_at=now,
            )

            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Verify user was created successfully
            assert user.id is not None
            assert user.create_at is not None
            assert user.create_at.tzinfo is not None

            # Verify datetime has timezone information
            assert user.create_at.tzinfo == timezone.utc

            # Query user back from database
            stmt = select(User).where(User.id == user.id)
            result = await session.execute(stmt)
            db_user = result.scalars().first()

            assert db_user is not None
            assert db_user.create_at.tzinfo is not None

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_psycopg_driver_creates_user_with_timezone_aware_datetime(postgres_url_psycopg):
    """Test that psycopg (v3) driver works with timezone-aware datetimes.

    This test validates that the fix doesn't break psycopg compatibility.
    """
    engine = create_async_engine(postgres_url_psycopg, echo=False)

    try:
        async with AsyncSession(engine) as session:
            now = datetime.now(timezone.utc)

            # Create user with timezone-aware datetime
            user = User(
                id=uuid4(),
                username=f"test_psycopg_{uuid4()}",
                password="hashed_password",  # noqa: S106
                is_active=True,
                is_superuser=False,
                create_at=now,
                updated_at=now,
                last_login_at=now,
            )

            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Verify user was created successfully
            assert user.id is not None
            assert user.create_at is not None
            assert user.create_at.tzinfo is not None

            # Verify datetime has timezone information
            assert user.create_at.tzinfo == timezone.utc

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_asyncpg_driver_schema_validation(postgres_url_asyncpg):
    """Validate that asyncpg driver sees correct PostgreSQL schema.

    This test confirms that the database schema uses TIMESTAMP WITH TIME ZONE
    when accessed via asyncpg driver.
    """
    engine = create_async_engine(postgres_url_asyncpg, echo=False)

    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                SELECT
                    column_name,
                    data_type,
                    udt_name
                FROM information_schema.columns
                WHERE table_name = 'user'
                AND column_name IN ('create_at', 'updated_at', 'last_login_at')
                ORDER BY column_name
            """)
            )

            columns = result.fetchall()

            # Verify we found the columns
            assert len(columns) > 0, "User table datetime columns not found"

            # Verify all use timestamptz
            for column_name, data_type, udt_name in columns:
                assert udt_name == "timestamptz", (
                    f"asyncpg: Column '{column_name}' should use timestamptz, "
                    f"but uses {udt_name} ({data_type}). This indicates the migration "
                    "c8613607a100 was not applied correctly."
                )

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_psycopg_driver_schema_validation(postgres_url_psycopg):
    """Validate that psycopg driver sees correct PostgreSQL schema.

    This test confirms that the database schema uses TIMESTAMP WITH TIME ZONE
    when accessed via psycopg driver.
    """
    engine = create_async_engine(postgres_url_psycopg, echo=False)

    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                SELECT
                    column_name,
                    data_type,
                    udt_name
                FROM information_schema.columns
                WHERE table_name = 'user'
                AND column_name IN ('create_at', 'updated_at', 'last_login_at')
                ORDER BY column_name
            """)
            )

            columns = result.fetchall()

            # Verify we found the columns
            assert len(columns) > 0, "User table datetime columns not found"

            # Verify all use timestamptz
            for column_name, data_type, udt_name in columns:
                assert udt_name == "timestamptz", (
                    f"psycopg: Column '{column_name}' should use timestamptz, but uses {udt_name} ({data_type})"
                )

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_asyncpg_driver_bulk_insert(postgres_url_asyncpg):
    """Test bulk insertion with asyncpg driver.

    Validates that asyncpg can handle multiple inserts with timezone-aware
    datetimes in a single transaction.
    """
    engine = create_async_engine(postgres_url_asyncpg, echo=False)

    try:
        async with AsyncSession(engine) as session:
            now = datetime.now(timezone.utc)

            # Create multiple users
            users = [
                User(
                    id=uuid4(),
                    username=f"test_asyncpg_bulk_{i}_{uuid4()}",
                    password="hashed_password",  # noqa: S106
                    is_active=True,
                    is_superuser=False,
                    create_at=now,
                    updated_at=now,
                )
                for i in range(5)
            ]

            session.add_all(users)
            await session.commit()

            # Verify all users were created
            for user in users:
                await session.refresh(user)
                assert user.id is not None
                assert user.create_at.tzinfo is not None

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_psycopg_driver_bulk_insert(postgres_url_psycopg):
    """Test bulk insertion with psycopg driver.

    Validates that psycopg can handle multiple inserts with timezone-aware
    datetimes in a single transaction.
    """
    engine = create_async_engine(postgres_url_psycopg, echo=False)

    try:
        async with AsyncSession(engine) as session:
            now = datetime.now(timezone.utc)

            # Create multiple users
            users = [
                User(
                    id=uuid4(),
                    username=f"test_psycopg_bulk_{i}_{uuid4()}",
                    password="hashed_password",  # noqa: S106
                    is_active=True,
                    is_superuser=False,
                    create_at=now,
                    updated_at=now,
                )
                for i in range(5)
            ]

            session.add_all(users)
            await session.commit()

            # Verify all users were created
            for user in users:
                await session.refresh(user)
                assert user.id is not None
                assert user.create_at.tzinfo is not None

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_asyncpg_datetime_storage_format(postgres_url_asyncpg):
    """Test that asyncpg stores datetimes with timezone information.

    Validates that when we store a timezone-aware datetime via asyncpg,
    it's actually stored with timezone information in PostgreSQL.
    """
    engine = create_async_engine(postgres_url_asyncpg, echo=False)

    try:
        async with AsyncSession(engine) as session:
            # Create user with specific datetime
            specific_time = datetime(2025, 11, 7, 12, 30, 45, tzinfo=timezone.utc)

            user = User(
                id=uuid4(),
                username=f"test_asyncpg_format_{uuid4()}",
                password="hashed_password",  # noqa: S106
                is_active=True,
                is_superuser=False,
                create_at=specific_time,
                updated_at=specific_time,
            )

            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Query via SQL to see exact storage format
            result = await session.execute(
                text("""
                SELECT
                    create_at,
                    pg_typeof(create_at) as type
                FROM "user"
                WHERE id = :user_id
            """),
                {"user_id": str(user.id)},
            )

            row = result.fetchone()
            assert row is not None

            db_datetime, pg_type = row

            # Verify PostgreSQL type
            assert pg_type == "timestamp with time zone"

            # Verify datetime value
            assert db_datetime == specific_time

    finally:
        await engine.dispose()
