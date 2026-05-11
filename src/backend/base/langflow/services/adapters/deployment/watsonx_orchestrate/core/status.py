"""Health/status helpers and metadata mapping for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from typing import Any

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


def get_agent_environments(agent: dict[str, Any]) -> list[str]:
    """Return the de-duplicated list of environment names for an agent.

    Names are surfaced as-is from the provider so the API response stays
    resilient if watsonx Orchestrate adds new environments in the future.
    Missing keys or unexpected types indicate a contract break on watsonx
    Orchestrate's side and are allowed to raise.
    """
    raw_environments = agent["environments"]
    seen: set[str] = set()
    names: list[str] = []
    for env in raw_environments:
        env_name = env["name"]
        if env_name in seen:
            continue
        seen.add(env_name)
        names.append(env_name)
    return names
