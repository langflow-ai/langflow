"""Migration contract for versioned SSO client-secret ciphertext."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import sqlalchemy as sa
from alembic import command
from langflow.services.database.models.auth import decrypt_sso_client_secret, encrypt_sso_client_secret
from pydantic import SecretStr

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "b7d5f9a3c2e4"  # pragma: allowlist secret
_REVISION = "e9f2a3b4c5d6"  # pragma: allowlist secret
_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
_PLAINTEXT_SECRET = "migration-oidc-client-secret"  # noqa: S105  # pragma: allowlist secret


def _settings():
    return SimpleNamespace(
        auth_settings=SimpleNamespace(SECRET_KEY=SecretStr("migration-test-langflow-secret-key-material"))
    )


def test_sso_secret_upgrade_and_downgrade_preserve_seeded_ciphertext(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    user_id = str(uuid4())
    config_id = str(uuid4())
    profile_id = str(uuid4())
    encrypted_secret = encrypt_sso_client_secret(_PLAINTEXT_SECRET, _settings())

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
                    "username": "sso-secret-migration-user",
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
                    "provider": "oidc",
                    "provider_name": "Encrypted OIDC",
                    "enabled": True,
                    "enforce_sso": False,
                    "client_secret_encrypted": encrypted_secret,
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
                    "sso_provider": "encrypted-oidc",
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
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)
            stored_secret = connection.scalar(
                sa.select(sso_config.c.client_secret_encrypted).where(sso_config.c.id == config_id)
            )

            assert stored_secret == encrypted_secret
            assert _PLAINTEXT_SECRET not in stored_secret
            assert decrypt_sso_client_secret(stored_secret, _settings()) == _PLAINTEXT_SECRET
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
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)
            stored_secret = connection.scalar(
                sa.select(sso_config.c.client_secret_encrypted).where(sso_config.c.id == config_id)
            )

            assert stored_secret == encrypted_secret
            assert decrypt_sso_client_secret(stored_secret, _settings()) == _PLAINTEXT_SECRET
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(sso_user_profile).where(sso_user_profile.c.id == profile_id)
                )
                == 1
            )
    finally:
        engine.dispose()


def test_sso_upgrade_clears_pre_encryption_plaintext_secret(db_url):  # noqa: F811
    """A legacy plaintext secret is removed and its connection disabled.

    Before this revision ``client_secret_encrypted`` held the raw secret. The
    model now rejects non-envelope values, so leaving one in place would make the
    row unwritable through the ORM and undecryptable at login. The migration
    fails safe instead: clear the plaintext, disable the connection, and require
    an administrator to re-enter it.
    """
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    config_id = str(uuid4())

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            connection.execute(
                sso_config.insert(),
                {
                    "id": config_id,
                    "provider": "oidc",
                    "provider_name": "Legacy Plaintext OIDC",
                    "enabled": True,
                    "enforce_sso": False,
                    "client_secret_encrypted": _PLAINTEXT_SECRET,
                    "email_claim": "email",
                    "username_claim": "preferred_username",
                    "user_id_claim": "sub",
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
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            row = (
                connection.execute(
                    sa.select(sso_config.c.client_secret_encrypted, sso_config.c.enabled).where(
                        sso_config.c.id == config_id
                    )
                )
                .mappings()
                .one()
            )

            assert row["client_secret_encrypted"] is None
            assert not row["enabled"]
    finally:
        engine.dispose()
