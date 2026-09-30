"""complete rolling-compatible SSO schema expansion

Revision ID: 8d9e0f1a2b3c
Revises: 7c8e9f0a1b2d
Create Date: 2026-08-05

Phase: EXPAND

The preceding SSO revisions deliberately retain both the released scalar
columns and the new typed columns. Temporary triggers in this revision keep
those representations coherent while N-1 and N services coexist. A future
CONTRACT revision may remove these triggers and the legacy columns only after
all released consumers have switched to the new representation.

The released client-secret column is the deliberate exception to write
compatibility: a plaintext N-1 write is rejected by the envelope constraint
rather than reintroducing plaintext credentials. Secret rotation during the
rolling window must go through the N admin API, which encrypts before storage.

``provider_name`` also remains the stable legacy identity key during EXPAND.
Changing the N-only ``display_name`` therefore does not rewrite it (or any
profiles); a future CONTRACT migration can re-key profiles atomically.

The original SSO table migration shipped ``created_at`` and ``updated_at`` as
UTC-naive timestamps. PostgreSQL is corrected forward here rather than by
editing that already-applied migration. SQLite has no distinct timezone-aware
datetime affinity, so the timestamp conversion is intentionally a no-op there.
"""

# ruff: noqa: S608

import base64
import binascii
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "8d9e0f1a2b3c"  # pragma: allowlist secret
down_revision: str | None = "7c8e9f0a1b2d"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIG_TABLE = "sso_config"
_SETTINGS_TABLE = "sso_settings"
_TIMESTAMP_COLUMNS = ("created_at", "updated_at")
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
_SUPPORTED_PROTOCOLS = ("oidc", "saml", "ldap")
_ENVELOPE_HEADER = "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:"
_ENVELOPE_PART_COUNT = 6
_ENVELOPE_NONCE_BYTES = 12
_ENVELOPE_MIN_CIPHERTEXT_BYTES = 16
_BASE64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
_COMPAT_COLUMNS = {
    "id",
    "slug",
    "display_name",
    "provider_name",
    "protocol",
    "provider",
    "enabled",
    "client_secret_encrypted",
    "provider_settings",
    "enforce_sso",
    *_PROVIDER_SETTING_COLUMNS,
}

_SQLITE_CONFIG_INSERT_TRIGGER = "trg_sso_config_expand_compat_insert"
_SQLITE_CONFIG_UPDATE_TRIGGER = "trg_sso_config_expand_compat_update"
_SQLITE_CONFIG_ENFORCE_TRIGGER = "trg_sso_config_expand_compat_enforce"
_SQLITE_SETTINGS_ENFORCE_TRIGGER = "trg_sso_settings_expand_compat_enforce"
_POSTGRES_CONFIG_FUNCTION = "sync_sso_config_expand_compat"
_POSTGRES_CONFIG_TRIGGER = "trg_sso_config_expand_compat"
_POSTGRES_CONFIG_ENFORCE_FUNCTION = "sync_sso_config_enforce_sso_compat"
_POSTGRES_CONFIG_ENFORCE_TRIGGER = "trg_sso_config_enforce_sso_compat"
_POSTGRES_SETTINGS_ENFORCE_FUNCTION = "sync_sso_settings_enforce_sso_compat"
_POSTGRES_SETTINGS_ENFORCE_TRIGGER = "trg_sso_settings_enforce_sso_compat"


def _column_names(conn: sa.Connection, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table_name)}


