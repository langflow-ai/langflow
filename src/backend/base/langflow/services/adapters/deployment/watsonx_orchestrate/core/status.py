"""Health/status helpers and metadata mapping for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from typing import Any

from ibm_watsonx_orchestrate_core.types.connections import ConnectionEnvironment
from lfx.services.adapters.deployment.schema import DeploymentGetResult, DeploymentType, ItemResult


def get_deployment_metadata(
    data: dict[str, Any],
    deployment_type: DeploymentType,
    provider_data: dict[str, Any] | None = None,
) -> ItemResult:
    result: dict[str, Any] = {
        "id": data.get("id"),
        "type": deployment_type.value,
        "name": data.get("name"),
        "created_at": data.get("created_on"),
        "updated_at": data.get("updated_at"),
    }
    if provider_data:
        result["provider_data"] = provider_data

    return ItemResult(**result)


def get_deployment_detail_metadata(
    data: dict[str, Any],
    deployment_type: DeploymentType,
    provider_data: dict[str, Any] | None = None,
    provider_raw: bool = False,  # noqa: FBT001,FBT002
) -> DeploymentGetResult:
    result: dict[str, Any] = {
        "id": data.get("id"),
        "type": deployment_type.value,
        "name": data.get("name"),
        "description": data.get("description"),
    }
    if provider_data:
        result["provider_data"] = provider_data
    if provider_raw:
        result["provider_data"] = data if not provider_data else {**provider_data, "provider_raw": data}

    return DeploymentGetResult(**result)


def derive_agent_environment(agent: dict[str, Any]) -> str:
    environments = agent.get("environments", [])
    if not isinstance(environments, list) or not environments:
        return "unknown"

    has_draft = False
    has_live = False
    for env in environments:
        if not isinstance(env, dict):
            continue
        env_name = str(env.get("name", "")).strip().lower()
        if env_name == ConnectionEnvironment.DRAFT.value:
            has_draft = True
            continue
        if env_name:
            has_live = True

    if has_draft and has_live:
        return "both"
    if has_live:
        return "live"
    if has_draft:
        return "draft"
    return "unknown"
