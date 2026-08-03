"""update SSO identity, connection, and protocol contracts

Revision ID: e9f2a3b4c5d6
Revises: b7d5f9a3c2e4
Create Date: 2026-07-29

Phase: EXPAND
"""

import os
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e9f2a3b4c5d6"  # pragma: allowlist secret
down_revision: str | None = "b7d5f9a3c2e4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILE_TABLE = "sso_user_profile"
_CONFIG_TABLE = "sso_config"
_SETTINGS_TABLE = "sso_settings"
_USER_ID_INDEX = "ix_sso_user_profile_user_id"
_USER_PROVIDER_INDEX = "uq_sso_user_profile_user_provider"
_CONFIG_SLUG_INDEX = "uq_sso_config_slug"
_UPDATED_BY_FK = "fk_sso_config_updated_by_user"
_SETTINGS_SINGLETON_CHECK = "ck_sso_settings_singleton"
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
# Structural prefix of the current client-secret envelope. Duplicated from
# ``models/auth/sso_secret.py`` on purpose: a migration must not import
# application models, whose shape changes independently of this revision.
_ENVELOPE_HEADER = "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:"
_ENVELOPE_PART_COUNT = 6


def _external_auth_provider() -> str | None:
    """Return the provider key owned by OSS EXTERNAL_AUTH, if configured.

    ``sso_user_profile.sso_provider`` has two independent writers: the SSO plugin
    (which this revision re-keys onto ``sso_config.slug``) and the OSS
    EXTERNAL_AUTH flow in ``services/auth/service.py``, which writes
    ``EXTERNAL_AUTH_PROVIDER`` verbatim. Those rows belong to a different feature
    and must never be re-keyed here — rewriting one silently breaks that user's
    login and JIT-provisions a duplicate account on their next sign-in.
    """
    return os.environ.get("LANGFLOW_EXTERNAL_AUTH_PROVIDER", "").strip() or None


def _is_secret_envelope(value: object) -> bool:
    """Return whether a stored secret is already a versioned ciphertext envelope."""
    return (
        isinstance(value, str) and value.startswith(_ENVELOPE_HEADER) and len(value.split(":")) == _ENVELOPE_PART_COUNT
    )


def _indexes(conn: sa.Connection, table_name: str) -> dict[str, dict]:
    return {index["name"]: index for index in sa.inspect(conn).get_indexes(table_name)}


def _column_names(conn: sa.Connection, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table_name)}


def _foreign_keys(conn: sa.Connection, table_name: str) -> list[dict]:
    return sa.inspect(conn).get_foreign_keys(table_name)


def _backfill_connection_identity(conn: sa.Connection) -> None:
    columns = _column_names(conn, _CONFIG_TABLE)
    if not {"id", "slug", "display_name", "provider_name"} <= columns:
        return

    table = sa.table(
        _CONFIG_TABLE,
        sa.column("id"),
        sa.column("slug"),
        sa.column("display_name"),
        sa.column("provider_name"),
    )
    for row in conn.execute(
        sa.select(table.c.id, table.c.slug, table.c.display_name, table.c.provider_name)
    ).mappings():
        values = {}
        if not row["slug"]:
            values["slug"] = f"sso-{UUID(str(row['id'])).hex}"
        if row["display_name"] is None:
            values["display_name"] = row["provider_name"]
        if values:
            conn.execute(table.update().where(table.c.id == row["id"]).values(**values))


def _backfill_profile_connection_slugs(conn: sa.Connection) -> None:
    if not migration.table_exists(_PROFILE_TABLE, conn):
        return
    config_columns = _column_names(conn, _CONFIG_TABLE)
    profile_columns = _column_names(conn, _PROFILE_TABLE)
    if not {"id", "slug", "provider_name"} <= config_columns or "sso_provider" not in profile_columns:
        return

    config = sa.table(
        _CONFIG_TABLE,
        sa.column("id"),
        sa.column("slug"),
        sa.column("provider_name"),
    )
    profile = sa.table(_PROFILE_TABLE, sa.column("sso_provider"))
    external_provider = _external_auth_provider()
    rows = conn.execute(sa.select(config.c.slug, config.c.provider_name).order_by(config.c.id)).all()
    for row in rows:
        if not (row.slug and row.provider_name):
            continue
        # Leave EXTERNAL_AUTH-owned identities alone; see _external_auth_provider.
        if external_provider is not None and row.provider_name == external_provider:
            continue
        conn.execute(profile.update().where(profile.c.sso_provider == row.provider_name).values(sso_provider=row.slug))


