"""Catalog-governance policy storage."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, text
from sqlmodel import Field, SQLModel
from sqlmodel.sql.sqltypes import AutoString

from langflow.schema.serialize import UUIDstr


class CatalogResourceKind(str, Enum):
    """Kinds of catalog resources that can be governed."""

    COMPONENT = "component"
    TEMPLATE = "template"


class CatalogPolicyMode(str, Enum):
    """Catalog policy modes.

    ``ALLOW`` is reserved for a future allowlist phase. P1 only writes block
    rules, but the schema can accept the future value without another enum
    migration.
    """

    BLOCK = "block"
    ALLOW = "allow"


class CatalogPolicyScope(str, Enum):
    """Policy scopes.

    P1 uses only ``GLOBAL``. Organization and workspace values reserve the
    existing authorization domain shape for a later scoped-policy phase.
    """

    GLOBAL = "global"
    ORG = "org"
    WORKSPACE = "workspace"


def _tz_aware_now() -> datetime:
    return datetime.now(timezone.utc)


class CatalogPolicyRule(SQLModel, table=True):  # type: ignore[call-arg]
    """A block or allow rule for a component type or template id."""

    __tablename__ = "catalog_policy_rule"
    __table_args__ = (
        CheckConstraint(
            "resource_kind IN ('component', 'template')",
            name="ck_catalog_policy_rule_resource_kind",
        ),
        CheckConstraint(
            "mode IN ('block', 'allow')",
            name="ck_catalog_policy_rule_mode",
        ),
        CheckConstraint(
            "scope IN ('global', 'org', 'workspace')",
            name="ck_catalog_policy_rule_scope",
        ),
        CheckConstraint(
            "(scope = 'global' AND domain_id IS NULL) OR (scope IN ('org', 'workspace') AND domain_id IS NOT NULL)",
            name="ck_catalog_policy_rule_scope_domain_consistency",
        ),
        Index(
            "uq_catalog_policy_rule_scoped",
            "resource_kind",
            "resource_key",
            "scope",
            "domain_id",
            unique=True,
            postgresql_where=text("domain_id IS NOT NULL"),
            sqlite_where=text("domain_id IS NOT NULL"),
        ),
        Index(
            "uq_catalog_policy_rule_unscoped",
            "resource_kind",
            "resource_key",
            "scope",
            unique=True,
            postgresql_where=text("domain_id IS NULL"),
            sqlite_where=text("domain_id IS NULL"),
        ),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    resource_kind: str
    resource_key: str
    mode: str = Field(
        default=CatalogPolicyMode.BLOCK.value,
        sa_column=Column(AutoString(), nullable=False, server_default=sa.text("'block'")),
    )
    scope: str = Field(
        default=CatalogPolicyScope.GLOBAL.value,
        sa_column=Column(AutoString(), nullable=False, server_default=sa.text("'global'")),
    )
    domain_id: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), nullable=True),
    )
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=_tz_aware_now,
        sa_column=Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    updated_at: datetime = Field(
        default_factory=_tz_aware_now,
        sa_column=Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
