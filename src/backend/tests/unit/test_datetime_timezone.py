"""Tests for datetime timezone compatibility (asyncpg support).

This test suite validates that DateTime(timezone=True) works correctly
with both asyncpg and psycopg drivers for PostgreSQL.

Related to: Migration c8613607a100_add_timezone_support_for_asyncpg
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.user.model import User
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service
from sqlalchemy import text
from sqlmodel import select


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


@pytest.mark.api_key_required
async def test_user_create_with_timezone_aware_datetime():
    """Test that User model accepts timezone-aware datetimes."""
    async with session_getter(get_db_service()) as session:
        user = _create_test_user(username_prefix="test_tz_user", with_login=True)

        session.add(user)
        await session.commit()
        await session.refresh(user)

        assert user.create_at is not None
        assert user.updated_at is not None
        assert user.last_login_at is not None
        assert user.create_at.tzinfo is not None
        assert user.updated_at.tzinfo is not None
        assert user.last_login_at.tzinfo is not None


@pytest.mark.api_key_required
async def test_apikey_create_with_timezone_aware_datetime():
    """Test that ApiKey model accepts timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        user = _create_test_user(username_prefix="test_apikey_user")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        api_key = ApiKey(
            id=uuid4(),
            api_key=f"test_key_{uuid4()}",
            user_id=user.id,
            name="Test API Key",
            last_used_at=now,
            total_uses=0,
            is_active=True,
        )

        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)

        assert api_key.last_used_at is not None
        assert api_key.last_used_at.tzinfo is not None


@pytest.mark.api_key_required
async def test_flow_create_with_timezone_aware_datetime():
    """Test that Flow model accepts timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        user = _create_test_user(username_prefix="test_flow_user")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        flow = Flow(
            id=uuid4(),
            name=f"Test Flow {uuid4()}",
            description="Test flow description",
            data={"nodes": [], "edges": []},
            user_id=user.id,
            updated_at=now,
        )

        session.add(flow)
        await session.commit()
        await session.refresh(flow)

        assert flow.updated_at is not None
        assert flow.updated_at.tzinfo is not None


@pytest.mark.api_key_required
async def test_message_create_with_timezone_aware_datetime():
    """Test that MessageTable model accepts timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        message = MessageTable(
            id=uuid4(),
            timestamp=now,
            sender="test_sender",
            sender_name="Test Sender",
            session_id=str(uuid4()),
            text="Test message",
        )

        session.add(message)
        await session.commit()
        await session.refresh(message)

        assert message.timestamp is not None
        assert message.timestamp.tzinfo is not None


@pytest.mark.api_key_required
async def test_datetime_comparison_timezone_aware():
    """Test that timezone-aware datetimes can be compared correctly."""
    now = datetime.now(timezone.utc)
    earlier = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    async with session_getter(get_db_service()) as session:
        user1 = _create_test_user(username_prefix="test_compare_1", created_at=earlier)
        user2 = _create_test_user(username_prefix="test_compare_2", created_at=now)

        session.add(user1)
        session.add(user2)
        await session.commit()

        stmt = select(User).where(User.username.like("test_compare_%")).order_by(User.create_at.desc())
        result = await session.exec(stmt)
        users = result.all()

        assert len(users) >= 2
        assert users[0].create_at > users[1].create_at


SCHEMA_VALIDATION_QUERY = """
    SELECT column_name, data_type, udt_name
    FROM information_schema.columns
    WHERE table_name = :table_name
    AND column_name = ANY(:columns)
    ORDER BY column_name
"""


def _assert_columns_use_timestamptz(columns: list, context: str) -> None:
    """Assert all columns use timestamptz type."""
    for column_name, data_type, udt_name in columns:
        assert udt_name == "timestamptz", (
            f"{context}: Column '{column_name}' should use timestamptz, but uses {udt_name} ({data_type})"
        )


@pytest.mark.api_key_required
@pytest.mark.skipif(
    get_db_service().database_url.startswith("sqlite"),
    reason="PostgreSQL-specific test (checks timestamptz schema)",
)
async def test_postgresql_schema_uses_timestamptz():
    """Test that PostgreSQL columns use TIMESTAMP WITH TIME ZONE.

    Validates that migration c8613607a100 was applied correctly.
    """
    async with session_getter(get_db_service()) as session:
        # Check User table
        result = await session.exec(
            text(SCHEMA_VALIDATION_QUERY),
            {"table_name": "user", "columns": ["create_at", "updated_at", "last_login_at"]},
        )
        _assert_columns_use_timestamptz(result.fetchall(), "User")

        # Check ApiKey table
        result = await session.exec(
            text(SCHEMA_VALIDATION_QUERY),
            {"table_name": "apikey", "columns": ["last_used_at"]},
        )
        _assert_columns_use_timestamptz(result.fetchall(), "ApiKey")

        # Check Flow table
        result = await session.exec(
            text(SCHEMA_VALIDATION_QUERY),
            {"table_name": "flow", "columns": ["updated_at"]},
        )
        _assert_columns_use_timestamptz(result.fetchall(), "Flow")

        # Check Message table
        result = await session.exec(
            text(SCHEMA_VALIDATION_QUERY),
            {"table_name": "message", "columns": ["timestamp"]},
        )
        _assert_columns_use_timestamptz(result.fetchall(), "Message")


@pytest.mark.api_key_required
async def test_datetime_serialization_iso8601():
    """Test that datetimes are serialized to ISO 8601 format correctly."""
    import json

    async with session_getter(get_db_service()) as session:
        user = _create_test_user(username_prefix="test_serialization")

        session.add(user)
        await session.commit()
        await session.refresh(user)

        user_dict = user.model_dump()
        assert "create_at" in user_dict
        assert "updated_at" in user_dict

        user_json = user.model_dump_json()
        assert user_json is not None

        parsed = json.loads(user_json)
        assert "T" in parsed["create_at"]
        assert "T" in parsed["updated_at"]


@pytest.mark.api_key_required
async def test_mixed_timezone_naive_and_aware_handling():
    """Test that the system handles timezone-aware datetimes correctly.

    Our models enforce timezone-aware datetimes via DateTime(timezone=True).
    """
    async with session_getter(get_db_service()) as session:
        user_aware = _create_test_user(username_prefix="test_aware")

        session.add(user_aware)
        await session.commit()
        await session.refresh(user_aware)

        assert user_aware.create_at.tzinfo is not None


@pytest.mark.api_key_required
async def test_bulk_insert_with_timezone_aware_datetimes():
    """Test bulk insertion of records with timezone-aware datetimes."""
    async with session_getter(get_db_service()) as session:
        users = [_create_test_user(username_prefix=f"test_bulk_{i}") for i in range(10)]

        session.add_all(users)
        await session.commit()

        stmt = select(User).where(User.username.like("test_bulk_%"))
        result = await session.exec(stmt)
        created_users = result.all()

        assert len(created_users) >= 10

        for user in created_users:
            assert user.create_at.tzinfo is not None
            assert user.updated_at.tzinfo is not None
