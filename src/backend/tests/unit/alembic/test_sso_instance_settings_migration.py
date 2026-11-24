"""Migration contract for multi-connection and instance-level SSO fields."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import command

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "b7d5f9a3c2e4"  # pragma: allowlist secret
_REVISION = "e9f2a3b4c5d6"  # pragma: allowlist secret
_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


def _config_values(
    *,
    config_id: str,
    provider_name: str,
    enforce_sso: bool,
    timestamp: datetime,
    enabled: bool = True,
) -> dict:
    return {
        "id": config_id,
        "provider": "oidc",
        "provider_name": provider_name,
        "enabled": enabled,
        "enforce_sso": enforce_sso,
        "email_claim": "email",
        "username_claim": "preferred_username",
        "user_id_claim": "sub",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_sso_instance_fields_upgrade_and_downgrade_preserve_seeded_rows(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    profile_user_id = str(uuid4())
    updater_user_id = str(uuid4())
    first_config_id = str(UUID(int=1))
    second_config_id = str(UUID(int=2))
    profile_id = str(uuid4())

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
                        "id": profile_user_id,
                        "username": "sso-instance-profile-user",
                        "password": _TEST_PASSWORD,
                        "is_active": True,
                        "is_superuser": False,
                        "create_at": timestamp,
                        "updated_at": timestamp,
                    },
                    {
                        "id": updater_user_id,
                        "username": "sso-instance-updater",
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
                [
                    _config_values(
                        config_id=second_config_id,
                        provider_name="Second OIDC",
                        enforce_sso=False,
                        timestamp=timestamp,
                    ),
                    _config_values(
                        config_id=first_config_id,
                        provider_name="First OIDC",
                        enforce_sso=True,
                        timestamp=timestamp,
                    ),
                ],
            )
            connection.execute(
                sso_user_profile.insert(),
                {
                    "id": profile_id,
                    "user_id": profile_user_id,
                    "sso_provider": "first-oidc",
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
            config_columns = {column["name"] for column in inspector.get_columns("sso_config")}
            foreign_keys = inspector.get_foreign_keys("sso_config")
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_settings = sa.Table("sso_settings", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            assert {"sort_order", "updated_by", "enforce_sso"} <= config_columns
            assert any(
                foreign_key["constrained_columns"] == ["updated_by"]
                and foreign_key["referred_table"] == "user"
                and foreign_key["options"].get("ondelete") == "SET NULL"
                for foreign_key in foreign_keys
            )

            settings_rows = connection.execute(sa.select(sso_settings)).mappings().all()
            assert settings_rows == [{"id": 1, "enforce_sso": True}]

            ordered_configs = (
                connection.execute(
                    sa.select(sso_config.c.id, sso_config.c.enabled, sso_config.c.sort_order).order_by(
                        sso_config.c.sort_order,
                        sso_config.c.id,
                    )
                )
                .mappings()
                .all()
            )
            assert [str(row["id"]) for row in ordered_configs] == [first_config_id, second_config_id]
            assert [row["sort_order"] for row in ordered_configs] == [0, 1]
            assert all(row["enabled"] for row in ordered_configs)
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
            inspector = sa.inspect(connection)
            config_columns = {column["name"] for column in inspector.get_columns("sso_config")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            assert "enforce_sso" in config_columns
            assert {"sort_order", "updated_by"}.isdisjoint(config_columns)
            assert not inspector.has_table("sso_settings")
            assert connection.execute(sa.select(sso_config.c.enforce_sso)).scalars().all() == [True, True]
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(sso_user_profile).where(sso_user_profile.c.id == profile_id)
                )
                == 1
            )
    finally:
        engine.dispose()


def test_sso_instance_fields_upgrade_ignores_disabled_enforce_sso(db_url):  # noqa: F811
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
                _config_values(
                    config_id=config_id,
                    provider_name="Disabled OIDC",
                    enforce_sso=True,
                    timestamp=timestamp,
                    enabled=False,
                ),
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_cfg, _REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            sso_settings = sa.Table("sso_settings", metadata, autoload_with=connection)
            settings_rows = connection.execute(sa.select(sso_settings)).mappings().all()
            assert settings_rows == [{"id": 1, "enforce_sso": False}]
    finally:
        engine.dispose()
