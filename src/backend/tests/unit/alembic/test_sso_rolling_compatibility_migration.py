"""Rolling compatibility contract for the SSO expand migrations."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.utils import migration as migration_utils
from sqlalchemy.exc import IntegrityError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "b7d5f9a3c2e4"  # pragma: allowlist secret
_INVARIANT_PRIOR_REVISION = "f0a1b2c3d4e5"  # pragma: allowlist secret
_HEAD_REVISION = "8d9e0f1a2b3c"  # pragma: allowlist secret
_TEST_ENCRYPTED_SECRET = "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:AAAAAAAAAAAAAAAA:BBBBBBBBBBBBBBBBBBBBBBBB"  # noqa: S105  # pragma: allowlist secret
_TEST_PLAINTEXT_SECRET = "plaintext-secret"  # noqa: S105  # pragma: allowlist secret
_TEST_INVALID_BASE64_ENVELOPE = (  # pragma: allowlist secret
    "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:!!!!!!!!!!!!!!!!:!!!!!!!!!!!!!!!!!!!!!!"
)
_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
_INITIAL_MIGRATION = importlib.import_module(
    "langflow.alembic.versions.b1c2d3e4f5a6_add_sso_plugin_tables_sso_user_profile_"
)
_IDENTITY_MIGRATION = importlib.import_module(
    "langflow.alembic.versions.e9f2a3b4c5d6_allow_multiple_sso_identities_per_user"
)
_INVARIANT_MIGRATION = importlib.import_module("langflow.alembic.versions.7c8e9f0a1b2d_add_sso_config_invariant_checks")
_HEAD_MIGRATION = importlib.import_module("langflow.alembic.versions.8d9e0f1a2b3c_complete_sso_expand_compatibility")


def _legacy_config_values(
    *,
    config_id: str,
    provider: str,
    provider_name: str,
    timestamp: datetime,
    enabled: bool = True,
) -> dict:
    return {
        "id": config_id,
        "provider": provider,
        "provider_name": provider_name,
        "enabled": enabled,
        "enforce_sso": False,
        "client_secret_encrypted": None,
        "client_id": None,
        "discovery_url": None,
        "redirect_uri": None,
        "scopes": None,
        "token_endpoint": None,
        "authorization_endpoint": None,
        "jwks_uri": None,
        "issuer": None,
        "email_claim": "email",
        "username_claim": "preferred_username",
        "user_id_claim": "sub",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _oidc_settings(*, discovery_url: str = "https://idp.example.com/.well-known/openid-configuration") -> dict:
    return {
        "protocol": "oidc",
        "discovery_url": discovery_url,
        "redirect_uri": "/api/v1/login/callback",
        "scopes": "openid email profile",
        "token_endpoint": None,
        "authorization_endpoint": None,
        "jwks_uri": None,
        "issuer": "https://idp.example.com",
        "client_id": "client-id",
    }


@pytest.mark.parametrize("invariant_checks_installed", [True, False], ids=["complete-schema", "missing-checks"])
def test_sso_migration_replay_preserves_installed_sqlite_triggers(invariant_checks_installed):
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            # Some SQLite builds default to legacy rename behavior, which hides
            # dangling cross-table trigger references during a batch rebuild.
            connection.exec_driver_sql("PRAGMA legacy_alter_table=OFF")
            metadata = sa.MetaData()
            sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
            metadata.create_all(connection)
            _INITIAL_MIGRATION.upgrade()
            _IDENTITY_MIGRATION.upgrade()
            if invariant_checks_installed:
                _INVARIANT_MIGRATION.upgrade()
            else:
                # A partially restored schema also needs the invariant migration
                # to rebuild the table while the newer compatibility triggers exist.
                _INVARIANT_MIGRATION._create_slug_trigger(connection)
            _HEAD_MIGRATION.upgrade()

            trigger_query = sa.text(
                "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
                "AND tbl_name IN ('sso_config', 'sso_settings')"
            )
            original_triggers = dict(connection.execute(trigger_query).all())
            assert set(original_triggers) == {
                "trg_sso_config_slug_immutable",
                "trg_sso_config_expand_compat_insert",
                "trg_sso_config_expand_compat_update",
                "trg_sso_config_expand_compat_enforce",
                "trg_sso_settings_expand_compat_enforce",
            }

            timestamp = datetime.now(timezone.utc)
            config_id = str(uuid4())
            config = sa.Table("sso_config", sa.MetaData(), autoload_with=connection)
            settings = sa.Table("sso_settings", sa.MetaData(), autoload_with=connection)
            connection.execute(
                config.insert(),
                {
                    **_legacy_config_values(
                        config_id=config_id,
                        provider="oidc",
                        provider_name="Existing OIDC",
                        timestamp=timestamp,
                    ),
                    "client_secret_encrypted": _TEST_ENCRYPTED_SECRET,
                    **{key: value for key, value in _oidc_settings().items() if key != "protocol"},
                },
            )
            original_row = dict(connection.execute(sa.select(config)).mappings().one())

            for migration in (_INITIAL_MIGRATION, _IDENTITY_MIGRATION, _INVARIANT_MIGRATION, _HEAD_MIGRATION):
                migration.upgrade()
                # Check each revision so the final migration cannot hide triggers
                # lost during an earlier table rebuild by reinstalling them.
                assert dict(connection.execute(trigger_query).all()) == original_triggers
                assert dict(connection.execute(sa.select(config)).mappings().one()) == original_row

            connection.execute(settings.update().where(settings.c.id == 1).values(enforce_sso=True))
            assert connection.scalar(sa.select(config.c.enforce_sso).where(config.c.id == config_id))

            inserted_id = str(uuid4())
            connection.execute(
                config.insert(),
                _legacy_config_values(
                    config_id=inserted_id,
                    provider="saml",
                    provider_name="Inserted After Replay",
                    timestamp=timestamp,
                ),
            )
            inserted = connection.execute(sa.select(config).where(config.c.id == inserted_id)).mappings().one()
            assert inserted["slug"] == f"sso-{UUID(inserted_id).hex}"
            assert inserted["display_name"] == "Inserted After Replay"
            assert inserted["protocol"] == "saml"
            assert inserted["provider_settings"]["protocol"] == "saml"
            assert inserted["enforce_sso"]

            changed_settings = {**_oidc_settings(), "issuer": "https://after-replay.example.com"}
            connection.execute(
                config.update().where(config.c.id == config_id).values(provider_settings=changed_settings)
            )
            assert (
                connection.scalar(sa.select(config.c.issuer).where(config.c.id == config_id))
                == changed_settings["issuer"]
            )

            connection.execute(config.update().where(config.c.id == config_id).values(enforce_sso=False))
            assert not connection.scalar(sa.select(settings.c.enforce_sso).where(settings.c.id == 1))
            assert not any(connection.execute(sa.select(config.c.enforce_sso)).scalars())
            with pytest.raises(IntegrityError, match=r"SSOConfig\.slug is immutable"):
                connection.execute(config.update().where(config.c.id == config_id).values(slug="changed-slug"))
    finally:
        engine.dispose()


def test_sso_failed_sqlite_rebuild_restores_schema_data_and_triggers():
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)) as operations:
            connection.exec_driver_sql("PRAGMA legacy_alter_table=OFF")
            metadata = sa.MetaData()
            sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
            metadata.create_all(connection)
            for migration in (_INITIAL_MIGRATION, _IDENTITY_MIGRATION, _INVARIANT_MIGRATION, _HEAD_MIGRATION):
                migration.upgrade()

            config = sa.Table("sso_config", sa.MetaData(), autoload_with=connection)
            connection.execute(
                config.insert(),
                _legacy_config_values(
                    config_id=str(uuid4()),
                    provider="saml",
                    provider_name="Existing SAML",
                    timestamp=datetime.now(timezone.utc),
                ),
            )
            original_row = dict(connection.execute(sa.select(config)).mappings().one())
            schema_query = sa.text(
                "SELECT name, sql FROM sqlite_master WHERE tbl_name IN ('sso_config', 'sso_settings') ORDER BY name"
            )
            original_schema = connection.execute(schema_query).all()

            with (
                pytest.raises(IntegrityError, match="ck_sso_config_disabled"),
                migration_utils.preserve_sqlite_triggers(connection, "sso_config", "sso_settings"),
                operations.batch_alter_table("sso_config", recreate="always") as batch,
            ):
                batch.create_check_constraint("ck_sso_config_disabled", "enabled = 0")

            assert connection.execute(schema_query).all() == original_schema
            assert dict(connection.execute(sa.select(config)).mappings().one()) == original_row
            assert not sa.inspect(connection).has_table("_alembic_tmp_sso_config")
            settings = sa.Table("sso_settings", sa.MetaData(), autoload_with=connection)
            connection.execute(settings.update().where(settings.c.id == 1).values(enforce_sso=True))
            assert connection.scalar(sa.select(config.c.enforce_sso))
    finally:
        engine.dispose()


def test_sso_protocol_preflight_is_schema_aware_and_rejects_unsupported_legacy_state(db_url):  # noqa: F811
    engine = sa.create_engine(_engine_url(db_url))
    try:
        typed_metadata = sa.MetaData()
        typed_config = sa.Table(
            "sso_config",
            typed_metadata,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("protocol", sa.String()),
            sa.Column("provider_settings", sa.JSON()),
        )
        typed_metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                typed_config.insert(),
                {"id": "typed-only", "protocol": "oidc", "provider_settings": {"protocol": "oidc"}},
            )
            _INVARIANT_MIGRATION._raise_for_protocol_mismatches(
                connection,
                _INVARIANT_MIGRATION._config_table(),
            )
        typed_metadata.drop_all(engine)

        legacy_metadata = sa.MetaData()
        legacy_config = sa.Table(
            "sso_config",
            legacy_metadata,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("protocol", sa.String()),
            sa.Column("provider", sa.String()),
            sa.Column("provider_settings", sa.JSON()),
        )
        legacy_metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                legacy_config.insert(),
                {"id": "unsupported-legacy", "protocol": None, "provider": "custom", "provider_settings": None},
            )
            with pytest.raises(RuntimeError, match="unsupported-legacy"):
                _INVARIANT_MIGRATION._raise_for_protocol_mismatches(
                    connection,
                    _INVARIANT_MIGRATION._config_table(),
                )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("client_secret", "complete", "expected_enabled", "expected_secret"),
    [
        pytest.param(None, True, False, None, id="missing-secret"),
        pytest.param(_TEST_PLAINTEXT_SECRET, True, False, None, id="plaintext-secret"),
        pytest.param(_TEST_INVALID_BASE64_ENVELOPE, True, False, None, id="invalid-base64-envelope"),
        pytest.param(
            _TEST_ENCRYPTED_SECRET,
            False,
            False,
            _TEST_ENCRYPTED_SECRET,
            id="valid-envelope-incomplete-settings",
        ),
        pytest.param(_TEST_ENCRYPTED_SECRET, True, True, _TEST_ENCRYPTED_SECRET, id="complete-valid"),
    ],
)
def test_sso_head_normalizes_pending_n_minus_one_insert(
    db_url,  # noqa: F811
    client_secret,
    complete,
    expected_enabled,
    expected_secret,
):
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _INVARIANT_PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    config_id = str(uuid4())
    expected_settings = _oidc_settings()
    if not complete:
        expected_settings = {**expected_settings, "client_id": None, "discovery_url": None}

    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            sso_config = sa.Table("sso_config", sa.MetaData(), autoload_with=connection)
            connection.execute(
                sso_config.insert(),
                {
                    **_legacy_config_values(
                        config_id=config_id,
                        provider="oidc",
                        provider_name="Pending N-1 OIDC",
                        timestamp=timestamp,
                    ),
                    "client_secret_encrypted": client_secret,
                    **{key: value for key, value in expected_settings.items() if key != "protocol"},
                },
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_cfg, _HEAD_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            sso_config = sa.Table("sso_config", sa.MetaData(), autoload_with=connection)
            row = connection.execute(sa.select(sso_config).where(sso_config.c.id == config_id)).mappings().one()
            assert row["slug"] == f"sso-{UUID(config_id).hex}"
            assert row["display_name"] == "Pending N-1 OIDC"
            assert row["provider"] == "oidc"
            assert row["protocol"] == "oidc"
            assert row["provider_settings"] == expected_settings
            assert row["enabled"] is expected_enabled
            assert row["client_secret_encrypted"] == expected_secret
    finally:
        engine.dispose()


def test_sso_expand_keeps_n_and_n_minus_one_writes_coherent(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    timestamp = datetime.now(timezone.utc)
    user_id = str(uuid4())
    profile_id = str(uuid4())
    saml_config_id = str(uuid4())
    ldap_config_id = str(uuid4())
    malformed_oidc_id = str(uuid4())

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
                    "username": "sso-rolling-user",
                    "password": _TEST_PASSWORD,
                    "is_active": True,
                    "is_superuser": False,
                    "create_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sso_config.insert(),
                [
                    {
                        **_legacy_config_values(
                            config_id=saml_config_id,
                            provider="saml",
                            provider_name="Legacy SAML",
                            timestamp=timestamp,
                        ),
                        "issuer": "https://saml.example.com",
                    },
                    {
                        **_legacy_config_values(
                            config_id=ldap_config_id,
                            provider="ldap",
                            provider_name="Legacy LDAP",
                            timestamp=timestamp,
                        ),
                        "discovery_url": "https://ldap.example.com",
                    },
                    {
                        **_legacy_config_values(
                            config_id=malformed_oidc_id,
                            provider="oidc",
                            provider_name="Malformed OIDC",
                            timestamp=timestamp,
                        ),
                        "client_secret_encrypted": _TEST_ENCRYPTED_SECRET,
                        "client_id": "client-id",
                        "discovery_url": "http://example.com:bad",
                    },
                ],
            )
            connection.execute(
                sso_user_profile.insert(),
                {
                    "id": profile_id,
                    "user_id": user_id,
                    "sso_provider": "Legacy SAML",
                    "sso_user_id": "subject-1",
                    "email": "user@example.com",
                    "sso_last_login_at": None,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_cfg, _HEAD_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        with engine.begin() as connection:
            inspector = sa.inspect(connection)
            columns = {column["name"]: column for column in inspector.get_columns("sso_config")}
            sso_config = sa.Table("sso_config", metadata, autoload_with=connection)
            sso_settings = sa.Table("sso_settings", metadata, autoload_with=connection)
            sso_user_profile = sa.Table("sso_user_profile", metadata, autoload_with=connection)

            assert {
                "provider",
                "provider_name",
                "enforce_sso",
                "slug",
                "display_name",
                "protocol",
                "provider_settings",
            } <= columns.keys()
            assert all(
                columns[name]["nullable"]
                for name in ("provider", "provider_name", "slug", "display_name", "protocol", "provider_settings")
            )
            if connection.dialect.name == "postgresql":
                assert columns["created_at"]["type"].timezone
                assert columns["updated_at"]["type"].timezone

            historical_rows = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id.in_((saml_config_id, ldap_config_id))))
                .mappings()
                .all()
            )
            assert {row["protocol"] for row in historical_rows} == {"saml", "ldap"}
            assert all(row["enabled"] for row in historical_rows)
            assert {row["provider_settings"]["protocol"] for row in historical_rows} == {"saml", "ldap"}
            assert not connection.scalar(sa.select(sso_config.c.enabled).where(sso_config.c.id == malformed_oidc_id))
            assert (
                connection.scalar(sa.select(sso_user_profile.c.sso_provider).where(sso_user_profile.c.id == profile_id))
                == "Legacy SAML"
            )

            # display_name is mutable presentation data in N, while the
            # released provider_name remains the EXPAND identity key used by
            # N-1 profiles.
            connection.execute(
                sso_config.update().where(sso_config.c.id == saml_config_id).values(display_name="Renamed SAML")
            )
            renamed_saml = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == saml_config_id)).mappings().one()
            )
            assert renamed_saml["provider_name"] == "Legacy SAML"
            assert (
                connection.scalar(sa.select(sso_user_profile.c.sso_provider).where(sso_user_profile.c.id == profile_id))
                == "Legacy SAML"
            )

            # N-1 INSERT: released scalar fields populate the N representation.
            legacy_oidc_id = str(uuid4())
            legacy_oidc_settings = _oidc_settings()
            connection.execute(
                sso_config.insert(),
                {
                    **_legacy_config_values(
                        config_id=legacy_oidc_id,
                        provider="oidc",
                        provider_name="Rolling Legacy OIDC",
                        timestamp=timestamp,
                    ),
                    "client_secret_encrypted": _TEST_ENCRYPTED_SECRET,
                    **{key: value for key, value in legacy_oidc_settings.items() if key != "protocol"},
                },
            )
            legacy_oidc = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == legacy_oidc_id)).mappings().one()
            )
            assert legacy_oidc["slug"] == f"sso-{UUID(legacy_oidc_id).hex}"
            assert legacy_oidc["display_name"] == "Rolling Legacy OIDC"
            assert legacy_oidc["protocol"] == "oidc"
            assert legacy_oidc["provider_settings"] == legacy_oidc_settings

            # N INSERT: typed fields populate the released scalar representation
            # and DB defaults satisfy columns the new model no longer maps.
            typed_oidc_id = str(uuid4())
            typed_settings = _oidc_settings(discovery_url="https://typed.example.com/.well-known/openid-configuration")
            connection.execute(
                sso_config.insert(),
                {
                    "id": typed_oidc_id,
                    "slug": "sso-typed-writer",
                    "display_name": "Typed OIDC",
                    "protocol": "oidc",
                    "enabled": True,
                    "sort_order": 5,
                    "client_secret_encrypted": _TEST_ENCRYPTED_SECRET,
                    "provider_settings": typed_settings,
                    "email_claim": "email",
                    "username_claim": "preferred_username",
                    "user_id_claim": "sub",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            typed_oidc = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == typed_oidc_id)).mappings().one()
            )
            assert typed_oidc["provider"] == "oidc"
            assert typed_oidc["provider_name"] == "Typed OIDC"
            assert typed_oidc["discovery_url"] == typed_settings["discovery_url"]
            assert not typed_oidc["enforce_sso"]

            # Regression: a single N-1 update can change the protocol and a
            # scalar setting without the trigger overwriting that setting from
            # stale JSON.
            changed_discovery_url = "https://saml-rolling.example.com/metadata"
            connection.execute(
                sso_config.update()
                .where(sso_config.c.id == legacy_oidc_id)
                .values(provider="saml", discovery_url=changed_discovery_url)
            )
            updated_legacy = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == legacy_oidc_id)).mappings().one()
            )
            assert updated_legacy["protocol"] == "saml"
            assert updated_legacy["provider_settings"]["protocol"] == "saml"
            assert updated_legacy["provider_settings"]["discovery_url"] == changed_discovery_url

            # N UPDATE keeps the released fields usable by an old process.
            changed_typed_settings = {**typed_settings, "issuer": "https://issuer.example.com"}
            connection.execute(
                sso_config.update()
                .where(sso_config.c.id == typed_oidc_id)
                .values(display_name="Renamed Typed OIDC", provider_settings=changed_typed_settings)
            )
            updated_typed = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == typed_oidc_id)).mappings().one()
            )
            assert updated_typed["provider_name"] == "Typed OIDC"
            assert updated_typed["issuer"] == "https://issuer.example.com"

            # SQLite evaluates CHECK constraints before its AFTER UPDATE
            # compatibility trigger. Supported temporary mismatches must reach
            # the trigger, which then applies the same deterministic precedence
            # as PostgreSQL's BEFORE trigger.
            connection.execute(
                sso_config.update().where(sso_config.c.id == typed_oidc_id).values(enabled=False, protocol="saml")
            )
            protocol_only_update = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == typed_oidc_id)).mappings().one()
            )
            assert protocol_only_update["provider"] == "saml"
            assert protocol_only_update["provider_settings"]["protocol"] == "saml"

            ldap_settings = {**changed_typed_settings, "protocol": "ldap"}
            connection.execute(
                sso_config.update().where(sso_config.c.id == typed_oidc_id).values(provider_settings=ldap_settings)
            )
            settings_only_update = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == typed_oidc_id)).mappings().one()
            )
            assert settings_only_update["protocol"] == "ldap"
            assert settings_only_update["provider"] == "ldap"

            conflicting_settings = {
                **changed_typed_settings,
                "protocol": "ldap",
                "issuer": "https://conflict.example.com",
            }
            connection.execute(
                sso_config.update()
                .where(sso_config.c.id == typed_oidc_id)
                .values(protocol="saml", provider_settings=conflicting_settings)
            )
            conflicting_update = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == typed_oidc_id)).mappings().one()
            )
            assert conflicting_update["protocol"] == "saml"
            assert conflicting_update["provider"] == "saml"
            assert conflicting_update["provider_settings"]["protocol"] == "saml"
            assert conflicting_update["provider_settings"]["issuer"] == "https://conflict.example.com"

            # An explicit N-1 key rename still mirrors to N presentation data;
            # released plugin code owns any corresponding profile maintenance.
            connection.execute(
                sso_config.update().where(sso_config.c.id == legacy_oidc_id).values(provider_name="Legacy Renamed")
            )
            assert (
                connection.scalar(sa.select(sso_config.c.display_name).where(sso_config.c.id == legacy_oidc_id))
                == "Legacy Renamed"
            )

            # Old and new enforcement writers converge on one instance value.
            connection.execute(sso_config.update().where(sso_config.c.id == typed_oidc_id).values(enforce_sso=True))
            assert connection.scalar(sa.select(sso_settings.c.enforce_sso).where(sso_settings.c.id == 1))
            assert all(connection.execute(sa.select(sso_config.c.enforce_sso)).scalars())

            inserted_while_enforced_id = str(uuid4())
            connection.execute(
                sso_config.insert(),
                _legacy_config_values(
                    config_id=inserted_while_enforced_id,
                    provider="saml",
                    provider_name="Inserted While Enforced",
                    timestamp=timestamp,
                    enabled=True,
                ),
            )
            assert connection.scalar(
                sa.select(sso_config.c.enforce_sso).where(sso_config.c.id == inserted_while_enforced_id)
            )
            inserted_saml = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == inserted_while_enforced_id))
                .mappings()
                .one()
            )
            assert inserted_saml["protocol"] == "saml"
            assert inserted_saml["provider_settings"]["protocol"] == "saml"

            connection.execute(sso_settings.update().where(sso_settings.c.id == 1).values(enforce_sso=False))
            assert not any(connection.execute(sa.select(sso_config.c.enforce_sso)).scalars())

            inserted_ldap_id = str(uuid4())
            connection.execute(
                sso_config.insert(),
                _legacy_config_values(
                    config_id=inserted_ldap_id,
                    provider="ldap",
                    provider_name="Rolling LDAP",
                    timestamp=timestamp,
                    enabled=True,
                ),
            )
            inserted_ldap = (
                connection.execute(sa.select(sso_config).where(sso_config.c.id == inserted_ldap_id)).mappings().one()
            )
            assert inserted_ldap["protocol"] == "ldap"
            assert inserted_ldap["provider_settings"]["protocol"] == "ldap"

        # Security boundary: N-1 plaintext secret writes are intentionally not
        # compatible. They fail atomically instead of reintroducing plaintext.
        plaintext_update = (
            sso_config.update()
            .where(sso_config.c.id == typed_oidc_id)
            .values(client_secret_encrypted=_TEST_PLAINTEXT_SECRET)
        )
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(plaintext_update)
        with engine.connect() as connection:
            sso_config = sa.Table("sso_config", sa.MetaData(), autoload_with=connection)
            assert (
                connection.scalar(
                    sa.select(sso_config.c.client_secret_encrypted).where(sso_config.c.id == typed_oidc_id)
                )
                == _TEST_ENCRYPTED_SECRET
            )
    finally:
        engine.dispose()

    command.downgrade(alembic_cfg, "7c8e9f0a1b2d")  # pragma: allowlist secret
    if db_url.startswith("postgresql"):
        engine = sa.create_engine(_engine_url(db_url))
        try:
            with engine.connect() as connection:
                columns = {column["name"]: column for column in sa.inspect(connection).get_columns("sso_config")}
                assert not columns["created_at"]["type"].timezone
                assert not columns["updated_at"]["type"].timezone
        finally:
            engine.dispose()


def test_sso_timestamp_conversion_uses_utc_in_both_directions(monkeypatch):
    calls: list[str] = []
    fake_conn = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    monkeypatch.setattr(_HEAD_MIGRATION.migration, "table_exists", lambda *_args: True)
    monkeypatch.setattr(_HEAD_MIGRATION, "_column_names", lambda *_args: {"created_at", "updated_at"})
    monkeypatch.setattr(_HEAD_MIGRATION.op, "execute", lambda statement: calls.append(str(statement)))

    _HEAD_MIGRATION._convert_timestamps(fake_conn, timezone_aware=True)
    assert len(calls) == 2
    assert all("TYPE TIMESTAMP WITH TIME ZONE" in statement for statement in calls)
    assert all("AT TIME ZONE 'UTC'" in statement for statement in calls)

    calls.clear()
    _HEAD_MIGRATION._convert_timestamps(fake_conn, timezone_aware=False)
    assert len(calls) == 2
    assert all("TYPE TIMESTAMP WITHOUT TIME ZONE" in statement for statement in calls)
    assert all("AT TIME ZONE 'UTC'" in statement for statement in calls)