def _has_compatibility_schema(conn: sa.Connection) -> bool:
    return (
        migration.table_exists(_CONFIG_TABLE, conn)
        and migration.table_exists(_SETTINGS_TABLE, conn)
        and _column_names(conn, _CONFIG_TABLE) >= _COMPAT_COLUMNS
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


def _normalize_pending_n_minus_one_rows(conn: sa.Connection) -> None:
    """Complete rows written through the legacy representation before this revision."""
    if not _has_compatibility_schema(conn):
        return

    table = sa.table(
        _CONFIG_TABLE,
        sa.column("id"),
        sa.column("slug", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("provider_name", sa.String()),
        sa.column("protocol", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("client_secret_encrypted", sa.String()),
        sa.column("provider_settings", sa.JSON()),
        *(sa.column(name, sa.String()) for name in _PROVIDER_SETTING_COLUMNS),
    )
    rows = (
        conn.execute(
            sa.select(table).where(
                table.c.protocol.is_(None),
                table.c.provider_settings.is_(None),
                table.c.provider.in_(_SUPPORTED_PROTOCOLS),
            )
        )
        .mappings()
        .all()
    )
    for row in rows:
        provider_settings = {"protocol": row["provider"]}
        provider_settings.update({name: row[name] for name in _PROVIDER_SETTING_COLUMNS})
        values = {
            "slug": row["slug"] or f"sso-{UUID(str(row['id'])).hex}",
            "display_name": row["display_name"] or row["provider_name"],
            "protocol": row["provider"],
            "provider_settings": provider_settings,
        }
        if row["provider"] == "oidc" and not _is_secret_envelope(row["client_secret_encrypted"]):
            # A pending row bypassed the typed OIDC completeness branch in 7c.
            # Complete it fail-closed, and discard any legacy plaintext or
            # malformed value instead of reintroducing an unusable credential.
            values["enabled"] = False
            values["client_secret_encrypted"] = None
        conn.execute(table.update().where(table.c.id == row["id"]).values(**values))


def _sqlite_provider_settings_json(prefix: str = "NEW") -> str:
    pairs = [f"'protocol', COALESCE({prefix}.provider, {prefix}.protocol, 'oidc')"]
    pairs.extend(f"'{name}', {prefix}.{name}" for name in _PROVIDER_SETTING_COLUMNS)
    return f"json_object({', '.join(pairs)})"


def _sqlite_legacy_settings_changed() -> str:
    return " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in ("provider", *_PROVIDER_SETTING_COLUMNS))


def _sqlite_insert_assignments() -> str:
    settings_json = _sqlite_provider_settings_json()
    assignments = [
        "slug = COALESCE(NEW.slug, 'sso-' || lower(replace(CAST(NEW.id AS TEXT), '-', '')))",
        "display_name = COALESCE(NEW.display_name, NEW.provider_name)",
        "provider_name = COALESCE(NEW.provider_name, NEW.display_name)",
        "protocol = COALESCE(NEW.protocol, NEW.provider, json_extract(NEW.provider_settings, '$.protocol'), 'oidc')",
        "provider = COALESCE(NEW.provider, NEW.protocol, json_extract(NEW.provider_settings, '$.protocol'), 'oidc')",
        f"provider_settings = COALESCE(NEW.provider_settings, {settings_json})",
        """enforce_sso = CASE
                        WHEN NEW.enforce_sso = 1 THEN 1
                        ELSE COALESCE((SELECT enforce_sso FROM sso_settings WHERE id = 1), 0)
                    END""",
    ]
    assignments.extend(
        f"{name} = COALESCE(NEW.{name}, json_extract(NEW.provider_settings, '$.{name}'))"
        for name in _PROVIDER_SETTING_COLUMNS
    )
    return ",\n                    ".join(assignments)


def _sqlite_update_assignments() -> str:
    legacy_settings_changed = _sqlite_legacy_settings_changed()
    settings_json = _sqlite_provider_settings_json()
    assignments = [
        """display_name = CASE
                        WHEN NEW.display_name IS NOT OLD.display_name THEN NEW.display_name
                        WHEN NEW.provider_name IS NOT OLD.provider_name THEN NEW.provider_name
                        ELSE NEW.display_name
                    END""",
        """provider_name = CASE
                        WHEN NEW.provider_name IS NOT OLD.provider_name THEN NEW.provider_name
                        ELSE OLD.provider_name
                    END""",
        """protocol = CASE
                        WHEN NEW.protocol IS NOT OLD.protocol THEN NEW.protocol
                        WHEN NEW.provider IS NOT OLD.provider THEN NEW.provider
                        WHEN NEW.provider_settings IS NOT OLD.provider_settings
                            THEN json_extract(NEW.provider_settings, '$.protocol')
                        ELSE NEW.protocol
                    END""",
        """provider = CASE
                        WHEN NEW.protocol IS NOT OLD.protocol THEN NEW.protocol
                        WHEN NEW.provider IS NOT OLD.provider THEN NEW.provider
                        WHEN NEW.provider_settings IS NOT OLD.provider_settings
                            THEN json_extract(NEW.provider_settings, '$.protocol')
                        ELSE NEW.provider
                    END""",
        f"""provider_settings = CASE
                        WHEN NEW.protocol IS NOT OLD.protocol
                            THEN json_set(COALESCE(NEW.provider_settings, '{{}}'), '$.protocol', NEW.protocol)
                        WHEN NEW.provider IS NOT OLD.provider
                                AND NEW.provider_settings IS NOT OLD.provider_settings
                            THEN json_set(COALESCE(NEW.provider_settings, '{{}}'), '$.protocol', NEW.provider)
                        WHEN NEW.provider IS NOT OLD.provider THEN {settings_json}
                        WHEN NEW.provider_settings IS NOT OLD.provider_settings THEN NEW.provider_settings
                        WHEN {legacy_settings_changed} THEN {settings_json}
                        ELSE NEW.provider_settings
                    END""",
    ]
    assignments.extend(
        f"""{name} = CASE
                        WHEN NEW.provider_settings IS NOT OLD.provider_settings
                            THEN json_extract(NEW.provider_settings, '$.{name}')
                        ELSE NEW.{name}
                    END"""
        for name in _PROVIDER_SETTING_COLUMNS
    )
    return ",\n                    ".join(assignments)


def _create_sqlite_compatibility_triggers() -> None:
    _drop_sqlite_compatibility_triggers()
    update_columns = ", ".join(
        ("display_name", "provider_name", "protocol", "provider", "provider_settings", *_PROVIDER_SETTING_COLUMNS)
    )
    changed = " OR ".join(
        f"NEW.{name} IS NOT OLD.{name}"
        for name in (
            "display_name",
            "provider_name",
            "protocol",
            "provider",
            "provider_settings",
            *_PROVIDER_SETTING_COLUMNS,
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_SQLITE_CONFIG_INSERT_TRIGGER}
            AFTER INSERT ON {_CONFIG_TABLE}
            FOR EACH ROW
            BEGIN
                UPDATE {_CONFIG_TABLE}
                SET {_sqlite_insert_assignments()}
                WHERE id = NEW.id;
                UPDATE {_SETTINGS_TABLE}
                SET enforce_sso = 1
                WHERE id = 1 AND NEW.enforce_sso = 1;
                UPDATE {_CONFIG_TABLE}
                SET enforce_sso = 1
                WHERE NEW.enforce_sso = 1 AND enforce_sso IS NOT 1;
            END
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_SQLITE_CONFIG_UPDATE_TRIGGER}
            AFTER UPDATE OF {update_columns} ON {_CONFIG_TABLE}
            FOR EACH ROW
            WHEN {changed}
            BEGIN
                UPDATE {_CONFIG_TABLE}
                SET {_sqlite_update_assignments()}
                WHERE id = NEW.id;
            END
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_SQLITE_CONFIG_ENFORCE_TRIGGER}
            AFTER UPDATE OF enforce_sso ON {_CONFIG_TABLE}
            FOR EACH ROW
            WHEN NEW.enforce_sso IS NOT OLD.enforce_sso
            BEGIN
                UPDATE {_SETTINGS_TABLE} SET enforce_sso = NEW.enforce_sso WHERE id = 1;
                UPDATE {_CONFIG_TABLE}
                SET enforce_sso = NEW.enforce_sso
                WHERE enforce_sso IS NOT NEW.enforce_sso;
            END
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_SQLITE_SETTINGS_ENFORCE_TRIGGER}
            AFTER UPDATE OF enforce_sso ON {_SETTINGS_TABLE}
            FOR EACH ROW
            WHEN NEW.enforce_sso IS NOT OLD.enforce_sso
            BEGIN
                UPDATE {_CONFIG_TABLE}
                SET enforce_sso = NEW.enforce_sso
                WHERE enforce_sso IS NOT NEW.enforce_sso;
            END
            """
        )
    )


def _drop_sqlite_compatibility_triggers() -> None:
    for name in (
        _SQLITE_CONFIG_INSERT_TRIGGER,
        _SQLITE_CONFIG_UPDATE_TRIGGER,
        _SQLITE_CONFIG_ENFORCE_TRIGGER,
        _SQLITE_SETTINGS_ENFORCE_TRIGGER,
    ):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))


def _postgres_provider_settings_json() -> str:
    pairs = ["'protocol', COALESCE(NEW.provider, NEW.protocol, 'oidc')"]
    pairs.extend(f"'{name}', NEW.{name}" for name in _PROVIDER_SETTING_COLUMNS)
    return f"json_build_object({', '.join(pairs)})"


def _postgres_legacy_settings_changed() -> str:
    return " OR ".join(f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in ("provider", *_PROVIDER_SETTING_COLUMNS))


def _create_postgres_compatibility_triggers() -> None:
    _drop_postgres_compatibility_triggers()
    legacy_settings_changed = _postgres_legacy_settings_changed()
    settings_json = _postgres_provider_settings_json()
    legacy_insert_assignments = "\n".join(
        f"NEW.{name} := COALESCE(NEW.{name}, NEW.provider_settings ->> '{name}');" for name in _PROVIDER_SETTING_COLUMNS
    )
    legacy_update_assignments = "\n".join(
        f"""IF NEW.provider_settings::jsonb IS DISTINCT FROM OLD.provider_settings::jsonb THEN
                    NEW.{name} := NEW.provider_settings ->> '{name}';
                END IF;"""
        for name in _PROVIDER_SETTING_COLUMNS
    )
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_POSTGRES_CONFIG_FUNCTION}()
            RETURNS trigger AS $$
            DECLARE
                provider_settings_changed boolean := false;
                protocol_changed boolean := false;
                provider_changed boolean := false;
                legacy_settings_changed boolean := false;
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    NEW.slug := COALESCE(NEW.slug, 'sso-' || replace(NEW.id::text, '-', ''));
                    NEW.display_name := COALESCE(NEW.display_name, NEW.provider_name);
                    NEW.provider_name := COALESCE(NEW.provider_name, NEW.display_name);
                    NEW.protocol := COALESCE(
                        NEW.protocol,
                        NEW.provider,
                        NEW.provider_settings ->> 'protocol',
                        'oidc'
                    );
                    NEW.provider := COALESCE(
                        NEW.provider,
                        NEW.protocol,
                        NEW.provider_settings ->> 'protocol',
                        'oidc'
                    );
                    NEW.provider_settings := COALESCE(NEW.provider_settings, {settings_json});
                    {legacy_insert_assignments}
                    IF NEW.enforce_sso IS NOT TRUE THEN
                        NEW.enforce_sso := (
                            SELECT enforce_sso FROM {_SETTINGS_TABLE} WHERE id = 1
                        );
                    END IF;
                    RETURN NEW;
                END IF;

                -- Capture the writer's source representation before mutating
                -- NEW. Otherwise a legacy provider + scalar update makes our
                -- own json mutation look like an N-side write and loses the
                -- changed legacy scalar.
                provider_settings_changed :=
                    NEW.provider_settings::jsonb IS DISTINCT FROM OLD.provider_settings::jsonb;
                protocol_changed := NEW.protocol IS DISTINCT FROM OLD.protocol;
                provider_changed := NEW.provider IS DISTINCT FROM OLD.provider;
                legacy_settings_changed := {legacy_settings_changed};

                IF NEW.provider_name IS DISTINCT FROM OLD.provider_name
                        AND NEW.display_name IS NOT DISTINCT FROM OLD.display_name THEN
                    NEW.display_name := NEW.provider_name;
                END IF;

                IF protocol_changed THEN
                    NEW.provider := NEW.protocol;
                    NEW.provider_settings := jsonb_set(
                        COALESCE(NEW.provider_settings::jsonb, '{{}}'::jsonb),
                        '{{protocol}}',
                        to_jsonb(NEW.protocol)
                    )::json;
                ELSIF provider_changed THEN
                    NEW.protocol := NEW.provider;
                    NEW.provider_settings := jsonb_set(
                        COALESCE(NEW.provider_settings::jsonb, '{{}}'::jsonb),
                        '{{protocol}}',
                        to_jsonb(NEW.provider)
                    )::json;
                ELSIF provider_settings_changed THEN
                    NEW.protocol := NEW.provider_settings ->> 'protocol';
                    NEW.provider := NEW.protocol;
                END IF;

                IF provider_settings_changed OR protocol_changed THEN
                    {legacy_update_assignments}
                ELSIF legacy_settings_changed THEN
                    NEW.provider_settings := {settings_json};
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
            CREATE TRIGGER {_POSTGRES_CONFIG_TRIGGER}
            BEFORE INSERT OR UPDATE OF
                display_name, provider_name, protocol, provider, provider_settings,
                {", ".join(_PROVIDER_SETTING_COLUMNS)}
            ON {_CONFIG_TABLE}
            FOR EACH ROW EXECUTE FUNCTION {_POSTGRES_CONFIG_FUNCTION}()
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_POSTGRES_CONFIG_ENFORCE_FUNCTION}()
            RETURNS trigger AS $$
            BEGIN
                IF pg_trigger_depth() > 1 THEN
                    RETURN NULL;
                END IF;
                IF TG_OP = 'INSERT' AND NEW.enforce_sso IS NOT TRUE THEN
                    RETURN NULL;
                END IF;
                UPDATE {_SETTINGS_TABLE} SET enforce_sso = NEW.enforce_sso WHERE id = 1;
                UPDATE {_CONFIG_TABLE}
                SET enforce_sso = NEW.enforce_sso
                WHERE enforce_sso IS DISTINCT FROM NEW.enforce_sso;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_POSTGRES_CONFIG_ENFORCE_TRIGGER}
            AFTER INSERT OR UPDATE OF enforce_sso ON {_CONFIG_TABLE}
            FOR EACH ROW EXECUTE FUNCTION {_POSTGRES_CONFIG_ENFORCE_FUNCTION}()
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_POSTGRES_SETTINGS_ENFORCE_FUNCTION}()
            RETURNS trigger AS $$
            BEGIN
                IF pg_trigger_depth() > 1 THEN
                    RETURN NULL;
                END IF;
                UPDATE {_CONFIG_TABLE}
                SET enforce_sso = NEW.enforce_sso
                WHERE enforce_sso IS DISTINCT FROM NEW.enforce_sso;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_POSTGRES_SETTINGS_ENFORCE_TRIGGER}
            AFTER UPDATE OF enforce_sso ON {_SETTINGS_TABLE}
            FOR EACH ROW EXECUTE FUNCTION {_POSTGRES_SETTINGS_ENFORCE_FUNCTION}()
            """
        )
    )


