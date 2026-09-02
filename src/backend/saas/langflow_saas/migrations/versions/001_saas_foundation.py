"""SaaS foundation tables.

Creates all saas_* tables in one migration.  These tables are additive —
Langflow's own schema is never touched.

Revision ID: 001saas
Revises: (none — initial SaaS migration)
Create Date: 2025-01-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as _sa_inspect

revision: str = "001saas"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("saas",)
depends_on: str | Sequence[str] | None = None

# Use a DB-agnostic UUID type: native UUID on PostgreSQL, CHAR(36) elsewhere.
_uuid = sa.Uuid()


def _has_table(name: str) -> bool:
    """Return True if the table already exists in the target database."""
    return _sa_inspect(op.get_bind()).has_table(name)


def _seed_plans() -> None:
    """Upsert the three built-in plans. Safe to call multiple times."""
    op.execute(
        """
        INSERT INTO saas_plan
            (id, name, slug, is_active, max_flows, max_executions_per_day,
             max_members, max_storage_mb, max_api_keys, rpm_limit,
             price_monthly_cents, price_yearly_cents, created_at, updated_at)
        VALUES
            ('00000000-0000-0000-0000-000000000001', 'Free', 'free', TRUE,
             50, 1000, 5, 500, 5, 60, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('00000000-0000-0000-0000-000000000002', 'Pro', 'pro', TRUE,
             500, 10000, 25, 5000, 20, 300, 2900, 29000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('00000000-0000-0000-0000-000000000003', 'Enterprise', 'enterprise', TRUE,
             -1, -1, -1, -1, -1, 1000, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (slug) DO NOTHING
        """
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # saas_plan
    # ------------------------------------------------------------------
    if _has_table("saas_plan"):
        # Tables were already created (e.g., plugin reinstalled on existing DB).
        # Skip DDL but still re-seed plans in case the rows are missing.
        _seed_plans()
        return

    op.create_table(
        "saas_plan",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_flows", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("max_executions_per_day", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("max_members", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_storage_mb", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("max_api_keys", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("rpm_limit", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("price_monthly_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_yearly_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stripe_monthly_price_id", sa.String(), nullable=True),
        sa.Column("stripe_yearly_price_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saas_plan_slug", "saas_plan", ["slug"])
    op.create_index("ix_saas_plan_name", "saas_plan", ["name"])

    _seed_plans()

    # ------------------------------------------------------------------
    # saas_organization
    # ------------------------------------------------------------------
    op.create_table(
        "saas_organization",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column(
            "owner_id",
            _uuid,
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            _uuid,
            sa.ForeignKey("saas_plan.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saas_org_slug", "saas_organization", ["slug"])
    op.create_index("ix_saas_org_owner", "saas_organization", ["owner_id"])
    op.create_index("ix_saas_org_stripe_customer", "saas_organization", ["stripe_customer_id"])

    # ------------------------------------------------------------------
    # saas_invitation  (must exist before saas_user_organization FK)
    # ------------------------------------------------------------------
    op.create_table(
        "saas_invitation",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column(
            "org_id",
            _uuid,
            sa.ForeignKey("saas_organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column(
            "invited_by",
            _uuid,
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "accepted_by",
            _uuid,
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saas_invitation_org", "saas_invitation", ["org_id"])
    op.create_index("ix_saas_invitation_email", "saas_invitation", ["email"])
    op.create_index("ix_saas_invitation_token_hash", "saas_invitation", ["token_hash"], unique=True)

    # ------------------------------------------------------------------
    # saas_user_organization
    # ------------------------------------------------------------------
    op.create_table(
        "saas_user_organization",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column(
            "user_id",
            _uuid,
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            _uuid,
            sa.ForeignKey("saas_organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column(
            "invitation_id",
            _uuid,
            sa.ForeignKey("saas_invitation.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "org_id", name="uq_saas_user_org"),
    )
    op.create_index("ix_saas_user_org_user", "saas_user_organization", ["user_id"])
    op.create_index("ix_saas_user_org_org", "saas_user_organization", ["org_id"])

    # ------------------------------------------------------------------
    # saas_team
    # ------------------------------------------------------------------
    op.create_table(
        "saas_team",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column(
            "org_id",
            _uuid,
            sa.ForeignKey("saas_organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_saas_team_name_in_org"),
    )
    op.create_index("ix_saas_team_org", "saas_team", ["org_id"])

    # ------------------------------------------------------------------
    # saas_team_member
    # ------------------------------------------------------------------
    op.create_table(
        "saas_team_member",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column(
            "team_id",
            _uuid,
            sa.ForeignKey("saas_team.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            _uuid,
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("team_id", "user_id", name="uq_saas_team_member"),
    )
    op.create_index("ix_saas_team_member_team", "saas_team_member", ["team_id"])
    op.create_index("ix_saas_team_member_user", "saas_team_member", ["user_id"])

    # ------------------------------------------------------------------
    # saas_subscription
    # ------------------------------------------------------------------
    op.create_table(
        "saas_subscription",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column(
            "org_id",
            _uuid,
            sa.ForeignKey("saas_organization.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "plan_id",
            _uuid,
            sa.ForeignKey("saas_plan.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="trialing"),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True, unique=True),
        sa.Column("stripe_price_id", sa.String(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saas_subscription_org", "saas_subscription", ["org_id"])
    op.create_index("ix_saas_subscription_stripe", "saas_subscription", ["stripe_subscription_id"])

    # ------------------------------------------------------------------
    # saas_usage_record
    # ------------------------------------------------------------------
    op.create_table(
        "saas_usage_record",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column(
            "org_id",
            _uuid,
            sa.ForeignKey("saas_organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            _uuid,
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_saas_usage_org_metric_time",
        "saas_usage_record",
        ["org_id", "metric", "recorded_at"],
    )

    # ------------------------------------------------------------------
    # saas_audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "saas_audit_log",
        sa.Column("id", _uuid, primary_key=True),
        sa.Column(
            "org_id",
            _uuid,
            sa.ForeignKey("saas_organization.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            _uuid,
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("log_metadata", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saas_audit_org_time", "saas_audit_log", ["org_id", "created_at"])
    op.create_index("ix_saas_audit_user_time", "saas_audit_log", ["user_id", "created_at"])
    op.create_index("ix_saas_audit_action", "saas_audit_log", ["action"])


def downgrade() -> None:
    # Drop in reverse FK dependency order.
    op.drop_table("saas_audit_log")
    op.drop_table("saas_usage_record")
    op.drop_table("saas_subscription")
    op.drop_table("saas_team_member")
    op.drop_table("saas_team")
    op.drop_table("saas_user_organization")
    op.drop_table("saas_invitation")
    op.drop_table("saas_organization")
    op.drop_table("saas_plan")
