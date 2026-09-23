"""Effective integration policy and the governed provider catalog (INT-7).

The UI never decides what is available: it renders what this API returns. B9
(the operator integration-policy panel) and INT-8 (the connection picker) both
read the effective policy here rather than reimplementing the ceiling and the
deny-list, so a client that ignores it still fails closed at execution.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from lfx.integrations.models import PROVIDER_ID_PATTERN
from lfx.services.deps import get_integration_policy_service
from lfx.services.integration_policy import IntegrationPolicyPurpose, aresolve_integration_policy
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser, DbSessionReadOnly
from langflow.api.v1.connections import ConnectionService
from langflow.api.v1.model_provider_policy_scope import ProviderPolicyAttributesDependency
from langflow.services.rate_limit import check_rate_limit, get_metadata_read_limit, get_user_limiter_key

router = APIRouter(prefix="/integrations", tags=["Integrations"])

# Counter namespace shared by the catalog reads; distinct from the connections
# buckets so browsing the catalog cannot consume mutation/OAuth budget.
# Catalog and policy reads carry no credential material and make no outbound
# call, so they share the connections metadata-read budget rather than the
# login budget: the connections UI loads both on every page open. Both routes
# are authenticated, so they count per user like the connections routes.
_SCOPE_INTEGRATIONS = "integrations"


class IntegrationCapabilityRead(BaseModel):
    """One governed provider action as the caller may use it."""

    id: str
    display_name: str
    policy_keys: list[str]
    risk: str
    maturity: str
    substrate: str
    identity: str
    auth_profile_id: str
    deployment_contexts: list[str]
    component_ref: str | None = None
    mcp_tool: str | None = None
    allowed: bool = Field(description="False when at least one of the action's policy keys is denied.")
    blocked_policy_key: str | None = Field(
        default=None,
        description="The first denied policy key, so an operator panel can explain the decision.",
    )


class IntegrationProviderRead(BaseModel):
    """One loaded integration provider and the caller's effective access to it."""

    provider_id: str
    display_name: str
    icon: str | None = None
    docs_url: str | None = None
    approved: bool = Field(description="False when the provider is outside the operator ceiling.")
    enabled: bool = Field(
        description=(
            "True when the caller can already use this provider: it is approved and at least one "
            "connection they own, an instance connection, or an explicit share exists for it."
        )
    )
    connection_count: int
    capabilities: list[IntegrationCapabilityRead]


class IntegrationListRead(BaseModel):
    providers: list[IntegrationProviderRead]


class EffectiveIntegrationPolicyRead(BaseModel):
    """The decision set a client must render, and where it came from."""

    approved_provider_ids: list[str] = Field(
        description="The loaded providers allowed for this caller; consult unrestricted to interpret an empty list."
    )
    blocked_action_keys: list[str] = Field(description="Operator-only deny-list; empty for non-superusers.")
    loaded_provider_ids: list[str] = Field(
        description="Loaded providers; restricted to allowed providers for non-superusers."
    )
    unrestricted: bool = Field(description="True when no ceiling is configured, i.e. every loaded provider is allowed.")
    managed_externally: bool = Field(description="True when a plugin owns the ceiling instead of the policy bundle.")
    policy_revision: int | None = None


