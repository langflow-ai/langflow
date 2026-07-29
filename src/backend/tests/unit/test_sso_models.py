"""Tests for SSO plugin models against a real database.

No mocks: uses in-memory SQLite with foreign keys enabled to verify
CASCADE delete, unique constraints, and default values.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from langflow.services.database.models.auth import decrypt_sso_client_secret, encrypt_sso_client_secret
from langflow.services.database.models.auth.sso import OIDCProviderSettings, SSOConfig, SSOSettings, SSOUserProfile
from langflow.services.database.models.user.model import User
from pydantic import SecretStr, ValidationError
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# Placeholder for User.password in tests (not a real secret)
_TEST_PASSWORD = "hashed"  # noqa: S105
_TEST_PLAINTEXT_SECRET = "oidc-client-secret"  # noqa: S105


@pytest.fixture(name="sso_secret_settings")
def sso_secret_settings_fixture():
    return SimpleNamespace(
        auth_settings=SimpleNamespace(SECRET_KEY=SecretStr("unit-test-langflow-secret-key-material"))
    )


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

    async def test_user_can_have_profiles_for_distinct_providers(self, sso_async_session):
        """One user can have one SSO profile for each distinct provider."""
        user = User(username="multi_provider_user", password=_TEST_PASSWORD)
        sso_async_session.add(user)
        await sso_async_session.commit()
        await sso_async_session.refresh(user)

        profiles = [
            SSOUserProfile(user_id=user.id, sso_provider="oidc-primary", sso_user_id="sub-1"),
            SSOUserProfile(user_id=user.id, sso_provider="oidc-secondary", sso_user_id="sub-2"),
            SSOUserProfile(user_id=user.id, sso_provider="saml", sso_user_id="sub-3"),
        ]
        sso_async_session.add_all(profiles)
        await sso_async_session.commit()

        result = await sso_async_session.exec(
            select(SSOUserProfile).where(SSOUserProfile.user_id == user.id).order_by(SSOUserProfile.sso_provider)
        )
        assert [profile.sso_provider for profile in result.all()] == ["oidc-primary", "oidc-secondary", "saml"]

    async def test_composite_unique_user_id_sso_provider(self, sso_async_session):
        """A user cannot have two SSO profiles for the same provider."""
        user = User(username="unique_user_provider", password=_TEST_PASSWORD)
        sso_async_session.add(user)
        await sso_async_session.commit()
        await sso_async_session.refresh(user)

        sso_async_session.add(SSOUserProfile(user_id=user.id, sso_provider="oidc-primary", sso_user_id="sub-1"))
        await sso_async_session.commit()

        duplicate = SSOUserProfile(user_id=user.id, sso_provider="oidc-primary", sso_user_id="sub-2")
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

    async def test_create_and_read_sso_config(self, sso_async_session, sso_secret_settings):
        """Create and read SSOConfig."""
        encrypted_secret = encrypt_sso_client_secret(_TEST_PLAINTEXT_SECRET, sso_secret_settings)
        config = SSOConfig(
            protocol="oidc",
            display_name="Test OIDC",
            client_secret_encrypted=encrypted_secret,
            provider_settings={
                "protocol": "oidc",
                "client_id": "client-id",
                "discovery_url": "https://idp.example.com/.well-known/openid-configuration",
                "redirect_uri": "/api/v1/login/callback",
                "scopes": "openid email profile groups",
                "token_endpoint": "https://idp.example.com/token",
                "authorization_endpoint": "https://idp.example.com/authorize",
                "jwks_uri": "https://idp.example.com/jwks",
                "issuer": "https://idp.example.com",
            },
        )
        sso_async_session.add(config)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)

        assert config.id is not None
        assert config.protocol == "oidc"
        assert config.display_name == "Test OIDC"
        assert config.slug.startswith("sso-")
        assert isinstance(config.provider_settings, OIDCProviderSettings)
        assert config.provider_settings.client_id == "client-id"
        assert config.provider_settings.discovery_url == "https://idp.example.com/.well-known/openid-configuration"
        assert config.provider_settings.scopes == "openid email profile groups"
        assert config.client_secret_encrypted == encrypted_secret
        assert config.enabled is True
        assert config.sort_order == 0
        assert config.email_claim == "email"
        assert config.username_claim == "preferred_username"
        assert config.user_id_claim == "sub"
        assert config.created_at is not None
        assert config.updated_at is not None
        assert config.updated_by is None

    async def test_default_values(self, sso_async_session):
        """Default values are applied when not specified."""
        config = SSOConfig(protocol="oidc", display_name="Default Test")
        sso_async_session.add(config)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)

        assert config.protocol == "oidc"
        assert config.provider_settings == OIDCProviderSettings()
        assert config.enabled is True
        assert config.sort_order == 0
        assert config.email_claim == "email"
        assert config.username_claim == "preferred_username"
        assert config.user_id_claim == "sub"
        assert config.created_by is None
        assert config.updated_by is None

    async def test_multiple_enabled_configs_have_deterministic_sort_order_and_one_instance_policy(
        self, sso_async_session
    ):
        settings = SSOSettings(enforce_sso=True)
        configs = [
            SSOConfig(display_name="Second", sort_order=20),
            SSOConfig(display_name="First", sort_order=10),
        ]
        sso_async_session.add_all([settings, *configs])
        await sso_async_session.commit()

        result = await sso_async_session.exec(
            select(SSOConfig).where(SSOConfig.enabled.is_(True)).order_by(SSOConfig.sort_order, SSOConfig.id)
        )
        assert [config.display_name for config in result.all()] == ["First", "Second"]
        assert (await sso_async_session.get(SSOSettings, 1)).enforce_sso is True
        assert "enforce_sso" not in SSOConfig.__table__.columns

        sso_async_session.add(SSOSettings(id=2, enforce_sso=False))
        with pytest.raises(IntegrityError, match=r"CHECK constraint failed|check constraint"):
            await sso_async_session.commit()

    async def test_updated_at_and_updated_by_are_maintained(self, sso_async_session):
        updater = User(username="sso_config_updater", password=_TEST_PASSWORD)
        config = SSOConfig(display_name="Audited connection")
        sso_async_session.add_all([updater, config])
        await sso_async_session.commit()
        await sso_async_session.refresh(updater)
        await sso_async_session.refresh(config)

        old_timestamp = datetime(2000, 1, 1, tzinfo=timezone.utc)
        config.updated_at = old_timestamp
        await sso_async_session.commit()

        config.display_name = "Updated connection"
        config.updated_by = updater.id
        await sso_async_session.commit()
        await sso_async_session.refresh(config)
        assert config.updated_at.replace(tzinfo=timezone.utc) > old_timestamp
        assert config.updated_by == updater.id

        await sso_async_session.delete(updater)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)
        assert config.updated_by is None

    async def test_client_secret_is_stored_as_ciphertext_envelope(self, sso_async_session, sso_secret_settings):
        encrypted = encrypt_sso_client_secret(_TEST_PLAINTEXT_SECRET, sso_secret_settings)
        config = SSOConfig(
            display_name="Encrypted secret connection",
            client_secret_encrypted=encrypted,
        )
        sso_async_session.add(config)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)

        stored_value = config.client_secret_encrypted
        assert stored_value is not None
        assert _TEST_PLAINTEXT_SECRET not in stored_value
        assert decrypt_sso_client_secret(stored_value, sso_secret_settings) == _TEST_PLAINTEXT_SECRET

    async def test_client_secret_rejects_plaintext_model_writes(self):
        with pytest.raises(ValueError, match="versioned SSO secret envelope"):
            SSOConfig(
                display_name="Plaintext secret connection",
                client_secret_encrypted=_TEST_PLAINTEXT_SECRET,
            )

    async def test_display_name_update_preserves_profile_connection(self, sso_async_session):
        """Changing the label does not change the profile's stable connection identity."""
        user = User(username="stable_connection_user", password=_TEST_PASSWORD)
        config = SSOConfig(display_name="Original connection name")
        sso_async_session.add_all([user, config])
        await sso_async_session.commit()
        await sso_async_session.refresh(user)
        await sso_async_session.refresh(config)

        original_slug = config.slug
        profile = SSOUserProfile(
            user_id=user.id,
            sso_provider=original_slug,
            sso_user_id="stable-subject",
        )
        sso_async_session.add(profile)
        await sso_async_session.commit()

        config.display_name = "Renamed connection"
        await sso_async_session.commit()
        await sso_async_session.refresh(profile)

        result = await sso_async_session.exec(select(SSOConfig).where(SSOConfig.slug == profile.sso_provider))
        resolved_config = result.one()
        assert config.slug == original_slug
        assert profile.sso_provider == original_slug
        assert resolved_config.display_name == "Renamed connection"

    async def test_slug_is_url_safe_unique_and_immutable(self, sso_async_session):
        config = SSOConfig(display_name="Primary connection")
        sso_async_session.add(config)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)

        assert config.slug.replace("-", "").isalnum()
        assert config.slug == config.slug.lower()

        config.slug = "sso-replacement"
        with pytest.raises(ValueError, match="immutable after insert"):
            await sso_async_session.commit()

    async def test_duplicate_slug_is_rejected(self, sso_async_session):
        slug = "sso-fixed-connection"
        sso_async_session.add(SSOConfig(slug=slug, display_name="First connection"))
        await sso_async_session.commit()

        sso_async_session.add(SSOConfig(slug=slug, display_name="Second connection"))
        with pytest.raises(IntegrityError, match=r"UNIQUE constraint failed|unique constraint"):
            await sso_async_session.commit()

    async def test_invalid_slug_is_rejected(self):
        with pytest.raises(ValueError, match="lowercase letters"):
            SSOConfig(slug="Not URL safe!", display_name="Invalid")

    async def test_provider_settings_reject_protocol_mismatch(self):
        with pytest.raises(ValueError, match="does not match"):
            SSOConfig(
                protocol="saml",
                display_name="Invalid",
                provider_settings={"protocol": "oidc"},
            )

    async def test_provider_settings_reject_invalid_oidc_payload(self):
        with pytest.raises(ValidationError, match="saml_metadata_url"):
            SSOConfig(
                protocol="oidc",
                display_name="Invalid",
                provider_settings={
                    "protocol": "oidc",
                    "saml_metadata_url": "https://idp.example.com/metadata",
                },
            )

    async def test_protocol_specific_settings_are_only_in_json_column(self):
        columns = SSOConfig.__table__.columns
        assert {"protocol", "provider_settings", "client_secret_encrypted"} <= set(columns.keys())
        assert {
            "provider",
            "client_id",
            "discovery_url",
            "redirect_uri",
            "scopes",
            "token_endpoint",
            "authorization_endpoint",
            "jwks_uri",
            "issuer",
        }.isdisjoint(columns.keys())
