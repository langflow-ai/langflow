"""Pydantic schemas for /api/v1/authz/role-assignments."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# Recognized domain categories for ``authz_role_assignment.domain_type``.
# ``global``  — assignment is unscoped, ``domain_id`` MUST be null.
# ``org`` / ``workspace`` / ``project`` — scoped, ``domain_id`` MUST be set.
# Keeping this as a ``Literal`` rejects free-form strings at the API
# boundary instead of letting a typo (``"organization"``) silently
# create a row that no enforcer will ever match.
DomainType = Literal["global", "org", "workspace", "project"]


class RoleAssignmentCreate(BaseModel):
    """Payload for assigning a role to a user."""

    user_id: UUID
    role_id: UUID
    domain_type: DomainType = Field(
        default="global",
        description=(
            "Domain scope of the assignment. ``global`` is unscoped (no "
            "``domain_id``); ``org``/``workspace``/``project`` require a "
            "matching ``domain_id``."
        ),
    )
    domain_id: UUID | None = Field(
        default=None,
        description="Required when ``domain_type`` is org/workspace/project; must be null for ``global``.",
    )

    @model_validator(mode="after")
    def _check_domain_id_consistency(self) -> RoleAssignmentCreate:
        if self.domain_type == "global" and self.domain_id is not None:
            msg = "domain_id must be null when domain_type='global'"
            raise ValueError(msg)
        # org / workspace / project all require an id — without one the
        # assignment cannot match any concrete domain in the enforcer.
        if self.domain_type != "global" and self.domain_id is None:
            msg = f"domain_id is required when domain_type={self.domain_type!r}"
            raise ValueError(msg)
        return self


class RoleAssignmentRead(BaseModel):
    """Serialized authz_role_assignment row returned by the API."""

    id: UUID
    user_id: UUID
    role_id: UUID
    domain_type: str
    domain_id: UUID | None
    assigned_at: datetime
    assigned_by: UUID | None

    model_config = {"from_attributes": True}