def _drop_postgres_compatibility_triggers() -> None:
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_POSTGRES_CONFIG_TRIGGER} ON {_CONFIG_TABLE}"))
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_POSTGRES_CONFIG_ENFORCE_TRIGGER} ON {_CONFIG_TABLE}"))
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_POSTGRES_SETTINGS_ENFORCE_TRIGGER} ON {_SETTINGS_TABLE}"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_POSTGRES_CONFIG_FUNCTION}()"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_POSTGRES_CONFIG_ENFORCE_FUNCTION}()"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_POSTGRES_SETTINGS_ENFORCE_FUNCTION}()"))


def _create_compatibility_triggers(conn: sa.Connection) -> None:
    if not _has_compatibility_schema(conn):
        return
    if conn.dialect.name == "sqlite":
        _create_sqlite_compatibility_triggers()
    elif conn.dialect.name == "postgresql":
        _create_postgres_compatibility_triggers()


def _drop_compatibility_triggers(conn: sa.Connection) -> None:
    if not migration.table_exists(_CONFIG_TABLE, conn) or not migration.table_exists(_SETTINGS_TABLE, conn):
        return
    if conn.dialect.name == "sqlite":
        _drop_sqlite_compatibility_triggers()
    elif conn.dialect.name == "postgresql":
        _drop_postgres_compatibility_triggers()


