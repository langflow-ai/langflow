"""add database enforcement for SSO configuration invariants

Revision ID: 7c8e9f0a1b2d
Revises: f0a1b2c3d4e5
Create Date: 2026-08-04

Phase: EXPAND
"""

import base64
import binascii
import re
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
# Final DB names (op.f / conv). Without the token wrapper, alembic's
# ck_%(table_name)s_%(constraint_name)s convention doubles the prefix to
# ck_sso_config_ck_sso_config_*, which then survives downgrade and breaks
# later batch_alter drops of protocol / provider_settings on SQLite.
_PROTOCOL_CHECK = "ck_sso_config_protocol_consistency"
_ENABLED_CHECK = "ck_sso_config_enabled_complete"
_CLIENT_SECRET_CHECK = "ck_sso_config_client_secret_envelope"  # noqa: S105  # pragma: allowlist secret
_LEGACY_DOUBLED_PROTOCOL_CHECK = "ck_sso_config_ck_sso_config_protocol_consistency"
_LEGACY_DOUBLED_ENABLED_CHECK = "ck_sso_config_ck_sso_config_enabled_complete"
_LEGACY_DOUBLED_CLIENT_SECRET_CHECK = "ck_sso_config_ck_sso_config_client_secret_envelope"  # noqa: S105  # pragma: allowlist secret
_PROTOCOL_CHECK_ALIASES = (_PROTOCOL_CHECK, _LEGACY_DOUBLED_PROTOCOL_CHECK)
_ENABLED_CHECK_ALIASES = (_ENABLED_CHECK, _LEGACY_DOUBLED_ENABLED_CHECK)
_CLIENT_SECRET_CHECK_ALIASES = (_CLIENT_SECRET_CHECK, _LEGACY_DOUBLED_CLIENT_SECRET_CHECK)
_SLUG_TRIGGER = "trg_sso_config_slug_immutable"
_POSTGRES_TRIGGER_FUNCTION = "prevent_sso_config_slug_update"
_SUPPORTED_PROTOCOLS = ("oidc", "saml", "ldap")
_ENVELOPE_HEADER = "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:"
_ENVELOPE_PART_COUNT = 6
_ENVELOPE_NONCE_LENGTH = 16
_ENVELOPE_MIN_CIPHERTEXT_LENGTH = 22
_ENVELOPE_NONCE_BYTES = 12
_ENVELOPE_MIN_CIPHERTEXT_BYTES = 16
_BASE64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
_PROVIDER_SETTING_COLUMNS = (
    "discovery_url",
    "redirect_uri",
    "scopes",
    "token_endpoint",
    "authorization_endpoint",
    "jwks_uri",
    "issuer",
    "client_id",
)
_REMOTE_URL_FIELDS = (
    "discovery_url",
    "token_endpoint",
    "authorization_endpoint",
    "jwks_uri",
    "issuer",
)
_INVALID_PERCENT_ESCAPE_PATTERN = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _config_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        _CONFIG_TABLE,
        metadata,
        # Leave the id untyped so comparisons reuse the exact DBAPI value.
        # SQLite installations can contain either 32-character UUID hex or
        # historical hyphenated UUID strings, and coercing through ``sa.Uuid``
        # would normalize the latter before UPDATE and fail to match the row.
        sa.Column("id"),
        sa.Column("slug", sa.String()),
        sa.Column("protocol", sa.String()),
        sa.Column("provider", sa.String()),
        sa.Column("enabled", sa.Boolean()),
        sa.Column("client_secret_encrypted", sa.String()),
        sa.Column("provider_settings", sa.JSON()),
    )


def _column_names(conn: sa.Connection) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(_CONFIG_TABLE)}


def _nonblank_json_string(json_column: sa.Column, key: str) -> sa.ColumnElement[bool]:
    value = json_column[key].as_string()
    return sa.and_(value.is_not(None), sa.func.length(sa.func.trim(value)) > 0)