@router.get("", response_model=IntegrationListRead)
@router.get("/", response_model=IntegrationListRead, include_in_schema=False)
async def list_integrations(
    request: Request,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
    service: ConnectionService,
    provider: Annotated[str | None, Query(pattern=PROVIDER_ID_PATTERN, max_length=120)] = None,
    *,
    include_blocked: bool = False,
) -> IntegrationListRead:
    """List loaded integration providers and the caller's effective access.

    Blocked providers and actions are omitted by default so a picker cannot
    advertise what execution would refuse. ``include_blocked`` returns them with
    their decision attached, which is what the operator panel renders, and is
    superuser-only for the same reason every other ``include_blocked`` surface
    is (``/api/v1/all``, starter projects, basic examples): the deny decision is
    operator information, not something a plain caller may enumerate.
    """
    check_rate_limit(
        request,
        scope=_SCOPE_INTEGRATIONS,
        limit_per_minute=get_metadata_read_limit(),
        key=get_user_limiter_key(current_user.id),
    )
    if include_blocked and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can include blocked integrations.",
        )

    manifests = {
        integration.provider_id: integration.capability_manifest
        for integration in loaded_integrations()
        if provider is None or integration.provider_id == provider
    }
    if not manifests:
        return IntegrationListRead(providers=[])

    policy = await aresolve_integration_policy(
        user_id=current_user.id,
        provider_ids=frozenset(manifests),
        purpose=IntegrationPolicyPurpose.DISCOVER,
        attributes=provider_policy_attributes,
    )
    counts = await service.count_for_user(session, user=current_user, provider_ids=frozenset(manifests))

    providers: list[IntegrationProviderRead] = []
    for provider_id in sorted(manifests):
        manifest = manifests[provider_id]
        approved = policy.allows_provider(provider_id)
        if not approved and not include_blocked:
            continue
        capabilities: list[IntegrationCapabilityRead] = []
        for capability in manifest.capabilities:
            blocked_key = policy.blocked_action_key(capability.policy_keys)
            if blocked_key is not None and not include_blocked:
                continue
            capabilities.append(
                IntegrationCapabilityRead(
                    id=capability.id,
                    display_name=capability.display_name,
                    policy_keys=list(capability.policy_keys),
                    risk=capability.risk,
                    maturity=capability.maturity,
                    substrate=capability.substrate,
                    identity=capability.identity,
                    auth_profile_id=capability.auth_profile_id,
                    deployment_contexts=list(capability.deployment_contexts),
                    component_ref=capability.component_ref,
                    mcp_tool=capability.mcp_tool,
                    allowed=blocked_key is None,
                    blocked_policy_key=blocked_key,
                )
            )
        if not capabilities and not include_blocked:
            # Every action of an approved provider is blocked: there is nothing
            # a picker could offer, so do not advertise the provider either.
            continue
        connection_count = counts.get(provider_id, 0)
        providers.append(
            IntegrationProviderRead(
                provider_id=provider_id,
                display_name=manifest.display_name,
                icon=manifest.icon,
                docs_url=manifest.docs_url,
                approved=approved,
                enabled=approved and connection_count > 0,
                connection_count=connection_count,
                capabilities=capabilities,
            )
        )
    return IntegrationListRead(providers=providers)


@router.get("/policy/effective", response_model=EffectiveIntegrationPolicyRead)
async def read_effective_integration_policy(
    request: Request,
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
) -> EffectiveIntegrationPolicyRead:
    """Return the integration decision set that applies to this caller."""
    check_rate_limit(
        request,
        scope=_SCOPE_INTEGRATIONS,
        limit_per_minute=get_metadata_read_limit(),
        key=get_user_limiter_key(current_user.id),
    )
    loaded_provider_ids = frozenset(integration.provider_id for integration in loaded_integrations())
    policy = await aresolve_integration_policy(
        user_id=current_user.id,
        provider_ids=loaded_provider_ids,
        purpose=IntegrationPolicyPurpose.DISCOVER,
        attributes=provider_policy_attributes,
    )
    service = get_integration_policy_service()
    external = service.external_approved_integration_provider_ids
    configured_ceiling = external if external is not None else getattr(service, "approved_provider_ids", frozenset())
    is_operator = current_user.is_superuser
    return EffectiveIntegrationPolicyRead(
        approved_provider_ids=sorted(policy.allowed_provider_ids),
        blocked_action_keys=sorted(policy.blocked_action_keys) if is_operator else [],
        loaded_provider_ids=sorted(loaded_provider_ids if is_operator else policy.allowed_provider_ids),
        unrestricted=external is None and not configured_ceiling and policy.allowed_provider_ids == loaded_provider_ids,
        managed_externally=external is not None,
        policy_revision=getattr(service, "policy_version", None),
    )


def loaded_integrations():
    """Return every integration the bundle registry has loaded in this process.

    Shared with the policy-bundle write path, which checks newly blocked action
    keys against the capabilities these integrations declare.
    """
    from lfx.extension.bundle_registry import get_default_registry

    return get_default_registry().list_integrations()


__all__ = [
    "EffectiveIntegrationPolicyRead",
    "IntegrationCapabilityRead",
    "IntegrationListRead",
    "IntegrationProviderRead",
    "loaded_integrations",
    "router",
]