def _convert_timestamps(conn: sa.Connection, *, timezone_aware: bool) -> None:
    if conn.dialect.name != "postgresql" or not migration.table_exists(_CONFIG_TABLE, conn):
        return
    columns = _column_names(conn, _CONFIG_TABLE)
    for name in _TIMESTAMP_COLUMNS:
        if name not in columns:
            continue
        if timezone_aware:
            op.execute(
                sa.text(
                    f"ALTER TABLE {_CONFIG_TABLE} "
                    f"ALTER COLUMN {name} TYPE TIMESTAMP WITH TIME ZONE "
                    f"USING {name} AT TIME ZONE 'UTC'"
                )
            )
        else:
            op.execute(
                sa.text(
                    f"ALTER TABLE {_CONFIG_TABLE} "
                    f"ALTER COLUMN {name} TYPE TIMESTAMP WITHOUT TIME ZONE "
                    f"USING {name} AT TIME ZONE 'UTC'"
                )
            )


def upgrade() -> None:
    conn = op.get_bind()
    _normalize_pending_n_minus_one_rows(conn)
    _convert_timestamps(conn, timezone_aware=True)
    _create_compatibility_triggers(conn)


def downgrade() -> None:
    conn = op.get_bind()
    _drop_compatibility_triggers(conn)
    _convert_timestamps(conn, timezone_aware=False)
