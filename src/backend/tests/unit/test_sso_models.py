"""Tests for SSO plugin models against a real database.

No mocks: uses in-memory SQLite with foreign keys enabled to verify
CASCADE delete, unique constraints, and default values.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.database.models.auth import (
    SSOConfigCreate,
    SSOConfigRead,
    SSOConfigUpdate,
    decrypt_sso_client_secret,
    encrypt_sso_client_secret,
)
from langflow.services.database.models.auth.sso import (
    LegacyProviderSettings,
    OIDCProviderSettings,
    SSOConfig,
    SSOSettings,
    SSOUserProfile,
)
from langflow.services.database.models.user.model import User
from pydantic import SecretStr, ValidationError
from sqlalchemy import event, func, literal, update
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# Placeholder for User.password in tests (not a real secret)
_TEST_PASSWORD = "hashed"  # noqa: S105
_TEST_PLAINTEXT_SECRET = "oidc-client-secret"  # noqa: S105  # pragma: allowlist secret


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
            first_name="Deon",
            last_name="Sanchez",
            picture="https://idp.example.com/Deon.png",
        )
        sso_async_session.add(profile)
        await sso_async_session.commit()
        await sso_async_session.refresh(profile)

        assert profile.id is not None
        assert profile.user_id == user.id
        assert profile.sso_provider == "oidc"
        assert profile.sso_user_id == "sub-123"
        assert profile.email == "user@example.com"
        assert profile.first_name == "Deon"
        assert profile.last_name == "Sanchez"
        assert profile.picture == "https://idp.example.com/Deon.png"
        assert profile.created_at is not None
        assert profile.updated_at is not None

    async def test_identity_details_default_to_none(self, sso_async_session):
        user = User(username="legacy_sso_user", password=_TEST_PASSWORD)
        sso_async_session.add(user)
        await sso_async_session.commit()
        await sso_async_session.refresh(user)

        profile = SSOUserProfile(
            user_id=user.id,
            sso_provider="oidc",
            sso_user_id="legacy-subject",
        )
        sso_async_session.add(profile)
        await sso_async_session.commit()
        await sso_async_session.refresh(profile)

        assert profile.first_name is None
        assert profile.last_name is None
        assert profile.picture is None

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
        assert config.enabled is False
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
        assert config.enabled is False
        assert config.sort_order == 0
        assert config.email_claim == "email"
        assert config.username_claim == "preferred_username"
        assert config.user_id_claim == "sub"
        assert config.created_by is None
        assert config.updated_by is None

    async def test_multiple_enabled_configs_have_deterministic_sort_order_and_one_instance_policy(
        self, sso_async_session, sso_secret_settings
    ):
        settings = SSOSettings(enforce_sso=True)
        encrypted_secret = encrypt_sso_client_secret(_TEST_PLAINTEXT_SECRET, sso_secret_settings)
        provider_settings = OIDCProviderSettings(
            client_id="client-id",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
        )
        configs = [
            SSOConfig(
                display_name="Second",
                enabled=True,
                sort_order=20,
                client_secret_encrypted=encrypted_secret,
                provider_settings=provider_settings,
            ),
            SSOConfig(
                display_name="First",
                enabled=True,
                sort_order=10,
                client_secret_encrypted=encrypted_secret,
                provider_settings=provider_settings,
            ),
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

    async def test_client_secret_rejects_plaintext_core_updates(self, sso_async_session):
        config = SSOConfig(display_name="Core update connection")
        sso_async_session.add(config)
        await sso_async_session.commit()

        with pytest.raises(StatementError, match="versioned SSO secret envelope"):
            await sso_async_session.execute(
                update(SSOConfig)
                .where(SSOConfig.id == config.id)
                .values(client_secret_encrypted=_TEST_PLAINTEXT_SECRET)
            )

    async def test_client_secret_rejects_plaintext_core_expression_updates(self, sso_async_session):
        config = SSOConfig(display_name="Core expression update connection")
        sso_async_session.add(config)
        await sso_async_session.commit()

        with pytest.raises(IntegrityError, match=r"client_secret_envelope|CHECK constraint failed"):
            await sso_async_session.execute(
                update(SSOConfig)
                .where(SSOConfig.id == config.id)
                .values(client_secret_encrypted=literal(_TEST_PLAINTEXT_SECRET))
            )

    async def test_client_secret_is_excluded_from_serialization_and_repr(self, sso_secret_settings):
        encrypted = encrypt_sso_client_secret(_TEST_PLAINTEXT_SECRET, sso_secret_settings)
        config = SSOConfig(display_name="Safe output", client_secret_encrypted=encrypted)

        assert "client_secret_encrypted" not in config.model_dump()
        assert encrypted not in config.model_dump_json()
        assert encrypted not in repr(config)

        read_config = SSOConfigRead.model_validate(config)
        assert "client_secret_encrypted" not in SSOConfigRead.model_fields
        assert encrypted not in read_config.model_dump_json()

    async def test_create_schema_accepts_plaintext_secret_and_encrypts_for_persistence(self, sso_secret_settings):
        create = SSOConfigCreate(
            display_name="Created safely",
            client_secret=SecretStr(_TEST_PLAINTEXT_SECRET),
        )

        assert "client_secret" not in create.model_dump()
        config = create.to_model(sso_secret_settings)
        assert config.client_secret_encrypted is not None
        assert config.client_secret_encrypted != _TEST_PLAINTEXT_SECRET
        assert decrypt_sso_client_secret(config.client_secret_encrypted, sso_secret_settings) == _TEST_PLAINTEXT_SECRET

    async def test_update_schema_encrypts_secret_and_validates_merged_enabled_state(self, sso_secret_settings):
        config = SSOConfig(display_name="Update safely")
        update_schema = SSOConfigUpdate(
            enabled=True,
            client_secret=SecretStr(_TEST_PLAINTEXT_SECRET),
            provider_settings=OIDCProviderSettings(
                client_id="client-id",
                discovery_url="https://idp.example.com/.well-known/openid-configuration",
            ),
        )

        update_schema.apply_to(config, sso_secret_settings)

        assert config.enabled is True
        assert config.client_secret_encrypted is not None
        assert decrypt_sso_client_secret(config.client_secret_encrypted, sso_secret_settings) == _TEST_PLAINTEXT_SECRET

    async def test_update_schema_preserves_actor_when_omitted_and_updates_explicit_actor(self):
        original_actor_id = uuid4()
        config = SSOConfig(display_name="Actor attribution", updated_by=original_actor_id)

        SSOConfigUpdate(display_name="No new actor").apply_to(config)
        assert config.updated_by == original_actor_id

        replacement_actor_id = uuid4()
        SSOConfigUpdate(display_name="Replacement actor").apply_to(config, actor_id=replacement_actor_id)
        assert config.updated_by == replacement_actor_id

    async def test_update_schema_atomically_converts_legacy_config_to_oidc(self, sso_secret_settings):
        config = SSOConfig(
            display_name="Legacy connection",
            protocol="saml",
            provider_settings=LegacyProviderSettings(protocol="saml"),
        )
        oidc_settings = OIDCProviderSettings(
            client_id="client-id",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
        )

        SSOConfigUpdate(
            protocol="oidc",
            enabled=True,
            client_secret=SecretStr(_TEST_PLAINTEXT_SECRET),
            provider_settings=oidc_settings,
        ).apply_to(config, sso_secret_settings)

        assert config.protocol == "oidc"
        assert config.provider_settings == oidc_settings
        assert config.enabled is True
        assert decrypt_sso_client_secret(config.client_secret_encrypted, sso_secret_settings) == _TEST_PLAINTEXT_SECRET

    async def test_incomplete_config_cannot_be_enabled(self, sso_async_session):
        with pytest.raises(ValueError, match="require a client_id"):
            SSOConfig(display_name="Incomplete", enabled=True)

        config = SSOConfig(display_name="Initially disabled")
        sso_async_session.add(config)
        await sso_async_session.commit()

        with pytest.raises(ValueError, match="require a client_id"):
            config.enabled = True
        assert config.enabled is False

    async def test_create_schema_rejects_incomplete_enabled_config(self):
        with pytest.raises(ValidationError, match="require a client_id"):
            SSOConfigCreate(display_name="Incomplete", enabled=True)

    async def test_provider_credentials_reject_blank_values_and_non_http_urls(self):
        with pytest.raises(ValidationError, match="client_id must not be blank"):
            OIDCProviderSettings(client_id=" \t ")

        for field_name in ("discovery_url", "token_endpoint", "authorization_endpoint", "jwks_uri", "issuer"):
            with pytest.raises(ValidationError, match="absolute HTTP"):
                OIDCProviderSettings(**{field_name: "file:///etc/passwd"})

        with pytest.raises(ValidationError, match="client secret must not be blank"):
            SSOConfigCreate(display_name="Blank secret", client_secret=SecretStr("  "))
        with pytest.raises(ValidationError, match="client secret must not be blank"):
            SSOConfigUpdate(client_secret=SecretStr(""))

    @pytest.mark.parametrize(
        "malformed_url",
        [
            "http:// example.com",
            "http://example.com:bad",
            "https://exa mple.com",
            "https://%zz",
            "https://example.com/%zz",
            "http:///etc/passwd",
        ],
    )
    async def test_provider_credentials_reject_malformed_http_urls(self, malformed_url):
        with pytest.raises(ValidationError, match="absolute HTTP"):
            OIDCProviderSettings(discovery_url=malformed_url)

    async def test_external_schemas_do_not_accept_audit_actor_fields(self, sso_secret_settings):
        actor_id = uuid4()
        with pytest.raises(ValidationError, match="created_by"):
            SSOConfigCreate(display_name="Caller attributed", created_by=actor_id)
        with pytest.raises(ValidationError, match="updated_by"):
            SSOConfigUpdate(updated_by=actor_id)

        config = SSOConfigCreate(display_name="Server attributed").to_model(
            sso_secret_settings,
            actor_id=actor_id,
        )
        assert config.created_by == actor_id
        assert config.updated_by == actor_id

        new_actor_id = uuid4()
        SSOConfigUpdate(display_name="Updated").apply_to(
            config,
            sso_secret_settings,
            actor_id=new_actor_id,
        )
        assert config.updated_by == new_actor_id

    async def test_standard_model_validation_is_safe_and_strict(self):
        config = SSOConfig.model_validate({"display_name": "Validated"})
        assert config.display_name == "Validated"
        assert config.enabled is False

        with pytest.raises(ValidationError, match="display_name"):
            SSOConfig.model_validate({})
        with pytest.raises(ValidationError, match="valid string"):
            SSOConfig.model_validate({"display_name": 123})
        with pytest.raises(ValidationError, match="extra_forbidden"):
            SSOConfig.model_validate(
                {
                    "display_name": "Malformed",
                    "provider_settings": {"protocol": "oidc", "unexpected": True},
                }
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

    async def test_core_update_cannot_enable_an_incomplete_config(self, sso_async_session):
        config = SSOConfig(display_name="Core incomplete")
        sso_async_session.add(config)
        await sso_async_session.commit()

        with pytest.raises(IntegrityError, match=r"enabled_complete|CHECK constraint failed"):
            await sso_async_session.execute(update(SSOConfig).where(SSOConfig.id == config.id).values(enabled=True))

    async def test_core_expression_cannot_install_invalid_url_on_enabled_config(
        self, sso_async_session, sso_secret_settings
    ):
        encrypted_secret = encrypt_sso_client_secret(_TEST_PLAINTEXT_SECRET, sso_secret_settings)
        config = SSOConfig(
            display_name="Core URL expression",
            enabled=True,
            client_secret_encrypted=encrypted_secret,
            provider_settings=OIDCProviderSettings(
                client_id="client-id",
                discovery_url="https://idp.example.com/.well-known/openid-configuration",
            ),
        )
        sso_async_session.add(config)
        await sso_async_session.commit()

        with pytest.raises(IntegrityError, match=r"enabled_complete|CHECK constraint failed"):
            await sso_async_session.execute(
                update(SSOConfig)
                .where(SSOConfig.id == config.id)
                .values(
                    provider_settings=func.json_set(
                        SSOConfig.provider_settings,
                        "$.discovery_url",
                        "http:///etc/passwd",
                    )
                )
            )

    async def test_core_update_cannot_change_protocol(self, sso_async_session):
        config = SSOConfig(display_name="Core protocol")
        sso_async_session.add(config)
        await sso_async_session.commit()

        with pytest.raises(IntegrityError, match=r"protocol_consistency|CHECK constraint failed"):
            await sso_async_session.execute(update(SSOConfig).where(SSOConfig.id == config.id).values(protocol="saml"))

    async def test_core_update_cannot_change_slug(self, sso_async_session):
        config = SSOConfig(display_name="Core slug")
        sso_async_session.add(config)
        await sso_async_session.commit()

        with pytest.raises(IntegrityError, match="immutable after insert"):
            await sso_async_session.execute(
                update(SSOConfig).where(SSOConfig.id == config.id).values(slug="sso-replacement")
            )

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

    async def test_invalid_slug_assignment_is_rejected_before_insert(self):
        config = SSOConfig(display_name="Pending")
        with pytest.raises(ValueError, match="lowercase letters"):
            config.slug = "INVALID!"

    async def test_provider_settings_reject_protocol_mismatch(self):
        with pytest.raises(ValueError, match="does not match"):
            SSOConfig(
                protocol="saml",
                display_name="Invalid",
                provider_settings={"protocol": "oidc"},
            )

    @pytest.mark.parametrize("protocol", ["saml", "ldap"])
    async def test_disabled_legacy_provider_settings_can_load(self, protocol, sso_async_session):
        config = SSOConfig(
            protocol=protocol,
            display_name=f"Legacy {protocol}",
            enabled=False,
            provider_settings={"protocol": protocol, "client_id": "legacy-client"},
        )
        sso_async_session.add(config)
        await sso_async_session.commit()
        await sso_async_session.refresh(config)

        assert config.protocol == protocol
        assert config.provider_settings.protocol == protocol
        assert config.provider_settings.client_id == "legacy-client"

    @pytest.mark.parametrize("protocol", ["saml", "ldap"])
    async def test_legacy_provider_settings_cannot_be_enabled(self, protocol):
        with pytest.raises(ValueError, match="Only OIDC configurations can be enabled"):
            SSOConfig(
                protocol=protocol,
                display_name=f"Legacy {protocol}",
                enabled=True,
                provider_settings={"protocol": protocol},
            )

    @pytest.mark.parametrize("protocol", ["saml", "ldap"])
    async def test_disabled_legacy_provider_settings_cannot_be_enabled_by_assignment(self, protocol):
        config = SSOConfig(
            protocol=protocol,
            display_name=f"Legacy {protocol}",
            enabled=False,
            provider_settings={"protocol": protocol},
        )

        with pytest.raises(ValueError, match="Only OIDC configurations can be enabled"):
            config.enabled = True

        assert config.enabled is False

    @pytest.mark.parametrize("protocol", ["saml", "ldap"])
    async def test_database_preserves_enabled_legacy_provider_settings(self, protocol, sso_async_session):
        config_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        await sso_async_session.execute(
            SSOConfig.__table__.insert().values(
                id=config_id,
                slug=f"sso-legacy-{protocol}-{uuid4().hex}",
                display_name=f"Legacy enabled {protocol}",
                protocol=protocol,
                enabled=True,
                sort_order=0,
                client_secret_encrypted=None,
                provider_settings={"protocol": protocol},
                email_claim="email",
                username_claim="preferred_username",
                user_id_claim="sub",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        await sso_async_session.commit()

        config = await sso_async_session.get(SSOConfig, config_id)
        assert config is not None
        assert config.enabled is True
        assert config.provider_settings.protocol == protocol

    async def test_protocol_assignment_rejects_mismatch_with_provider_settings(self):
        config = SSOConfig(protocol="oidc", display_name="Valid")
        with pytest.raises(ValueError, match="does not match"):
            config.protocol = "saml"

    async def test_provider_settings_assignment_rejects_protocol_mismatch(self):
        config = SSOConfig(protocol="oidc", display_name="Valid")
        # Bypass validates so we can exercise the provider_settings assignment check.
        config.__dict__["protocol"] = "saml"
        with pytest.raises(ValueError, match="does not match"):
            config.provider_settings = OIDCProviderSettings()

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

    async def test_nested_provider_settings_are_immutable(self):
        config = SSOConfig(display_name="Immutable settings")
        with pytest.raises(ValidationError, match="frozen_instance"):
            config.provider_settings.client_id = "new-client-id"
