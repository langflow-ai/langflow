"""All SaaS database models.

Every table is prefixed with ``saas_`` to avoid any collision with
Langflow's own tables.  Foreign keys to Langflow's ``user`` table use
ON DELETE CASCADE / SET NULL so removing a Langflow user automatically
cleans up all SaaS artefacts.

Upgrade safety: these models never import Langflow model *classes* — only
primitive types and ``sqlalchemy``.  This means Langflow can rename its
internal model fields without breaking this package.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, Column, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"


class UsageMetric(str, enum.Enum):
    FLOW_EXECUTION = "flow_execution"
    API_CALL = "api_call"
    STORAGE_BYTES = "storage_bytes"


# ---------------------------------------------------------------------------
# Plan  (created at deployment time / via admin, not user-facing CRUD)
# ---------------------------------------------------------------------------


class Plan(SQLModel, table=True):  # type: ignore[call-arg]
    """Pricing plan / tier definition.  Rows are managed by operators."""

    __tablename__ = "saas_plan"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)  # "Free", "Pro", "Enterprise"
    slug: str = Field(unique=True, index=True)  # "free", "pro", "enterprise"
    is_active: bool = Field(default=True)
    # Quotas (-1 = unlimited)
    max_flows: int = Field(default=50)
    max_executions_per_day: int = Field(default=1000)
    max_members: int = Field(default=5)
    max_storage_mb: int = Field(default=500)
    max_api_keys: int = Field(default=5)
    # Rate limits
    rpm_limit: int = Field(default=60, description="Requests per minute for this plan.")
    # Billing
    price_monthly_cents: int = Field(default=0)
    price_yearly_cents: int = Field(default=0)
    stripe_monthly_price_id: str | None = Field(default=None)
    stripe_yearly_price_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------


class Organization(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_organization"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    owner_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    plan_id: UUID | None = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_plan.id", ondelete="SET NULL"), nullable=True)
    )
    # Personal orgs are created automatically for every user and cannot be
    # renamed, shared, or deleted while the user exists.
    is_personal: bool = Field(default=False)
    is_active: bool = Field(default=True)
    stripe_customer_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# UserOrganization  (membership + role)
# ---------------------------------------------------------------------------


class UserOrganization(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_user_organization"
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_saas_user_org"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    org_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_organization.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    role: OrgRole = Field(default=OrgRole.MEMBER)
    # Tracks which invitation brought this member in; nullable for founders.
    invitation_id: UUID | None = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_invitation.id", ondelete="SET NULL"), nullable=True)
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Team  (sub-group inside an org)
# ---------------------------------------------------------------------------


class Team(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_team"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_organization.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    name: str = Field()
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_saas_team_name_in_org"),)


class TeamMember(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_team_member"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_saas_team_member"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_team.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    user_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Invitation
# ---------------------------------------------------------------------------


class Invitation(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_invitation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_organization.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    email: str = Field(index=True)
    role: OrgRole = Field(default=OrgRole.MEMBER)
    invited_by: UUID = Field(sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False))
    # HMAC-signed token — the actual secret is derived from the invitation ID
    # and SAAS_INVITATION_SECRET so the token is never stored in cleartext.
    token_hash: str = Field(unique=True, index=True)
    status: InvitationStatus = Field(default=InvitationStatus.PENDING)
    expires_at: datetime = Field()
    accepted_at: datetime | None = Field(default=None)
    accepted_by: UUID | None = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------


class Subscription(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_subscription"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("saas_organization.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,  # one active subscription per org
            index=True,
        )
    )
    plan_id: UUID = Field(sa_column=Column(sa.Uuid(), ForeignKey("saas_plan.id", ondelete="RESTRICT"), nullable=False))
    status: SubscriptionStatus = Field(default=SubscriptionStatus.TRIALING)
    stripe_subscription_id: str | None = Field(default=None, unique=True, index=True)
    stripe_price_id: str | None = Field(default=None)
    current_period_start: datetime | None = Field(default=None)
    current_period_end: datetime | None = Field(default=None)
    cancel_at_period_end: bool = Field(default=False)
    trial_end: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# UsageRecord  (append-only metering log; roll-up queries for quota checks)
# ---------------------------------------------------------------------------


class UsageRecord(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_usage_record"
    __table_args__ = (
        # Composite index for the quota-check query:
        # WHERE org_id=? AND metric=? AND recorded_at >= today
        Index("ix_saas_usage_org_metric_time", "org_id", "metric", "recorded_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_organization.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: UUID | None = Field(sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    metric: UsageMetric = Field()
    # For FLOW_EXECUTION / API_CALL: value=1 per event.
    # For STORAGE_BYTES: value = delta bytes (can be negative for deletions).
    value: int = Field(default=1)
    # Resource that triggered the usage (e.g. flow_id for executions).
    resource_id: str | None = Field(default=None)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# AuditLog  (immutable append-only; never update or delete rows)
# ---------------------------------------------------------------------------


class AuditLog(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "saas_audit_log"
    __table_args__ = (
        Index("ix_saas_audit_org_time", "org_id", "created_at"),
        Index("ix_saas_audit_user_time", "user_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Nullable so system-level events (e.g. Stripe webhook) don't require a user.
    org_id: UUID | None = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_organization.id", ondelete="SET NULL"), nullable=True)
    )
    user_id: UUID | None = Field(sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    # Dot-separated action name: "org.created", "member.invited", "subscription.upgraded"
    action: str = Field(index=True)
    resource_type: str | None = Field(default=None)  # "flow", "org", "team", …
    resource_id: str | None = Field(default=None)
    log_metadata: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    ip_address: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Pydantic response / request schemas (separate from table models)
# ---------------------------------------------------------------------------


class PlanRead(SQLModel):
    id: UUID
    name: str
    slug: str
    max_flows: int
    max_executions_per_day: int
    max_members: int
    max_storage_mb: int
    rpm_limit: int
    price_monthly_cents: int
    price_yearly_cents: int
    is_active: bool


class OrganizationCreate(SQLModel):
    name: str
    slug: str | None = None


class OrganizationRead(SQLModel):
    id: UUID
    name: str
    slug: str
    owner_id: UUID
    is_personal: bool
    is_active: bool
    created_at: datetime
    role: OrgRole | None = None  # caller's role — filled at query time
    plan: PlanRead | None = None


class OrganizationUpdate(SQLModel):
    name: str | None = None
    slug: str | None = None


class MemberRead(SQLModel):
    user_id: UUID
    username: str
    role: OrgRole
    joined_at: datetime


class InvitationCreate(SQLModel):
    email: str
    role: OrgRole = OrgRole.MEMBER


class InvitationRead(SQLModel):
    id: UUID
    email: str
    role: OrgRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class TeamCreate(SQLModel):
    name: str
    description: str | None = None


class TeamRead(SQLModel):
    id: UUID
    org_id: UUID
    name: str
    description: str | None


class UsageSummary(SQLModel):
    org_id: UUID
    executions_today: int
    executions_limit: int
    flows_count: int
    flows_limit: int
    storage_mb: float
    storage_limit_mb: int
    api_calls_today: int
    plan_slug: str


class SubscriptionRead(SQLModel):
    id: UUID
    org_id: UUID
    status: SubscriptionStatus
    plan: PlanRead
    current_period_end: datetime | None
    cancel_at_period_end: bool
    trial_end: datetime | None


# ---------------------------------------------------------------------------
# SaaS Alembic version tracking table
# Declared as a SQLModel so it appears in SQLModel.metadata — this prevents
# Langflow's migration drift-checker from flagging it as an unknown table.
# ---------------------------------------------------------------------------


class SaasAlembicVersion(SQLModel, table=True):  # type: ignore[call-arg]
    """Tracks the applied SaaS migration revisions (mirrors alembic_version)."""

    __tablename__ = "saas_alembic_version"

    version_num: str = Field(primary_key=True, max_length=32)


# ---------------------------------------------------------------------------
# FlowOrg  (shadow table — links Langflow flows to SaaS orgs)
# ---------------------------------------------------------------------------


class FlowOrg(SQLModel, table=True):  # type: ignore[call-arg]
    """Maps a Langflow flow (by its UUID) to the org that owns it.

    Never touches Langflow's ``flow`` table — pure shadow so the SaaS layer
    can filter/share flows without modifying core Langflow.  One flow belongs
    to at most one org at a time.
    """

    __tablename__ = "saas_flow_org"
    __table_args__ = (Index("ix_saas_flow_org_org", "org_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(sa_column=Column(sa.Uuid(), nullable=False, unique=True, index=True))
    org_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("saas_organization.id", ondelete="CASCADE"), nullable=False)
    )
    assigned_by: UUID | None = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    )
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# SQLModel metadata — exported so Alembic env.py can include it
# ---------------------------------------------------------------------------

saas_metadata = SQLModel.metadata
