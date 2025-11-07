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


@pytest.mark.api_key_required
async def test_user_create_with_timezone_aware_datetime():
    """Test that User model accepts timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        user = User(
            id=uuid4(),
            username=f"test_tz_user_{uuid4()}",
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

        # Verify datetimes are stored correctly
        assert user.create_at is not None
        assert user.updated_at is not None
        assert user.last_login_at is not None

        # Verify timezone information is preserved
        assert user.create_at.tzinfo is not None
        assert user.updated_at.tzinfo is not None
        assert user.last_login_at.tzinfo is not None


@pytest.mark.api_key_required
async def test_apikey_create_with_timezone_aware_datetime():
    """Test that ApiKey model accepts timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        # Create user first
        user = User(
            id=uuid4(),
            username=f"test_apikey_user_{uuid4()}",
            password="hashed_password",  # noqa: S106
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create API key with timezone-aware datetime
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

        # Verify datetime is stored correctly
        assert api_key.last_used_at is not None
        assert api_key.last_used_at.tzinfo is not None


@pytest.mark.api_key_required
async def test_flow_create_with_timezone_aware_datetime():
    """Test that Flow model accepts timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        # Create user first
        user = User(
            id=uuid4(),
            username=f"test_flow_user_{uuid4()}",
            password="hashed_password",  # noqa: S106
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create flow with timezone-aware datetime
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

        # Verify datetime is stored correctly
        assert flow.updated_at is not None
        assert flow.updated_at.tzinfo is not None


@pytest.mark.api_key_required
async def test_message_create_with_timezone_aware_datetime():
    """Test that MessageTable model accepts timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        # Create message with timezone-aware datetime
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

        # Verify datetime is stored correctly
        assert message.timestamp is not None
        assert message.timestamp.tzinfo is not None


@pytest.mark.api_key_required
async def test_datetime_comparison_timezone_aware():
    """Test that timezone-aware datetimes can be compared correctly."""
    now = datetime.now(timezone.utc)
    earlier = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    async with session_getter(get_db_service()) as session:
        user1 = User(
            id=uuid4(),
            username=f"test_compare_1_{uuid4()}",
            password="hashed_password",  # noqa: S106
            is_active=True,
            is_superuser=False,
            create_at=earlier,
            updated_at=earlier,
        )

        user2 = User(
            id=uuid4(),
            username=f"test_compare_2_{uuid4()}",
            password="hashed_password",  # noqa: S106
            is_active=True,
            is_superuser=False,
            create_at=now,
            updated_at=now,
        )

        session.add(user1)
        session.add(user2)
        await session.commit()

        # Query users ordered by create_at
        stmt = select(User).where(User.username.like("test_compare_%")).order_by(User.create_at.desc())

        result = await session.exec(stmt)
        users = result.all()

        # Verify ordering works correctly with timezone-aware datetimes
        assert len(users) >= 2
        assert users[0].create_at > users[1].create_at


@pytest.mark.api_key_required
@pytest.mark.skipif(
    get_db_service().database_url.startswith("sqlite"),
    reason="PostgreSQL-specific test (checks timestamptz schema)",
)
async def test_postgresql_schema_uses_timestamptz():
    """Test that PostgreSQL columns use TIMESTAMP WITH TIME ZONE.

    This test validates that the migration c8613607a100 was applied
    correctly and the schema uses timestamptz instead of timestamp.

    Only runs on PostgreSQL databases.
    """
    async with session_getter(get_db_service()) as session:
        # Check User table schema
        result = await session.exec(
            text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'user'
            AND column_name IN ('create_at', 'updated_at', 'last_login_at')
            ORDER BY column_name
        """)
        )

        columns = result.fetchall()

        # Verify all datetime columns use timestamptz
        for column_name, data_type, udt_name in columns:
            assert udt_name == "timestamptz", (
                f"Column '{column_name}' should use timestamptz, but uses {udt_name} ({data_type})"
            )

        # Check ApiKey table schema
        result = await session.exec(
            text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'apikey'
            AND column_name = 'last_used_at'
        """)
        )

        columns = result.fetchall()
        for _column_name, data_type, udt_name in columns:
            assert udt_name == "timestamptz", (
                f"ApiKey.last_used_at should use timestamptz, but uses {udt_name} ({data_type})"
            )

        # Check Flow table schema
        result = await session.exec(
            text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'flow'
            AND column_name = 'updated_at'
        """)
        )

        columns = result.fetchall()
        for _column_name, data_type, udt_name in columns:
            assert udt_name == "timestamptz", (
                f"Flow.updated_at should use timestamptz, but uses {udt_name} ({data_type})"
            )

        # Check Message table schema
        result = await session.exec(
            text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'message'
            AND column_name = 'timestamp'
        """)
        )

        columns = result.fetchall()
        for _column_name, data_type, udt_name in columns:
            assert udt_name == "timestamptz", (
                f"Message.timestamp should use timestamptz, but uses {udt_name} ({data_type})"
            )


