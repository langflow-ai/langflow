"""Tests for SSO plugin models against a real database.

No mocks: uses in-memory SQLite with foreign keys enabled to verify
CASCADE delete, unique constraints, and default values.
"""

import pytest
from langflow.services.database.models.auth.sso import SSOConfig, SSOUserProfile
from langflow.services.database.models.user.model import User
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# Placeholder for User.password in tests (not a real secret)
_TEST_PASSWORD = "hashed"  # noqa: S105


@pytest.fixture(name="sso_db_engine")
def sso_db_engine():
    """Async engine with SQLite and foreign keys enabled (real DB, no mocks)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(name="sso_async_session")
async def sso_async_session(sso_db_engine):
    """Async session with SSO and User tables created (real DB)."""
    async with sso_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(sso_db_engine, expire_on_commit=False) as session:
        yield session
    async with sso_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await sso_db_engine.dispose()


@pytest.mark.asyncio
class TestSSOUserProfile:
    """SSOUserProfile model tests against real database."""

    async def test_create_and_read_sso_user_profile(self, sso_async_session):
        """Create and read SSOUserProfile records."""
        user = User(username="sso_user", password=_TEST_PASSWORD)
        sso_async_session.add(user)
        await sso_async_session.commit()
        await sso_async_session.refresh(user)

        profile = SSOUserProfile(
            user_id=user.id,
            sso_provider="oidc",
            sso_user_id="sub-123",
            email="user@example.com",
        )
        sso_async_session.add(profile)
        await sso_async_session.commit()
        await sso_async_session.refresh(profile)

        assert profile.id is not None
        assert profile.user_id == user.id
        assert profile.sso_provider == "oidc"
        assert profile.sso_user_id == "sub-123"
        assert profile.email == "user@example.com"
        assert profile.created_at is not None
        assert profile.updated_at is not None

    async def test_user_id_unique_constraint(self, sso_async_session):
        """Cannot create two SSO profiles for the same user."""
        user = User(username="unique_user", password=_TEST_PASSWORD)
        sso_async_session.add(user)
        await sso_async_session.commit()
        await sso_async_session.refresh(user)

        sso_async_session.add(SSOUserProfile(user_id=user.id, sso_provider="oidc", sso_user_id="sub-1"))
        await sso_async_session.commit()

        duplicate = SSOUserProfile(user_id=user.id, sso_provider="saml", sso_user_id="sub-2")
        sso_async_session.add(duplicate)
        with pytest.raises(IntegrityError, match=r"UNIQUE constraint failed|unique constraint"):
            await sso_async_session.commit()

    async def test_composite_unique_sso_provider_sso_user_id(self, sso_async_session):
        """Same (sso_provider, sso_user_id) cannot be used for two different users."""
        user1 = User(username="user1", password=_TEST_PASSWORD)
        user2 = User(username="user2", password=_TEST_PASSWORD)
        sso_async_session.add(user1)
        sso_async_session.add(user2)
        await sso_async_session.commit()
        await sso_async_session.refresh(user1)
        await sso_async_session.refresh(user2)

        sso_async_session.add(SSOUserProfile(user_id=user1.id, sso_provider="oidc", sso_user_id="sub-123"))
        await sso_async_session.commit()

        duplicate = SSOUserProfile(user_id=user2.id, sso_provider="oidc", sso_user_id="sub-123")
        sso_async_session.add(duplicate)
        with pytest.raises(IntegrityError, match=r"UNIQUE constraint failed|unique constraint"):
            await sso_async_session.commit()

    async def test_cascade_delete_when_user_deleted(self, sso_async_session):
        """Deleting user deletes associated SSOUserProfile (CASCADE)."""
        user = User(username="cascade_user", password=_TEST_PASSWORD)
        sso_async_session.add(user)
        await sso_async_session.commit()
        await sso_async_session.refresh(user)

        profile = SSOUserProfile(user_id=user.id, sso_provider="oidc", sso_user_id="sub-cascade")
        sso_async_session.add(profile)
        await sso_async_session.commit()
        await sso_async_session.refresh(profile)
        profile_id = profile.id

        await sso_async_session.delete(user)
        await sso_async_session.commit()

        result = await sso_async_session.exec(select(SSOUserProfile).where(SSOUserProfile.id == profile_id))
        assert result.first() is None

    async def test_default_timestamps_set(self, sso_async_session):
        """created_at and updated_at are set on create."""
        user = User(username="ts_user", password=_TEST_PASSWORD)
        sso_async_session.add(user)
        await sso_async_session.commit()
        await sso_async_session.refresh(user)

        profile = SSOUserProfile(user_id=user.id, sso_provider="oidc", sso_user_id="sub-ts")
        sso_async_session.add(profile)
        await sso_async_session.commit()
        await sso_async_session.refresh(profile)

        assert profile.created_at is not None
        assert profile.updated_at is not None


@pytest.mark.asyncio
class TestSSOConfig:
    """SSOConfig model tests against real database."""

    async def test_create_and_read_sso_config(self, sso_async_session):
        """Create and read SSOConfig."""
        config = SSOConfig(
            provider="oidc",
            provider_name="Test OIDC",
        )
        sso_async_session.add(config)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)

        assert config.id is not None
        assert config.provider == "oidc"
        assert config.provider_name == "Test OIDC"
        assert config.enabled is True
        assert config.enforce_sso is False
        assert config.scopes == "openid email profile"
        assert config.email_claim == "email"
        assert config.username_claim == "preferred_username"
        assert config.user_id_claim == "sub"
        assert config.created_at is not None
        assert config.updated_at is not None

    async def test_default_values(self, sso_async_session):
        """Default values are applied when not specified."""
        config = SSOConfig(provider="oidc", provider_name="Default Test")
        sso_async_session.add(config)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)

        assert config.enabled is True
        assert config.enforce_sso is False
        assert config.scopes == "openid email profile"
        assert config.email_claim == "email"
        assert config.username_claim == "preferred_username"
        assert config.user_id_claim == "sub"
        assert config.created_by is None
