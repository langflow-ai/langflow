"""Migration contract for typed SSO provider settings."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import command

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "b7d5f9a3c2e4"  # pragma: allowlist secret
_REVISION = "e9f2a3b4c5d6"  # pragma: allowlist secret
_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
# Must be a structurally valid client-secret envelope. The revision clears any
# value that is not one: pre-encryption rows held plaintext, and the model now
# rejects non-envelope values. See _sanitize_legacy_client_secrets.
_TEST_ENCRYPTED_SECRET = "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:AAAAAAAAAAAAAAAA:BBBBBBBBBBBBBBBBBBBBBBBB"  # noqa: S105  # pragma: allowlist secret
_PROVIDER_SETTING_COLUMNS = {
    "discovery_url",
    "redirect_uri",
    "scopes",
    "token_endpoint",
    "authorization_endpoint",
    "jwks_uri",
    "issuer",
    "client_id",
}


def test_sso_provider_settings_upgrade_and_downgrade_preserve_seeded_rows(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    user_id = str(uuid4())
    config_id = str(uuid4())
    profile_id = str(uuid4())
    expected_settings = {
        "protocol": "oidc",
        "discovery_url": "https://idp.example.com/.well-known/openid-configuration",
        "redirect_uri": "/api/v1/login/callback",
        "scopes": "openid email profile groups",
        "token_endpoint": "https://idp.example.com/token",
        "authorization_endpoint": "https://idp.example.com/authorize",
        "jwks_uri": "https://idp.example.com/jwks",
        "issuer": "https://idp.example.com",
        "client_id": "client-id",
    }

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            user = sa.Table("user", metadata, autoload_with=connection)
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)
            connection.execute(
                user.insert(),
                {
                    "id": user_id,
                    "username": "sso-protocol-migration-user",
                    "password": _TEST_PASSWORD,
                    "is_active": True,
                    "is_superuser": False,
                    "create_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sso_config.insert(),
                {
                    "id": config_id,
                    "provider": expected_settings["protocol"],
                    "provider_name": "Primary OIDC",
                    "enabled": True,
                    "enforce_sso": False,
                    "client_secret_encrypted": _TEST_ENCRYPTED_SECRET,
                    **{name: expected_settings[name] for name in _PROVIDER_SETTING_COLUMNS},
                    "email_claim": "email",
                    "username_claim": "preferred_username",
                    "user_id_claim": "sub",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sso_user_profile.insert(),
                {
                    "id": profile_id,
                    "user_id": user_id,
                    "sso_provider": "primary-oidc",
                    "sso_user_id": "subject-1",
                    "email": "user@example.com",
                    "sso_last_login_at": None,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_cfg, _REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            columns = {column["name"] for column in inspector.get_columns("sso_config")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)
            config_row = connection.execute(sa.select(sso_config).where(sso_config.c.id == config_id)).mappings().one()

            assert {"protocol", "provider_settings", "client_secret_encrypted"} <= columns
            assert {"provider", *_PROVIDER_SETTING_COLUMNS} <= columns
            assert config_row["protocol"] == "oidc"
            assert config_row["provider"] == "oidc"
            assert config_row["provider_settings"] == expected_settings
            assert {name: config_row[name] for name in _PROVIDER_SETTING_COLUMNS} == {
                name: expected_settings[name] for name in _PROVIDER_SETTING_COLUMNS
            }
            assert config_row["client_secret_encrypted"] == _TEST_ENCRYPTED_SECRET
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(sso_user_profile).where(sso_user_profile.c.id == profile_id)
                )
                == 1
            )
    finally:
        engine.dispose()

    command.downgrade(alembic_cfg, _PRIOR_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.connect() as connection:
            columns = {column["name"] for column in sa.inspect(connection).get_columns("sso_config")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)
            config_row = connection.execute(sa.select(sso_config).where(sso_config.c.id == config_id)).mappings().one()

            assert {"provider", "client_secret_encrypted", *_PROVIDER_SETTING_COLUMNS} <= columns
            assert {"protocol", "provider_settings"}.isdisjoint(columns)
            assert config_row["provider"] == "oidc"
            assert {name: config_row[name] for name in _PROVIDER_SETTING_COLUMNS} == {
                name: expected_settings[name] for name in _PROVIDER_SETTING_COLUMNS
            }
            assert config_row["client_secret_encrypted"] == _TEST_ENCRYPTED_SECRET
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(sso_user_profile).where(sso_user_profile.c.id == profile_id)
                )
                == 1
            )
    finally:
        engine.dispose()