def _http_json_url_or_null(json_column: sa.Column, key: str) -> sa.ColumnElement[bool]:
    value = json_column[key].as_string()
    normalized = sa.func.lower(value)
    has_no_whitespace = sa.and_(
        value.not_like("% %"),
        value.not_like("%\t%"),
        value.not_like("%\n%"),
        value.not_like("%\r%"),
    )
    valid_http_host_start = sa.and_(
        normalized.like("http://%"),
        sa.func.length(value) > len("http://"),
        sa.func.substr(value, len("http://") + 1, 1).not_in(("/", "\\", "?", "#", ":")),
    )
    valid_https_host_start = sa.and_(
        normalized.like("https://%"),
        sa.func.length(value) > len("https://"),
        sa.func.substr(value, len("https://") + 1, 1).not_in(("/", "\\", "?", "#", ":")),
    )
    return sa.or_(value.is_(None), sa.and_(has_no_whitespace, sa.or_(valid_http_host_start, valid_https_host_start)))


def _protocol_check(
    table: sa.Table,
    *,
    allow_supported_mismatch: bool = False,
    allow_pending_n_minus_one: bool = False,
) -> sa.ColumnElement[bool]:
    settings_protocol = table.c.provider_settings["protocol"].as_string()
    synchronized = sa.and_(
        table.c.protocol.in_(_SUPPORTED_PROTOCOLS),
        settings_protocol.is_not(None),
        settings_protocol == table.c.protocol,
    )
    if allow_supported_mismatch:
        # SQLite has no way for a BEFORE trigger to assign NEW values. Its
        # EXPAND compatibility trigger is therefore AFTER UPDATE, so admit a
        # supported temporary mismatch long enough for that trigger to choose
        # one representation and make the row coherent. Invalid protocols are
        # still rejected before the trigger runs.
        synchronized = sa.and_(
            table.c.protocol.in_(_SUPPORTED_PROTOCOLS),
            settings_protocol.in_(_SUPPORTED_PROTOCOLS),
        )
    if not allow_pending_n_minus_one:
        return synchronized
    return sa.or_(
        # Temporary N-1 INSERT state. SQLite evaluates CHECK constraints before
        # the head revision's AFTER INSERT compatibility trigger can populate
        # the new representation.
        sa.and_(
            table.c.protocol.is_(None),
            table.c.provider_settings.is_(None),
            table.c.provider.in_(_SUPPORTED_PROTOCOLS),
        ),
        synchronized,
    )


def _enabled_check(table: sa.Table, *, allow_pending_n_minus_one: bool = False) -> sa.ColumnElement[bool]:
    settings = table.c.provider_settings
    allowed_states = [
        table.c.enabled.is_(False),
        # Historical Enterprise plugins can continue executing their released
        # SAML/LDAP rows during the rolling window. OIDC-only completeness is
        # enforced below without mutating those legacy configurations.
        table.c.protocol.in_(("saml", "ldap")),
        sa.and_(
            table.c.protocol == "oidc",
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
    ]
    if allow_pending_n_minus_one:
        # See _protocol_check: the compatibility trigger immediately fills the
        # typed fields. Final constraints then validate the synchronized row.
        allowed_states.insert(
            0,
            sa.and_(
                table.c.protocol.is_(None),
                table.c.provider_settings.is_(None),
                table.c.provider.in_(_SUPPORTED_PROTOCOLS),
            ),
        )
    return sa.or_(*allowed_states)


def _client_secret_check(table: sa.Table) -> sa.ColumnElement[bool]:
    secret = table.c.client_secret_encrypted
    separator_position = len(_ENVELOPE_HEADER) + _ENVELOPE_NONCE_LENGTH + 1
    minimum_length = separator_position + _ENVELOPE_MIN_CIPHERTEXT_LENGTH
    return sa.or_(
        secret.is_(None),
        sa.and_(
            sa.func.substr(secret, 1, len(_ENVELOPE_HEADER)) == _ENVELOPE_HEADER,
            sa.func.substr(secret, separator_position, 1) == ":",
            sa.func.length(secret) >= minimum_length,
        ),
    )


def _is_secret_envelope(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split(":")
    if len(parts) != _ENVELOPE_PART_COUNT or f"{':'.join(parts[:4])}:" != _ENVELOPE_HEADER:
        return False

    decoded_payloads = []
    for encoded in parts[4:]:
        if not encoded or any(character not in _BASE64URL_ALPHABET for character in encoded):
            return False
        try:
            decoded_payloads.append(
                base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            )
        except (binascii.Error, ValueError):
            return False
    nonce, ciphertext = decoded_payloads
    return len(nonce) == _ENVELOPE_NONCE_BYTES and len(ciphertext) >= _ENVELOPE_MIN_CIPHERTEXT_BYTES


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.netloc)
            and parsed.hostname is not None
            and not any(character.isspace() for character in value)
            and _INVALID_PERCENT_ESCAPE_PATTERN.search(value) is None
            and "%" not in parsed.hostname
        )
        if valid:
            # Accessing ``port`` forces urllib to reject malformed ports.
            _ = parsed.port
    except ValueError:
        return False
    return valid