def _restore_profile_connection_names(conn: sa.Connection) -> None:
    """Reverse of :func:`_backfill_profile_connection_slugs`.

    No EXTERNAL_AUTH guard is needed here: that flow never writes a slug, so a
    config skipped on upgrade simply matches no rows on the way back down.
    """
    if not migration.table_exists(_PROFILE_TABLE, conn):
        return
    config_columns = _column_names(conn, _CONFIG_TABLE)
    profile_columns = _column_names(conn, _PROFILE_TABLE)
    if not {"id", "slug", "provider_name"} <= config_columns or "sso_provider" not in profile_columns:
        return

    config = sa.table(
        _CONFIG_TABLE,
        sa.column("id"),
        sa.column("slug"),
        sa.column("provider_name"),
    )
    profile = sa.table(_PROFILE_TABLE, sa.column("sso_provider"))
    rows = conn.execute(sa.select(config.c.slug, config.c.provider_name).order_by(config.c.id)).all()
    for row in rows:
        if row.slug and row.provider_name:
            conn.execute(
                profile.update().where(profile.c.sso_provider == row.slug).values(sso_provider=row.provider_name)
            )


def _sanitize_legacy_client_secrets(conn: sa.Connection) -> None:
    """Clear pre-encryption plaintext client secrets and disable those connections.

    Before this revision ``client_secret_encrypted`` held the raw secret despite
    its name. From this revision on the model rejects any value that is not a
    versioned envelope, so a legacy row would be unwritable through the ORM and
    undecryptable at login — a failure that would surface long after upgrade.

    Re-encrypting in place is not possible here: the key is derived from the
    application's ``SECRET_KEY``, which alembic has no reliable access to, and a
    migration that fails on a missing key would block the deploy. Removing the
    plaintext and disabling the connection fails safe instead, and it also clears
    a secret that was stored unencrypted. An administrator re-enters it through
    the admin UI and re-enables the connection.

    This is deliberately one-way; ``downgrade`` cannot restore a secret that has
    been deleted.
    """
    columns = _column_names(conn, _CONFIG_TABLE)
    if not {"id", "client_secret_encrypted"} <= columns:
        return

    has_enabled = "enabled" in columns
    selected = [sa.column("id"), sa.column("client_secret_encrypted")]
    if has_enabled:
        selected.append(sa.column("enabled"))
    table = sa.table(_CONFIG_TABLE, *selected)

    for row in conn.execute(sa.select(table.c.id, table.c.client_secret_encrypted)).mappings():
        secret = row["client_secret_encrypted"]
        if secret is None or _is_secret_envelope(secret):
            continue
        values: dict[str, object] = {"client_secret_encrypted": None}
        if has_enabled:
            values["enabled"] = False
        conn.execute(table.update().where(table.c.id == row["id"]).values(**values))


def _backfill_provider_settings(conn: sa.Connection) -> None:
    columns = _column_names(conn, _CONFIG_TABLE)
    if not {"id", "protocol", "provider_settings"} <= columns:
        return

    selected_names = ["id", "protocol", "provider_settings"]
    selected_names.extend(name for name in ("provider", *_PROVIDER_SETTING_COLUMNS) if name in columns)
    table = sa.table(
        _CONFIG_TABLE,
        *(sa.column(name, sa.JSON() if name == "provider_settings" else None) for name in selected_names),
    )

    for row in conn.execute(sa.select(*(table.c[name] for name in selected_names))).mappings():
        protocol = row["protocol"] or row.get("provider") or "oidc"
        provider_settings = dict(row["provider_settings"] or {})
        provider_settings.setdefault("protocol", protocol)
        for name in _PROVIDER_SETTING_COLUMNS:
            if name in row and name not in provider_settings:
                provider_settings[name] = row[name]
        conn.execute(
            table.update().where(table.c.id == row["id"]).values(protocol=protocol, provider_settings=provider_settings)
        )


def _backfill_legacy_provider_columns(conn: sa.Connection) -> None:
    columns = _column_names(conn, _CONFIG_TABLE)
    if not {"id", "protocol", "provider_settings", "provider"} <= columns:
        return

    table = sa.table(
        _CONFIG_TABLE,
        sa.column("id"),
        sa.column("protocol"),
        sa.column("provider_settings", sa.JSON()),
        sa.column("provider"),
        *(sa.column(name) for name in _PROVIDER_SETTING_COLUMNS),
    )
    for row in conn.execute(sa.select(table.c.id, table.c.protocol, table.c.provider_settings)).mappings():
        provider_settings = row["provider_settings"] or {}
        values = {"provider": row["protocol"] or provider_settings.get("protocol") or "oidc"}
        values.update({name: provider_settings.get(name) for name in _PROVIDER_SETTING_COLUMNS})
        conn.execute(table.update().where(table.c.id == row["id"]).values(**values))


