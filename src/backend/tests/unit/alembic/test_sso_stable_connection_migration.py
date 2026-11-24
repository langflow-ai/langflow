"""Migration contract for stable SSO connection identity."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "b7d5f9a3c2e4"  # pragma: allowlist secret
_REVISION = "e9f2a3b4c5d6"  # pragma: allowlist secret
_SLUG_INDEX = "uq_sso_config_slug"
_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


def test_sso_connection_identity_upgrade_and_downgrade_preserve_seeded_rows(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    user_id = str(uuid4())
    slug_profile_user_id = str(uuid4())
    config_id = str(uuid4())
    profile_id = str(uuid4())
    slug_profile_id = str(uuid4())
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
                [
                    {
                        "id": user_id,
                        "username": "sso-stable-identity-user",
                        "password": _TEST_PASSWORD,
                        "is_active": True,
                        "is_superuser": False,
                        "create_at": timestamp,
                        "updated_at": timestamp,
                    },
                    {
                        "id": slug_profile_user_id,
                        "username": "sso-slug-identity-user",
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
            assert "provider_name" in columns
            assert columns["slug"]["nullable"]
            assert columns["display_name"]["nullable"]
            assert columns["provider_name"]["nullable"]
            assert indexes[_SLUG_INDEX]["unique"]
            assert config_row["slug"] == expected_slug
            assert config_row["display_name"] == "Primary OIDC"
            assert config_row["provider_name"] == "Primary OIDC"
            # EXPAND must not re-key this shared field while N-1 services still
            # resolve profiles by the legacy provider identifier.
            assert profile_row["sso_provider"] == "Primary OIDC"

            # N is allowed to create slug-backed identities during EXPAND.
            connection.execute(
                sso_user_profile.insert(),
                {
                    "id": slug_profile_id,
                    "user_id": slug_profile_user_id,
                    "sso_provider": expected_slug,
                    "sso_user_id": "subject-slug",
                    "email": "slug-user@example.com",
                    "sso_last_login_at": None,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
    finally:
        engine.dispose()

    # Downgrade must fail before any non-transactional SQLite DDL instead of
    # guessing how to rewrite identity keys and stranding or misbinding users.
    with pytest.raises(RuntimeError, match="Cannot downgrade SSO EXPAND"):
        command.downgrade(alembic_cfg, _PRIOR_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            columns = {column["name"] for column in sa.inspect(connection).get_columns("sso_config")}
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)
            assert {"slug", "sort_order", "updated_by"} <= columns
            assert (
                connection.scalar(
                    sa.select(sso_user_profile.c.sso_provider).where(sso_user_profile.c.id == slug_profile_id)
                )
                == expected_slug
            )
            # Explicitly verified remediation lets the downgrade proceed.
            connection.execute(
                sso_user_profile.update()
                .where(sso_user_profile.c.id == slug_profile_id)
                .values(sso_provider="Primary OIDC")
            )
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
            slug_profile_row = (
                connection.execute(sa.select(sso_user_profile).where(sso_user_profile.c.id == slug_profile_id))
                .mappings()
                .one()
            )

            assert "provider_name" in columns
            assert {"slug", "display_name"}.isdisjoint(columns)
            assert _SLUG_INDEX not in indexes
            assert config_row["provider_name"] == "Primary OIDC"
            assert profile_row["sso_provider"] == "Primary OIDC"
            assert slug_profile_row["sso_provider"] == "Primary OIDC"
    finally:
        engine.dispose()


def test_sso_connection_identity_upgrade_preserves_duplicate_provider_names(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    config_ids = [str(uuid4()), str(uuid4())]

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            connection.execute(
                sso_config.insert(),
                [
                    {
                        "id": config_ids[0],
                        "provider": "oidc",
                        "provider_name": "Shared OIDC",
                        "enabled": True,
                        "enforce_sso": False,
                        "email_claim": "email",
                        "username_claim": "preferred_username",
                        "user_id_claim": "sub",
                        "created_at": timestamp,
                        "updated_at": timestamp,
                    },
                    {
                        "id": config_ids[1],
                        "provider": "oidc",
                        "provider_name": "Shared OIDC",
                        "enabled": True,
                        "enforce_sso": False,
                        "email_claim": "email",
                        "username_claim": "preferred_username",
                        "user_id_claim": "sub",
                        "created_at": timestamp,
                        "updated_at": timestamp,
                    },
                ],
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_cfg, _REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            sso_config = sa.Table("sso_config", sa.MetaData(), autoload_with=connection)
            rows = (
                connection.execute(
                    sa.select(sso_config).where(sso_config.c.id.in_(config_ids)).order_by(sso_config.c.id)
                )
                .mappings()
                .all()
            )
            assert len(rows) == 2
            assert {row["provider_name"] for row in rows} == {"Shared OIDC"}
            assert len({row["slug"] for row in rows}) == 2
    finally:
        engine.dispose()