def _sanitize_pending_n_minus_one_configs(conn: sa.Connection) -> None:
    """Fail closed for legacy rows written after the typed-column backfill."""
    columns = _column_names(conn)
    required = {"id", "protocol", "provider", "enabled", "client_secret_encrypted", "provider_settings"}
    if not required <= columns:
        return

    selected_names = [*required]
    selected_names.extend(name for name in _PROVIDER_SETTING_COLUMNS if name in columns)
    table = sa.table(
        _CONFIG_TABLE,
        *(
            sa.column(
                name,
                sa.JSON()
                if name == "provider_settings"
                else sa.Boolean()
                if name == "enabled"
                else sa.String()
                if name != "id"
                else None,
            )
            for name in selected_names
        ),
    )
    rows = (
        conn.execute(
            sa.select(*(table.c[name] for name in selected_names)).where(
                table.c.protocol.is_(None),
                table.c.provider_settings.is_(None),
                table.c.provider.in_(_SUPPORTED_PROTOCOLS),
            )
        )
        .mappings()
        .all()
    )
    for row in rows:
        secret_is_valid = _is_secret_envelope(row["client_secret_encrypted"])
        values: dict[str, object] = {}
        if row["client_secret_encrypted"] is not None and not secret_is_valid:
            values["client_secret_encrypted"] = None

        if row["provider"] == "oidc" and row["enabled"]:
            has_client_id = isinstance(row.get("client_id"), str) and bool(row["client_id"].strip())
            has_discovery = _is_http_url(row.get("discovery_url"))
            endpoint_values = [row.get(key) for key in ("authorization_endpoint", "token_endpoint", "jwks_uri")]
            has_explicit_endpoints = all(_is_http_url(value) for value in endpoint_values)
            supplied_urls_are_valid = all(
                value is None or _is_http_url(value) for value in (row.get(key) for key in _REMOTE_URL_FIELDS)
            )
            if not (
                secret_is_valid
                and has_client_id
                and (has_discovery or has_explicit_endpoints)
                and supplied_urls_are_valid
            ):
                values["enabled"] = False

        if values:
            conn.execute(table.update().where(table.c.id == row["id"]).values(**values))


def _disable_invalid_enabled_configs(conn: sa.Connection, table: sa.Table) -> None:
    """Fail closed for legacy enabled rows that cannot satisfy the new invariant."""
    rows = conn.execute(
        sa.select(
            table.c.id,
            table.c.protocol,
            table.c.client_secret_encrypted,
            table.c.provider_settings,
        ).where(table.c.enabled.is_(True))
    ).mappings()
    for row in rows:
        # Preserve historical Enterprise protocols exactly. Their released
        # plugin remains responsible for protocol-specific completeness.
        if row["protocol"] != "oidc":
            continue
        settings = row["provider_settings"] or {}
        has_client_id = isinstance(settings.get("client_id"), str) and bool(settings["client_id"].strip())
        has_discovery = _is_http_url(settings.get("discovery_url"))
        endpoint_values = [settings.get(key) for key in ("authorization_endpoint", "token_endpoint", "jwks_uri")]
        has_explicit_endpoints = all(_is_http_url(value) for value in endpoint_values)
        supplied_urls_are_valid = all(
            value is None or _is_http_url(value) for value in (settings.get(key) for key in _REMOTE_URL_FIELDS)
        )
        if not (
            _is_secret_envelope(row["client_secret_encrypted"])
            and has_client_id
            and (has_discovery or has_explicit_endpoints)
            and supplied_urls_are_valid
        ):
            conn.execute(table.update().where(table.c.id == row["id"]).values(enabled=False))


