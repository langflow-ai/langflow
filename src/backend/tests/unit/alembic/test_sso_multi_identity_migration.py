"""Migration contract for multiple SSO identities per user."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import IntegrityError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "b7d5f9a3c2e4"  # pragma: allowlist secret
_REVISION = "e9f2a3b4c5d6"  # pragma: allowlist secret
_USER_ID_INDEX = "ix_sso_user_profile_user_id"
_USER_PROVIDER_INDEX = "uq_sso_user_profile_user_provider"
_PROVIDER_IDENTITY_INDEX = "uq_sso_user_profile_provider_user"
_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


def _profile_values(
    *,
    profile_id: str,
    user_id: str,
    provider: str,
    sso_user_id: str,
    timestamp: datetime,
) -> dict:
    return {
        "id": profile_id,
        "user_id": user_id,
        "sso_provider": provider,
        "sso_user_id": sso_user_id,
        "email": None,
        "sso_last_login_at": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_sso_multi_identity_upgrade_and_downgrade_preserve_seeded_rows(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    user_id = str(uuid4())
    other_user_id = str(uuid4())
    config_id = str(uuid4())
    original_profile_id = str(uuid4())
    second_profile_id = str(uuid4())

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            user = sa.Table("user", metadata, autoload_with=connection)
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            connection.execute(
                user.insert(),
                [
                    {
                        "id": user_id,
                        "username": "sso-migration-user",
                        "password": _TEST_PASSWORD,
                        "is_active": True,
                        "is_superuser": False,
                        "create_at": timestamp,
                        "updated_at": timestamp,
                    },
                    {
                        "id": other_user_id,
                        "username": "sso-migration-other-user",
                        "password": _TEST_PASSWORD,
                        "is_active": True,
                        "is_superuser": False,
                        "create_at": timestamp,
                        "updated_at": timestamp,
                    },
                ],
            )
            connection.execute(
                sso_config.insert(),
                {
                    "id": config_id,
                    "provider": "oidc",
                    "provider_name": "Primary OIDC",
                    "enabled": True,
                    "enforce_sso": False,
                    "email_claim": "email",
                    "username_claim": "preferred_username",
                    "user_id_claim": "sub",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sso_user_profile.insert(),
                _profile_values(
                    profile_id=original_profile_id,
                    user_id=user_id,
                    provider="oidc-primary",
                    sso_user_id="subject-1",
                    timestamp=timestamp,
                ),
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_cfg, _REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            indexes = {index["name"]: index for index in inspector.get_indexes("sso_user_profile")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            assert not indexes[_USER_ID_INDEX]["unique"]
            assert indexes[_USER_PROVIDER_INDEX]["unique"]
            assert indexes[_PROVIDER_IDENTITY_INDEX]["unique"]
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(sso_config).where(sso_config.c.id == config_id)
                )
                == 1
            )
            assert (
                connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(sso_user_profile)
                    .where(sso_user_profile.c.id == original_profile_id)
                )
                == 1
            )

        with engine.begin() as connection:
            connection.execute(
                sso_user_profile.insert(),
                _profile_values(
                    profile_id=second_profile_id,
                    user_id=user_id,
                    provider="saml",
                    sso_user_id="subject-2",
                    timestamp=timestamp,
                ),
            )

        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                sso_user_profile.insert(),
                _profile_values(
                    profile_id=str(uuid4()),
                    user_id=user_id,
                    provider="saml",
                    sso_user_id="different-subject",
                    timestamp=timestamp,
                ),
            )

        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                sso_user_profile.insert(),
                _profile_values(
                    profile_id=str(uuid4()),
                    user_id=other_user_id,
                    provider="oidc-primary",
                    sso_user_id="subject-1",
                    timestamp=timestamp,
                ),
            )

        with engine.begin() as connection:
            connection.execute(sso_user_profile.delete().where(sso_user_profile.c.id == second_profile_id))
    finally:
        engine.dispose()

    command.downgrade(alembic_cfg, _PRIOR_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.connect() as connection:
            indexes = {index["name"]: index for index in sa.inspect(connection).get_indexes("sso_user_profile")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            assert indexes[_USER_ID_INDEX]["unique"]
            assert _USER_PROVIDER_INDEX not in indexes
            assert indexes[_PROVIDER_IDENTITY_INDEX]["unique"]
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(sso_config).where(sso_config.c.id == config_id)
                )
                == 1
            )
            assert (
                connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(sso_user_profile)
                    .where(sso_user_profile.c.id == original_profile_id)
                )
                == 1
            )
    finally:
        engine.dispose()


def test_sso_multi_identity_downgrade_rejects_users_with_multiple_identities(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    user_id = str(uuid4())
    stored_user_id = UUID(user_id).hex if db_url.startswith("sqlite") else user_id
    config_id = str(uuid4())
    original_profile_id = str(uuid4())
    second_profile_id = str(uuid4())

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
                    "id": stored_user_id,
                    "username": "sso-multi-identity-downgrade-user",
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
                    "provider_name": "Primary OIDC",
                    "enabled": True,
                    "enforce_sso": False,
                    "email_claim": "email",
                    "username_claim": "preferred_username",
                    "user_id_claim": "sub",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sso_user_profile.insert(),
                _profile_values(
                    profile_id=original_profile_id,
                    user_id=stored_user_id,
                    provider="oidc-primary",
                    sso_user_id="subject-1",
                    timestamp=timestamp,
                ),
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_cfg, _REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)
            connection.execute(
                sso_user_profile.insert(),
                _profile_values(
                    profile_id=second_profile_id,
                    user_id=stored_user_id,
                    provider="saml",
                    sso_user_id="subject-2",
                    timestamp=timestamp,
                ),
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match=rf"multiple identities for user_id\(s\): {stored_user_id}"):
        command.downgrade(alembic_cfg, _PRIOR_REVISION)
