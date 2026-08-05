"""add database enforcement for SSO configuration invariants

Revision ID: 7c8e9f0a1b2d
Revises: f0a1b2c3d4e5
Create Date: 2026-08-04

Phase: EXPAND
"""

from collections.abc import Sequence
from urllib.parse import urlsplit

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "7c8e9f0a1b2d"  # pragma: allowlist secret
down_revision: str | None = "f0a1b2c3d4e5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIG_TABLE = "sso_config"
_PROTOCOL_CHECK = "ck_sso_config_protocol_consistency"
_ENABLED_CHECK = "ck_sso_config_enabled_complete"
_SLUG_TRIGGER = "trg_sso_config_slug_immutable"
_POSTGRES_TRIGGER_FUNCTION = "prevent_sso_config_slug_update"
_REMOTE_URL_FIELDS = (
    "discovery_url",
    "token_endpoint",
    "authorization_endpoint",
    "jwks_uri",
    "issuer",
)


def _config_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        _CONFIG_TABLE,
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("slug", sa.String()),
        sa.Column("protocol", sa.String()),
        sa.Column("enabled", sa.Boolean()),
        sa.Column("client_secret_encrypted", sa.String()),
        sa.Column("provider_settings", sa.JSON()),
    )


def _nonblank_json_string(json_column: sa.Column, key: str) -> sa.ColumnElement[bool]:
    value = json_column[key].as_string()
    return sa.and_(value.is_not(None), sa.func.length(sa.func.trim(value)) > 0)


def _http_json_url_or_null(json_column: sa.Column, key: str) -> sa.ColumnElement[bool]:
    value = json_column[key].as_string()
    normalized = sa.func.lower(value)
    return sa.or_(value.is_(None), normalized.like("http://%"), normalized.like("https://%"))


def _protocol_check(table: sa.Table) -> sa.ColumnElement[bool]:
    settings_protocol = table.c.provider_settings["protocol"].as_string()
    return sa.and_(
        table.c.protocol == "oidc",
        settings_protocol.is_not(None),
        settings_protocol == table.c.protocol,
    )


def _enabled_check(table: sa.Table) -> sa.ColumnElement[bool]:
    settings = table.c.provider_settings
    return sa.or_(
        table.c.enabled.is_(False),
        sa.and_(
            table.c.client_secret_encrypted.is_not(None),
            _nonblank_json_string(settings, "client_id"),
            sa.or_(
                _nonblank_json_string(settings, "discovery_url"),
                sa.and_(
                    _nonblank_json_string(settings, "authorization_endpoint"),
                    _nonblank_json_string(settings, "token_endpoint"),
                    _nonblank_json_string(settings, "jwks_uri"),
                ),
            ),
            *(_http_json_url_or_null(settings, key) for key in _REMOTE_URL_FIELDS),
        ),
    )


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and parsed.hostname is not None


def _disable_invalid_enabled_configs(conn: sa.Connection, table: sa.Table) -> None:
    """Fail closed for legacy enabled rows that cannot satisfy the new invariant."""
    rows = conn.execute(
        sa.select(
            table.c.id,
            table.c.client_secret_encrypted,
            table.c.provider_settings,
        ).where(table.c.enabled.is_(True))
    ).mappings()
    for row in rows:
        settings = row["provider_settings"] or {}
        has_client_id = isinstance(settings.get("client_id"), str) and bool(settings["client_id"].strip())
        has_discovery = _is_http_url(settings.get("discovery_url"))
        endpoint_values = [settings.get(key) for key in ("authorization_endpoint", "token_endpoint", "jwks_uri")]
        has_explicit_endpoints = all(_is_http_url(value) for value in endpoint_values)
        supplied_urls_are_valid = all(
            value is None or _is_http_url(value) for value in (settings.get(key) for key in _REMOTE_URL_FIELDS)
        )
        if not (
            row["client_secret_encrypted"]
            and has_client_id
            and (has_discovery or has_explicit_endpoints)
            and supplied_urls_are_valid
        ):
            conn.execute(table.update().where(table.c.id == row["id"]).values(enabled=False))


