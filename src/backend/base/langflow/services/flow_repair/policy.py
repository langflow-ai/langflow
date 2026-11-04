"""The caller authorizes repair while the owner supplies component policy scope."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from lfx.services.model_provider_policy import ModelProviderPolicyPurpose, aresolve_model_provider_policy
from lfx.upgrade.checker import build_registry_lookup
from lfx.utils.flow_validation import prepare_flow_build_for_user_from_cache, validate_catalog_policy_for_flow

from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_catalog_policy_service
from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow


async def require_admin(session: AsyncSession, actor_id: UUID) -> User:
    actor = await session.get(User, actor_id, populate_existing=True)
    if actor is None or not actor.is_active or await get_auth_service().get_current_active_superuser(actor) is None:
        raise HTTPException(status_code=403, detail="Active superuser access is required")
    return actor


async def authorize_flow(session: AsyncSession, flow: Flow, actor: User) -> User | None:
    await ensure_flow_permission(
        actor,
        FlowAction.WRITE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )
    owner = await session.get(User, flow.user_id) if flow.user_id is not None else None
    return owner if owner is not None and owner.is_active else None


def _component_providers(graph: dict, registry: Mapping[str, dict]) -> set[str]:
    providers = set()
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        entry = registry.get(data.get("type"), {})
        provider = (entry.get("metadata") or {}).get("model_provider_id")
        if isinstance(provider, str) and provider:
            providers.add(provider)
        nested = (data.get("node") or {}).get("flow", {}).get("data")
        if nested:
            providers.update(_component_providers(nested, registry))
    return providers


async def validate_owner_policy(flow: Flow, owner: User, updated: dict, all_types: Mapping[str, Any]) -> None:
    with scoped_model_provider_policy_for_flow(flow, user_id=owner.id, is_superuser=bool(owner.is_superuser)):
        validate_catalog_policy_for_flow(updated, snapshot=get_catalog_policy_service().snapshot)
        prepare_flow_build_for_user_from_cache(updated, is_superuser=bool(owner.is_superuser))
        providers = _component_providers(updated, build_registry_lookup(all_types))
        if providers:
            policy = await aresolve_model_provider_policy(
                user_id=owner.id,
                providers=providers,
                purpose=ModelProviderPolicyPurpose.USE,
            )
            for provider in providers:
                policy.require(provider)