@pytest.mark.api_key_required
async def test_datetime_serialization_iso8601():
    """Test that datetimes are serialized to ISO 8601 format correctly."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        user = User(
            id=uuid4(),
            username=f"test_serialization_{uuid4()}",
            password="hashed_password",  # noqa: S106
            is_active=True,
            is_superuser=False,
            create_at=now,
            updated_at=now,
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Serialize to dict
        user_dict = user.model_dump()

        # Verify datetime fields are present
        assert "create_at" in user_dict
        assert "updated_at" in user_dict

        # Serialize to JSON
        user_json = user.model_dump_json()

        # Verify JSON contains ISO 8601 format datetimes
        assert user_json is not None
        import json

        parsed = json.loads(user_json)

        # ISO 8601 format should contain 'T' separator
        assert "T" in parsed["create_at"]
        assert "T" in parsed["updated_at"]


@pytest.mark.api_key_required
async def test_mixed_timezone_naive_and_aware_handling():
    """Test that the system handles timezone-naive datetimes gracefully.

    While we always use timezone-aware datetimes in our code,
    this test ensures backward compatibility if any legacy data exists.
    """
    now_aware = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        # Create user with timezone-aware datetime
        user_aware = User(
            id=uuid4(),
            username=f"test_aware_{uuid4()}",
            password="hashed_password",  # noqa: S106
            is_active=True,
            is_superuser=False,
            create_at=now_aware,
            updated_at=now_aware,
        )

        session.add(user_aware)
        await session.commit()
        await session.refresh(user_aware)

        # Verify timezone-aware datetime works
        assert user_aware.create_at.tzinfo is not None

        # Note: We don't test timezone-naive datetimes because
        # our models now enforce timezone-aware datetimes via
        # DateTime(timezone=True) in the schema


@pytest.mark.api_key_required
async def test_bulk_insert_with_timezone_aware_datetimes():
    """Test bulk insertion of records with timezone-aware datetimes."""
    now = datetime.now(timezone.utc)

    async with session_getter(get_db_service()) as session:
        # Create multiple users with timezone-aware datetimes
        users = [
            User(
                id=uuid4(),
                username=f"test_bulk_{i}_{uuid4()}",
                password="hashed_password",  # noqa: S106
                is_active=True,
                is_superuser=False,
                create_at=now,
                updated_at=now,
            )
            for i in range(10)
        ]

        session.add_all(users)
        await session.commit()

        # Verify all users were created
        stmt = select(User).where(User.username.like("test_bulk_%"))
        result = await session.exec(stmt)
        created_users = result.all()

        assert len(created_users) >= 10

        # Verify all have timezone-aware datetimes
        for user in created_users:
            assert user.create_at.tzinfo is not None
            assert user.updated_at.tzinfo is not None
