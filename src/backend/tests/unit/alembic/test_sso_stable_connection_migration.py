"""Migration contract for stable SSO connection identity."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import command

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "b7d5f9a3c2e4"  # pragma: allowlist secret
_REVISION = "e8f1a2b3c4d5"  # pragma: allowlist secret
_SLUG_INDEX = "uq_sso_config_slug"
_TEST_PASSWORD = "hashed"  # noqa: S105


def test_sso_connection_identity_upgrade_and_downgrade_preserve_seeded_rows(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    user_id = str(uuid4())
    config_id = str(uuid4())
    profile_id = str(uuid4())
    expected_slug = f"sso-{UUID(config_id).hex}"

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
                    "username": "sso-stable-identity-user",
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
                {
                    "id": profile_id,
                    "user_id": user_id,
                    "sso_provider": "Primary OIDC",
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
        with engine.begin() as connection:
            inspector = sa.inspect(connection)
            columns = {column["name"]: column for column in inspector.get_columns("sso_config")}
            indexes = {index["name"]: index for index in inspector.get_indexes("sso_config")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            config_row = connection.execute(sa.select(sso_config).where(sso_config.c.id == config_id)).mappings().one()
            profile_row = (
                connection.execute(sa.select(sso_user_profile).where(sso_user_profile.c.id == profile_id))
                .mappings()
                .one()
            )

            assert {"slug", "display_name"} <= columns.keys()
            assert "provider_name" not in columns
            assert not columns["slug"]["nullable"]
            assert not columns["display_name"]["nullable"]
            assert indexes[_SLUG_INDEX]["unique"]
            assert config_row["slug"] == expected_slug
            assert config_row["display_name"] == "Primary OIDC"
            assert profile_row["sso_provider"] == config_row["slug"]

            connection.execute(
                sso_config.update().where(sso_config.c.id == config_id).values(display_name="Renamed OIDC")
            )
            resolved_config = (
                connection.execute(sa.select(sso_config).where(sso_config.c.slug == profile_row["sso_provider"]))
                .mappings()
                .one()
            )
            assert resolved_config["display_name"] == "Renamed OIDC"
    finally:
        engine.dispose()

    command.downgrade(alembic_cfg, _PRIOR_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            columns = {column["name"]: column for column in inspector.get_columns("sso_config")}
            indexes = {index["name"]: index for index in inspector.get_indexes("sso_config")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            config_row = connection.execute(sa.select(sso_config).where(sso_config.c.id == config_id)).mappings().one()
            profile_row = (
                connection.execute(sa.select(sso_user_profile).where(sso_user_profile.c.id == profile_id))
                .mappings()
                .one()
            )

            assert "provider_name" in columns
            assert {"slug", "display_name"}.isdisjoint(columns)
            assert _SLUG_INDEX not in indexes
            assert config_row["provider_name"] == "Renamed OIDC"
            assert profile_row["sso_provider"] == "Renamed OIDC"
    finally:
        engine.dispose()
