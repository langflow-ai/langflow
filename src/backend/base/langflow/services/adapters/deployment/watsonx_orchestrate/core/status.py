"""Health/status helpers and metadata mapping for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ibm_watsonx_orchestrate_core.types.connections import ConnectionEnvironment
from lfx.services.adapters.deployment.schema import DeploymentGetResult, DeploymentType, ItemResult

if TYPE_CHECKING:
    from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient


def resolve_health_environment_id(agent_client: AgentClient, *, deployment_id: str) -> str:
    environments = agent_client.get_environments_for_agent(deployment_id)
    if not environments:
        msg = f"No environments found for deployment '{deployment_id}'."
        raise ValueError(msg)

    draft_env_id: str | None = None
    for env in environments:
        env_name = str(env.get("name", "")).strip().lower()
        env_id = str(env.get("id", "")).strip()
        if env_name == ConnectionEnvironment.DRAFT.value and env_id:
            draft_env_id = env_id
            break

    if draft_env_id:
        return draft_env_id

    first_env_id = str(environments[0].get("id", "")).strip()
    if first_env_id:
        return first_env_id
    msg = f"Could not resolve environment id for deployment '{deployment_id}'."
    raise ValueError(msg)


def fetch_agent_release_status(
    agent_client: AgentClient,
    *,
    deployment_id: str,
    environment_id: str,
) -> dict[str, Any]:
    return agent_client._get(  # noqa: SLF001
        f"/orchestrate/agents/{deployment_id}/releases/status",
        params={"environment_id": environment_id},
    )


def normalize_release_status(provider_status: dict[str, Any]) -> str:
    status_candidates = [
        provider_status.get("status"),
        provider_status.get("deployment_status"),
        provider_status.get("state"),
    ]
    for candidate in status_candidates:
        normalized = str(candidate or "").strip().lower()
        if normalized:
            return normalized
    return "unknown"


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


def derive_agent_mode(agent: dict[str, Any]) -> str:
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