def _backfill_provider_name(conn: sa.Connection) -> None:
    columns = _column_names(conn, _CONFIG_TABLE)
    if not {"id", "provider_name", "display_name"} <= columns:
        return

    table = sa.table(
        _CONFIG_TABLE,
        sa.column("id"),
        sa.column("provider_name"),
        sa.column("display_name"),
    )
    conn.execute(table.update().where(table.c.provider_name.is_(None)).values(provider_name=table.c.display_name))


def _create_and_backfill_sso_settings(conn: sa.Connection) -> None:
    enforce_sso = False
    if migration.table_exists(_CONFIG_TABLE, conn) and "enforce_sso" in _column_names(conn, _CONFIG_TABLE):
        config = sa.table(_CONFIG_TABLE, sa.column("enforce_sso", sa.Boolean()))
        enforce_sso = any(conn.execute(sa.select(config.c.enforce_sso)).scalars())

    if not migration.table_exists(_SETTINGS_TABLE, conn):
        op.create_table(
            _SETTINGS_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("enforce_sso", sa.Boolean(), nullable=False),
            sa.CheckConstraint("id = 1", name=_SETTINGS_SINGLETON_CHECK),
            sa.PrimaryKeyConstraint("id"),
        )

    settings = sa.table(
        _SETTINGS_TABLE,
        sa.column("id", sa.Integer()),
        sa.column("enforce_sso", sa.Boolean()),
    )
    if conn.scalar(sa.select(sa.func.count()).select_from(settings).where(settings.c.id == 1)) == 0:
        conn.execute(settings.insert().values(id=1, enforce_sso=enforce_sso))


def _upgrade_instance_fields(conn: sa.Connection) -> None:
    _create_and_backfill_sso_settings(conn)
    columns = _column_names(conn, _CONFIG_TABLE)
    if "sort_order" not in columns:
        op.add_column(_CONFIG_TABLE, sa.Column("sort_order", sa.Integer(), nullable=True))
    if "updated_by" not in columns:
        op.add_column(_CONFIG_TABLE, sa.Column("updated_by", sa.Uuid(), nullable=True))

    config = sa.table(
        _CONFIG_TABLE,
        sa.column("id"),
        sa.column("sort_order", sa.Integer()),
    )
    rows = conn.execute(sa.select(config.c.id, config.c.sort_order).order_by(config.c.id)).all()
    for position, row in enumerate(rows):
        if row.sort_order is None:
            conn.execute(config.update().where(config.c.id == row.id).values(sort_order=position))

    columns = _column_names(conn, _CONFIG_TABLE)
    updated_by_foreign_key = next(
        (fk for fk in _foreign_keys(conn, _CONFIG_TABLE) if fk["constrained_columns"] == ["updated_by"]),
        None,
    )
    with op.batch_alter_table(_CONFIG_TABLE, schema=None) as batch_op:
        batch_op.alter_column("sort_order", existing_type=sa.Integer(), nullable=False)
        if updated_by_foreign_key is None:
            batch_op.create_foreign_key(
                _UPDATED_BY_FK,
                "user",
                ["updated_by"],
                ["id"],
                ondelete="SET NULL",
            )
        if "enforce_sso" in columns:
            batch_op.drop_column("enforce_sso")


def _downgrade_instance_fields(conn: sa.Connection) -> None:
    if migration.table_exists(_CONFIG_TABLE, conn):
        columns = _column_names(conn, _CONFIG_TABLE)
        if "enforce_sso" not in columns:
            op.add_column(_CONFIG_TABLE, sa.Column("enforce_sso", sa.Boolean(), nullable=True))

        enforce_sso = False
        if migration.table_exists(_SETTINGS_TABLE, conn):
            settings = sa.table(
                _SETTINGS_TABLE,
                sa.column("id", sa.Integer()),
                sa.column("enforce_sso", sa.Boolean()),
            )
            stored_value = conn.scalar(sa.select(settings.c.enforce_sso).where(settings.c.id == 1))
            enforce_sso = bool(stored_value)

        config = sa.table(_CONFIG_TABLE, sa.column("enforce_sso", sa.Boolean()))
        conn.execute(config.update().where(config.c.enforce_sso.is_(None)).values(enforce_sso=enforce_sso))

        columns = _column_names(conn, _CONFIG_TABLE)
        updated_by_foreign_key = next(
            (fk for fk in _foreign_keys(conn, _CONFIG_TABLE) if fk["constrained_columns"] == ["updated_by"]),
            None,
        )
        with op.batch_alter_table(_CONFIG_TABLE, schema=None) as batch_op:
            batch_op.alter_column("enforce_sso", existing_type=sa.Boolean(), nullable=False)
            if updated_by_foreign_key is not None and updated_by_foreign_key["name"]:
                batch_op.drop_constraint(updated_by_foreign_key["name"], type_="foreignkey")
            if "updated_by" in columns:
                batch_op.drop_column("updated_by")
            if "sort_order" in columns:
                batch_op.drop_column("sort_order")

    if migration.table_exists(_SETTINGS_TABLE, conn):
        op.drop_table(_SETTINGS_TABLE)


