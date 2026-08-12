"""Add immutable shared provider and catalog policy bundles.

Phase: EXPAND
Revision ID: f7a9c2d4e6b8
Revises: 8d9e0f1a2b3c
Create Date: 2026-08-05 00:00:00.000000

The legacy provider singleton and catalog rule tables remain in place for
already-running legacy services during the mixed-version window and for a
qualified rollback image that recognizes the preceding migration head. The
initial active revision is a complete snapshot of their currently enforced
global policy. A previously shipped image that does not recognize the preceding
head still requires a pre-upgrade database restore.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f7a9c2d4e6b8"  # pragma: allowlist secret
down_revision: str | None = "8d9e0f1a2b3c"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISION_TABLE = "policy_bundle_revision"
ACTIVE_TABLE = "policy_bundle_active"
SINGLETON_ID = 1
REASON_MAX_LENGTH = 1024
SOURCE_MAX_LENGTH = 32
_REVISION_COLUMNS = frozenset(
    {
        "revision",
        "initialized",
        "approved_provider_ids",
        "blocked_component_keys",
        "blocked_template_keys",
        "content_hash",
        "source",
        "created_by",
        "created_at",
        "reason",
        "rollback_of_revision",
    }
)
_ACTIVE_COLUMNS = frozenset({"id", "revision", "initialized", "updated_at"})


def _canonical_hash(
    approved_provider_ids: list[str],
    blocked_component_keys: list[str],
    blocked_template_keys: list[str],
) -> str:
    payload = {
        "approved_provider_ids": sorted(set(approved_provider_ids)),
        "blocked_component_keys": sorted(set(blocked_component_keys)),
        "blocked_template_keys": sorted(set(blocked_template_keys)),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _revision_table() -> sa.TableClause:
    return sa.table(
        REVISION_TABLE,
        sa.column("revision", sa.Integer()),
        sa.column("initialized", sa.Boolean()),
        sa.column("approved_provider_ids", sa.JSON()),
        sa.column("blocked_component_keys", sa.JSON()),
        sa.column("blocked_template_keys", sa.JSON()),
        sa.column("content_hash", sa.String(64)),
        sa.column("source", sa.String(SOURCE_MAX_LENGTH)),
        sa.column("created_by", sa.Uuid()),
        sa.column("reason", sa.String(REASON_MAX_LENGTH)),
        sa.column("rollback_of_revision", sa.Integer()),
    )


def _active_table() -> sa.TableClause:
    return sa.table(
        ACTIVE_TABLE,
        sa.column("id", sa.Integer()),
        sa.column("revision", sa.Integer()),
        sa.column("initialized", sa.Boolean()),
    )


def _legacy_provider_table() -> sa.TableClause:
    return sa.table(
        "model_provider_policy",
        sa.column("id", sa.Integer()),
        sa.column("approved_provider_ids", sa.JSON()),
        sa.column("version", sa.Integer()),
    )


def _legacy_catalog_table() -> sa.TableClause:
    return sa.table(
        "catalog_policy_rule",
        sa.column("id", sa.Uuid()),
        sa.column("resource_kind", sa.String()),
        sa.column("resource_key", sa.String()),
        sa.column("mode", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("domain_id", sa.Uuid()),
        sa.column("created_by", sa.Uuid()),
    )


def _validate_columns(conn: sa.Connection, table_name: str, required: frozenset[str]) -> None:
    columns = {column["name"] for column in sa.inspect(conn).get_columns(table_name)}
    missing = required - columns
    if missing:
        detail = ", ".join(sorted(missing))
        msg = f"Existing {table_name!r} table is missing required columns: {detail}"
        raise RuntimeError(msg)


def _legacy_snapshot(conn: sa.Connection) -> tuple[int, bool, list[str], list[str], list[str]]:
    provider_table = _legacy_provider_table()
    provider = (
        conn.execute(
            sa.select(provider_table.c.approved_provider_ids, provider_table.c.version).where(
                provider_table.c.id == SINGLETON_ID
            )
        )
        .mappings()
        .one_or_none()
    )
    if provider is None:
        msg = "Model-provider policy singleton is missing; apply the prerequisite migration"
        raise RuntimeError(msg)

    catalog_table = _legacy_catalog_table()
    rows = conn.execute(
        sa.select(catalog_table.c.resource_kind, catalog_table.c.resource_key).where(
            catalog_table.c.mode == "block",
            catalog_table.c.scope == "global",
            catalog_table.c.domain_id.is_(None),
            catalog_table.c.resource_kind.in_(("component", "template")),
        )
    ).all()
    components = sorted({row.resource_key for row in rows if row.resource_kind == "component"})
    templates = sorted({row.resource_key for row in rows if row.resource_kind == "template"})
    provider_ids = sorted(set(provider["approved_provider_ids"] or []))
    provider_version = int(provider["version"])
    initialized = bool(provider_version > 0 or provider_ids or components or templates)
    return max(1, provider_version), initialized, provider_ids, components, templates


def _seed_active_bundle(conn: sa.Connection) -> None:
    revision_table = _revision_table()
    active_table = _active_table()
    active = conn.execute(sa.select(active_table.c.revision).where(active_table.c.id == SINGLETON_ID)).first()
    if active is not None:
        exists = conn.execute(
            sa.select(revision_table.c.revision).where(revision_table.c.revision == active.revision)
        ).first()
        if exists is None:
            msg = "Active policy bundle points to a missing immutable revision"
            raise RuntimeError(msg)
        return

    if conn.execute(sa.select(revision_table.c.revision).limit(1)).first() is not None:
        msg = "Policy bundle history exists without an active singleton pointer"
        raise RuntimeError(msg)

    initial_revision, initialized, provider_ids, components, templates = _legacy_snapshot(conn)
    conn.execute(
        revision_table.insert().values(
            revision=initial_revision,
            initialized=initialized,
            approved_provider_ids=provider_ids,
            blocked_component_keys=components,
            blocked_template_keys=templates,
            content_hash=_canonical_hash(provider_ids, components, templates),
            source="migration",
            created_by=None,
            reason="Migrated existing provider and catalog policy",
            rollback_of_revision=None,
        )
    )
    conn.execute(
        active_table.insert().values(
            id=SINGLETON_ID,
            revision=initial_revision,
            initialized=initialized,
        )
    )


def _create_revision_table() -> None:
    op.create_table(
        REVISION_TABLE,
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("initialized", sa.Boolean(), nullable=False),
        sa.Column("approved_provider_ids", sa.JSON(), nullable=False),
        sa.Column("blocked_component_keys", sa.JSON(), nullable=False),
        sa.Column("blocked_template_keys", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=SOURCE_MAX_LENGTH), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reason", sa.String(length=REASON_MAX_LENGTH), nullable=True),
        sa.Column("rollback_of_revision", sa.Integer(), nullable=True),
        sa.CheckConstraint("revision >= 1", name="ck_policy_bundle_revision_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_policy_bundle_revision_hash_length"),
        sa.ForeignKeyConstraint(
            ["rollback_of_revision"],
            [f"{REVISION_TABLE}.revision"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("revision"),
    )


def _create_active_table() -> None:
    op.create_table(
        ACTIVE_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("initialized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"id = {SINGLETON_ID}", name="ck_policy_bundle_active_singleton"),
        sa.CheckConstraint("revision >= 1", name="ck_policy_bundle_active_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade() -> None:
    """Create and seed the additive shared policy bundle store."""
    conn = op.get_bind()
    revision_exists = migration.table_exists(REVISION_TABLE, conn)
    active_exists = migration.table_exists(ACTIVE_TABLE, conn)
    if revision_exists:
        _validate_columns(conn, REVISION_TABLE, _REVISION_COLUMNS)
    if active_exists:
        _validate_columns(conn, ACTIVE_TABLE, _ACTIVE_COLUMNS)

    if revision_exists != active_exists:
        existing_table = _revision_table() if revision_exists else _active_table()
        existing_key = existing_table.c.revision if revision_exists else existing_table.c.id
        if conn.execute(sa.select(existing_key).limit(1)).first() is not None:
            msg = "Shared policy bundle schema is partially initialized with durable data"
            raise RuntimeError(msg)

    if not revision_exists:
        _create_revision_table()
    if not active_exists:
        _create_active_table()

    _seed_active_bundle(conn)


def _sync_legacy_policy(conn: sa.Connection) -> None:
    revision_table = _revision_table()
    active_table = _active_table()
    active = (
        conn.execute(
            sa.select(active_table.c.revision, active_table.c.initialized).where(active_table.c.id == SINGLETON_ID)
        )
        .mappings()
        .one_or_none()
    )
    if active is None:
        if conn.execute(sa.select(sa.literal(1)).select_from(revision_table).limit(1)).first() is not None:
            msg = "Shared policy bundle has immutable revision history but no active singleton"
            raise RuntimeError(msg)
        return
    active_revision = active["revision"]
    bundle = (
        conn.execute(sa.select(revision_table).where(revision_table.c.revision == active_revision))
        .mappings()
        .one_or_none()
    )
    if bundle is None:
        msg = "Active policy bundle points to a missing immutable revision"
        raise RuntimeError(msg)

    provider_table = _legacy_provider_table()
    conn.execute(
        provider_table.update()
        .where(provider_table.c.id == SINGLETON_ID)
        .values(
            approved_provider_ids=bundle["approved_provider_ids"],
            # The legacy version is the only pristine/bootstrap sentinel.
            # Preserve it across downgrade so a later re-upgrade can still
            # perform the one-time Enterprise environment bootstrap.
            version=active_revision if active["initialized"] else 0,
        )
    )

    catalog_table = _legacy_catalog_table()
    conn.execute(
        catalog_table.delete().where(
            catalog_table.c.mode == "block",
            catalog_table.c.scope == "global",
            catalog_table.c.domain_id.is_(None),
            catalog_table.c.resource_kind.in_(("component", "template")),
        )
    )
    for resource_kind, keys in (
        ("component", bundle["blocked_component_keys"]),
        ("template", bundle["blocked_template_keys"]),
    ):
        for key in keys:
            conn.execute(
                catalog_table.insert().values(
                    id=uuid4(),
                    resource_kind=resource_kind,
                    resource_key=key,
                    mode="block",
                    scope="global",
                    domain_id=None,
                    # Bundle history deliberately retains actor UUIDs after a
                    # user is deleted, while this legacy table has a user FK.
                    # Never let a dangling historical actor block rollback.
                    created_by=None,
                )
            )


def downgrade() -> None:
    """Copy the active bundle to legacy stores before removing new tables."""
    conn = op.get_bind()
    revision_exists = migration.table_exists(REVISION_TABLE, conn)
    active_exists = migration.table_exists(ACTIVE_TABLE, conn)
    if revision_exists != active_exists:
        existing_table = _revision_table() if revision_exists else _active_table()
        if conn.execute(sa.select(sa.literal(1)).select_from(existing_table).limit(1)).first() is not None:
            msg = "Shared policy bundle schema is partially initialized with durable data"
            raise RuntimeError(msg)
        if active_exists:
            op.drop_table(ACTIVE_TABLE)
        if revision_exists:
            op.drop_table(REVISION_TABLE)
        return

    if not revision_exists:
        return

    _sync_legacy_policy(conn)
    op.drop_table(ACTIVE_TABLE)
    op.drop_table(REVISION_TABLE)
