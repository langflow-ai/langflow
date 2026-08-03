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

    P1 reads and writes only ``BLOCK`` rules. ``ALLOW`` is a schema reservation
    for a future allowlist phase and has no P1 resolution semantics.
    """

    BLOCK = "block"
    ALLOW = "allow"


class CatalogPolicyScope(str, Enum):
    """Policy scopes.

    P1 reads and writes only ``GLOBAL`` rules. Organization and workspace
    values reserve the existing authorization domain shape for a later
    scoped-policy phase and have no P1 resolution semantics.
    """

    GLOBAL = "global"
    ORG = "org"
    WORKSPACE = "workspace"


def _enum_values_sql(enum_type: type[Enum]) -> str:
    """Return safely quoted SQL literals for a closed internal string enum."""
    return ", ".join(f"'{member.value}'" for member in enum_type)


_RESOURCE_KIND_CHECK = f"resource_kind IN ({_enum_values_sql(CatalogResourceKind)})"
_MODE_CHECK = f"mode IN ({_enum_values_sql(CatalogPolicyMode)})"
_SCOPE_CHECK = f"scope IN ({_enum_values_sql(CatalogPolicyScope)})"
_SCOPED_VALUES_SQL = ", ".join(f"'{scope.value}'" for scope in (CatalogPolicyScope.ORG, CatalogPolicyScope.WORKSPACE))
_SCOPE_DOMAIN_CHECK = (
    f"(scope = '{CatalogPolicyScope.GLOBAL.value}' AND domain_id IS NULL) "
    f"OR (scope IN ({_SCOPED_VALUES_SQL}) AND domain_id IS NOT NULL)"
)


def _tz_aware_now() -> datetime:
    """Return the current UTC timestamp for in-memory model defaults."""
    return datetime.now(timezone.utc)


class CatalogPolicyRule(SQLModel, table=True):  # type: ignore[call-arg]
    """A catalog rule keyed by an exact, case-sensitive resource identifier.

    The P1 service considers only global block rules; reserved allow/scoped rows
    are ignored until a future phase defines their resolution semantics. The
    unique indexes prevent contradictory modes for the same resource and
    domain, while intentionally allowing distinct resources in one scope.
    """

    __tablename__ = "catalog_policy_rule"
    __table_args__ = (
        CheckConstraint(
            _RESOURCE_KIND_CHECK,
            name="ck_catalog_policy_rule_resource_kind",
        ),
        CheckConstraint(
            _MODE_CHECK,
            name="ck_catalog_policy_rule_mode",
        ),
        CheckConstraint(
            _SCOPE_CHECK,
            name="ck_catalog_policy_rule_scope",
        ),
        CheckConstraint(
            _SCOPE_DOMAIN_CHECK,
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