def _upgrade_sso_config(conn: sa.Connection) -> None:
    columns = _column_names(conn, _CONFIG_TABLE)
    if "slug" not in columns:
        op.add_column(
            _CONFIG_TABLE,
            sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )
    if "display_name" not in columns:
        op.add_column(
            _CONFIG_TABLE,
            sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )
    if "protocol" not in columns:
        op.add_column(
            _CONFIG_TABLE,
            sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )
    if "provider_settings" not in columns:
        op.add_column(_CONFIG_TABLE, sa.Column("provider_settings", sa.JSON(), nullable=True))

    _backfill_connection_identity(conn)
    _backfill_profile_connection_slugs(conn)
    _backfill_provider_settings(conn)
    _sanitize_legacy_client_secrets(conn)
    columns = _column_names(conn, _CONFIG_TABLE)
    indexes = _indexes(conn, _CONFIG_TABLE)
    with op.batch_alter_table(_CONFIG_TABLE, schema=None) as batch_op:
        batch_op.alter_column(
            "slug",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column(
            "display_name",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column(
            "protocol",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column(
            "provider_settings",
            existing_type=sa.JSON(),
            nullable=False,
        )
        if _CONFIG_SLUG_INDEX not in indexes:
            batch_op.create_index(_CONFIG_SLUG_INDEX, ["slug"], unique=True)
        for name in ("provider", "provider_name", *_PROVIDER_SETTING_COLUMNS):
            if name in columns:
                batch_op.drop_column(name)


def _downgrade_sso_config(conn: sa.Connection) -> None:
    columns = _column_names(conn, _CONFIG_TABLE)
    for name in ("provider", "provider_name", *_PROVIDER_SETTING_COLUMNS):
        if name not in columns:
            op.add_column(
                _CONFIG_TABLE,
                sa.Column(name, sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            )

    _backfill_legacy_provider_columns(conn)
    _backfill_provider_name(conn)
    _restore_profile_connection_names(conn)
    columns = _column_names(conn, _CONFIG_TABLE)
    indexes = _indexes(conn, _CONFIG_TABLE)
    with op.batch_alter_table(_CONFIG_TABLE, schema=None) as batch_op:
        batch_op.alter_column(
            "provider",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column(
            "provider_name",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        if _CONFIG_SLUG_INDEX in indexes:
            batch_op.drop_index(_CONFIG_SLUG_INDEX)
        for name in ("provider_settings", "protocol", "display_name", "slug"):
            if name in columns:
                batch_op.drop_column(name)


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(_PROFILE_TABLE, conn):
        indexes = _indexes(conn, _PROFILE_TABLE)
        user_id_index = indexes.get(_USER_ID_INDEX)
        with op.batch_alter_table(_PROFILE_TABLE, schema=None) as batch_op:
            if user_id_index and user_id_index.get("unique"):
                batch_op.drop_index(_USER_ID_INDEX)
                batch_op.create_index(_USER_ID_INDEX, ["user_id"], unique=False)
            elif user_id_index is None:
                batch_op.create_index(_USER_ID_INDEX, ["user_id"], unique=False)

            if _USER_PROVIDER_INDEX not in indexes:
                batch_op.create_index(_USER_PROVIDER_INDEX, ["user_id", "sso_provider"], unique=True)

    if migration.table_exists(_CONFIG_TABLE, conn):
        _upgrade_sso_config(conn)
        _upgrade_instance_fields(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(_CONFIG_TABLE, conn):
        _downgrade_instance_fields(conn)
        _downgrade_sso_config(conn)
    elif migration.table_exists(_SETTINGS_TABLE, conn):
        op.drop_table(_SETTINGS_TABLE)

    if migration.table_exists(_PROFILE_TABLE, conn):
        indexes = _indexes(conn, _PROFILE_TABLE)
        user_id_index = indexes.get(_USER_ID_INDEX)
        with op.batch_alter_table(_PROFILE_TABLE, schema=None) as batch_op:
            if _USER_PROVIDER_INDEX in indexes:
                batch_op.drop_index(_USER_PROVIDER_INDEX)

            if user_id_index and not user_id_index.get("unique"):
                batch_op.drop_index(_USER_ID_INDEX)
                batch_op.create_index(_USER_ID_INDEX, ["user_id"], unique=True)
            elif user_id_index is None:
                batch_op.create_index(_USER_ID_INDEX, ["user_id"], unique=True)
