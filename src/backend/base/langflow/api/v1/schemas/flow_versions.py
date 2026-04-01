from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from pydantic import Field as PydanticField

from langflow.services.database.models.flow_version.model import FlowVersionRead


class FlowVersionDeploymentInfo(BaseModel):
    """Per-deployment tool metadata surfaced when listing flow versions."""

    # TODO: be more provider-agnostic here. see RULES.md
    deployment_id: UUID
    tool_id: str | None = None
    tool_name: str | None = None


class FlowVersionReadWithDeployments(FlowVersionRead):
    """FlowVersionRead enriched with per-deployment tool metadata."""

    deployments: list[FlowVersionDeploymentInfo] = PydanticField(default_factory=list)


class FlowVersionWithDeploymentsListResponse(BaseModel):
    """List response used when deployment enrichment is active."""

    entries: list[FlowVersionReadWithDeployments]
    max_entries: int = PydanticField(ge=1)