def _raise_for_protocol_mismatches(conn: sa.Connection, table: sa.Table) -> None:
    invalid_ids = [
        str(row.id)
        for row in conn.execute(sa.select(table.c.id, table.c.protocol, table.c.provider_settings))
        if row.protocol != "oidc"
        or not isinstance(row.provider_settings, dict)
        or row.provider_settings.get("protocol") != row.protocol
    ]
    if invalid_ids:
        msg = (
            "sso_config contains unsupported or inconsistent protocol settings for row(s): "
            f"{', '.join(invalid_ids)}. Correct these rows before rerunning the migration."
        )
        raise RuntimeError(msg)


def _existing_check_names(conn: sa.Connection) -> set[str]:
    return {check["name"] for check in sa.inspect(conn).get_check_constraints(_CONFIG_TABLE) if check.get("name")}


def _create_checks(conn: sa.Connection, table: sa.Table) -> None:
    # create_all() may already have installed these from the SQLModel metadata.
    existing = _existing_check_names(conn)
    need_protocol = _PROTOCOL_CHECK not in existing
    need_enabled = _ENABLED_CHECK not in existing
    if not need_protocol and not need_enabled:
        return
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table(_CONFIG_TABLE, recreate="always") as batch_op:
            if need_protocol:
                batch_op.create_check_constraint(_PROTOCOL_CHECK, _protocol_check(table))
            if need_enabled:
                batch_op.create_check_constraint(_ENABLED_CHECK, _enabled_check(table))
        return
    if need_protocol:
        op.create_check_constraint(_PROTOCOL_CHECK, _CONFIG_TABLE, _protocol_check(table))
    if need_enabled:
        op.create_check_constraint(_ENABLED_CHECK, _CONFIG_TABLE, _enabled_check(table))


def _drop_checks(conn: sa.Connection) -> None:
    existing = _existing_check_names(conn)
    if _ENABLED_CHECK not in existing and _PROTOCOL_CHECK not in existing:
        return
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table(_CONFIG_TABLE, recreate="always") as batch_op:
            if _ENABLED_CHECK in existing:
                batch_op.drop_constraint(_ENABLED_CHECK, type_="check")
            if _PROTOCOL_CHECK in existing:
                batch_op.drop_constraint(_PROTOCOL_CHECK, type_="check")
        return
    if _ENABLED_CHECK in existing:
        op.drop_constraint(_ENABLED_CHECK, _CONFIG_TABLE, type_="check")
    if _PROTOCOL_CHECK in existing:
        op.drop_constraint(_PROTOCOL_CHECK, _CONFIG_TABLE, type_="check")


def _create_slug_trigger(conn: sa.Connection) -> None:
    # Idempotent for create_all()-then-upgrade: model after_create listeners may
    # already have installed the same trigger/function.
    if conn.dialect.name == "sqlite":
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_SLUG_TRIGGER}"))
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER {_SLUG_TRIGGER}
                BEFORE UPDATE OF slug ON {_CONFIG_TABLE}
                FOR EACH ROW
                WHEN NEW.slug IS NOT OLD.slug
                BEGIN
                    SELECT RAISE(ABORT, 'SSOConfig.slug is immutable after insert');
                END
                """
            )
        )
    elif conn.dialect.name == "postgresql":
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_SLUG_TRIGGER} ON {_CONFIG_TABLE}"))
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_POSTGRES_TRIGGER_FUNCTION}()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.slug IS DISTINCT FROM OLD.slug THEN
                        RAISE EXCEPTION 'SSOConfig.slug is immutable after insert';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER {_SLUG_TRIGGER}
                BEFORE UPDATE OF slug ON {_CONFIG_TABLE}
                FOR EACH ROW EXECUTE FUNCTION {_POSTGRES_TRIGGER_FUNCTION}()
                """
            )
        )


def _drop_slug_trigger(conn: sa.Connection) -> None:
    if conn.dialect.name == "sqlite":
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_SLUG_TRIGGER}"))
    elif conn.dialect.name == "postgresql":
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_SLUG_TRIGGER} ON {_CONFIG_TABLE}"))
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_POSTGRES_TRIGGER_FUNCTION}()"))


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_CONFIG_TABLE, conn):
        return
    table = _config_table()
    _disable_invalid_enabled_configs(conn, table)
    _raise_for_protocol_mismatches(conn, table)
    _create_checks(conn, table)
    _create_slug_trigger(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(_CONFIG_TABLE, conn):
        return
    _drop_slug_trigger(conn)
    _drop_checks(conn)