def _raise_for_protocol_mismatches(conn: sa.Connection, table: sa.Table) -> None:
    has_legacy_provider = "provider" in _column_names(conn)
    selected_columns = [table.c.id, table.c.protocol, table.c.provider_settings]
    if has_legacy_provider:
        selected_columns.append(table.c.provider)

    invalid_ids = []
    for row in conn.execute(sa.select(*selected_columns)).mappings():
        # Mirror _protocol_check: a pending N-1 insert is a legal temporary
        # state only when the released representation physically exists and
        # names a supported protocol.
        if (
            has_legacy_provider
            and row["protocol"] is None
            and row["provider_settings"] is None
            and row["provider"] in _SUPPORTED_PROTOCOLS
        ):
            continue
        if (
            row["protocol"] not in _SUPPORTED_PROTOCOLS
            or not isinstance(row["provider_settings"], dict)
            or row["provider_settings"].get("protocol") != row["protocol"]
        ):
            invalid_ids.append(str(row["id"]))
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
    # Also treat the legacy doubled-prefix names as present so a partial upgrade
    # does not install a second copy under the canonical name.
    existing = _existing_check_names(conn)
    need_protocol = not existing.intersection(_PROTOCOL_CHECK_ALIASES)
    need_enabled = not existing.intersection(_ENABLED_CHECK_ALIASES)
    need_client_secret = not existing.intersection(_CLIENT_SECRET_CHECK_ALIASES)
    if not need_protocol and not need_enabled and not need_client_secret:
        return
    allow_pending_n_minus_one = "provider" in _column_names(conn)
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table(_CONFIG_TABLE, recreate="always") as batch_op:
            if need_protocol:
                batch_op.create_check_constraint(
                    op.f(_PROTOCOL_CHECK),
                    _protocol_check(
                        table,
                        allow_supported_mismatch=True,
                        allow_pending_n_minus_one=allow_pending_n_minus_one,
                    ),
                )
            if need_enabled:
                batch_op.create_check_constraint(
                    op.f(_ENABLED_CHECK),
                    _enabled_check(table, allow_pending_n_minus_one=allow_pending_n_minus_one),
                )
            if need_client_secret:
                batch_op.create_check_constraint(op.f(_CLIENT_SECRET_CHECK), _client_secret_check(table))
        return
    if need_protocol:
        op.create_check_constraint(
            op.f(_PROTOCOL_CHECK),
            _CONFIG_TABLE,
            _protocol_check(table, allow_pending_n_minus_one=allow_pending_n_minus_one),
        )
    if need_enabled:
        op.create_check_constraint(
            op.f(_ENABLED_CHECK),
            _CONFIG_TABLE,
            _enabled_check(table, allow_pending_n_minus_one=allow_pending_n_minus_one),
        )
    if need_client_secret:
        op.create_check_constraint(op.f(_CLIENT_SECRET_CHECK), _CONFIG_TABLE, _client_secret_check(table))


def _drop_checks(conn: sa.Connection) -> None:
    existing = _existing_check_names(conn)
    to_drop = [
        name
        for name in (*_CLIENT_SECRET_CHECK_ALIASES, *_ENABLED_CHECK_ALIASES, *_PROTOCOL_CHECK_ALIASES)
        if name in existing
    ]
    if not to_drop:
        return
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table(_CONFIG_TABLE, recreate="always") as batch_op:
            for name in to_drop:
                batch_op.drop_constraint(op.f(name), type_="check")
        return
    for name in to_drop:
        op.drop_constraint(op.f(name), _CONFIG_TABLE, type_="check")


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
                WHEN OLD.slug IS NOT NULL AND NEW.slug IS NOT OLD.slug
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
                    IF OLD.slug IS NOT NULL AND NEW.slug IS DISTINCT FROM OLD.slug THEN
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
    _sanitize_pending_n_minus_one_configs(conn)
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
