"""Immutable deployment policy bundle history and active revision pointer."""

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr

POLICY_BUNDLE_SINGLETON_ID = 1
POLICY_BUNDLE_REASON_MAX_LENGTH = 1024
POLICY_BUNDLE_SOURCE_MAX_LENGTH = 32


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyBundleRevision(SQLModel, table=True):  # type: ignore[call-arg]
    """One immutable, complete deployment-governance policy revision."""

    __tablename__ = "policy_bundle_revision"
    __table_args__ = (
        sa.CheckConstraint("revision >= 1", name="ck_policy_bundle_revision_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_policy_bundle_revision_hash_length"),
    )

    revision: int = Field(primary_key=True, ge=1)
    initialized: bool = Field(default=True, sa_column=sa.Column(sa.Boolean(), nullable=False))
    approved_provider_ids: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON, nullable=False))
    blocked_component_keys: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON, nullable=False))
    blocked_template_keys: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON, nullable=False))
    # Nullable with a server default to match the EXPAND-phase migration:
    # revisions written before the column existed read back as "blocks
    # nothing" without a backfill. Writers always provide the value.
    blocked_model_keys: list[str] = Field(
        default_factory=list,
        sa_column=sa.Column(sa.JSON, nullable=True, server_default=sa.text("'[]'")),
    )
    content_hash: str = Field(sa_column=sa.Column(sa.String(64), nullable=False))
    source: str = Field(
        default="api",
        max_length=POLICY_BUNDLE_SOURCE_MAX_LENGTH,
        sa_column=sa.Column(sa.String(POLICY_BUNDLE_SOURCE_MAX_LENGTH), nullable=False),
    )
    created_by: UUIDstr | None = Field(
        default=None,
        # Immutable history keeps actor attribution even if the user row is
        # later deleted; authentication validates the actor before insertion.
        sa_column=sa.Column(sa.Uuid(), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    reason: str | None = Field(
        default=None,
        max_length=POLICY_BUNDLE_REASON_MAX_LENGTH,
        sa_column=sa.Column(sa.String(POLICY_BUNDLE_REASON_MAX_LENGTH), nullable=True),
    )
    rollback_of_revision: int | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Integer(),
            sa.ForeignKey("policy_bundle_revision.revision", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class PolicyBundleActive(SQLModel, table=True):  # type: ignore[call-arg]
    """Singleton pointer used to allocate and activate revisions with CAS."""

    __tablename__ = "policy_bundle_active"
    __table_args__ = (
        sa.CheckConstraint(
            f"id = {POLICY_BUNDLE_SINGLETON_ID}",
            name="ck_policy_bundle_active_singleton",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_policy_bundle_active_revision_positive"),
    )

    id: int = Field(default=POLICY_BUNDLE_SINGLETON_ID, primary_key=True)
    # Deliberately no FK: writers CAS this pointer before inserting the new
    # immutable revision in the same transaction. No reader can observe the
    # uncommitted pointer, and a failed insert rolls the CAS back atomically.
    revision: int = Field(nullable=False, ge=1)
    initialized: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
