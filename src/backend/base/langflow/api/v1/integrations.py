"""Effective integration policy and the governed provider catalog (INT-7).

The UI never decides what is available: it renders what this API returns. B9
(the operator integration-policy panel) and INT-8 (the connection picker) both
read the effective policy here rather than reimplementing the ceiling and the
deny-list, so a client that ignores it still fails closed at execution.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from lfx.integrations.models import PROVIDER_ID_PATTERN
from lfx.services.deps import get_integration_policy_service
from lfx.services.integration_policy import IntegrationPolicyPurpose, aresolve_integration_policy
from pydantic import BaseModel, Field
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSessionReadOnly
from langflow.api.v1.model_provider_policy_scope import ProviderPolicyAttributesDependency
from langflow.services.database.models.connection import Connection, ConnectionOwnershipMode

router = APIRouter(prefix="/integrations", tags=["Integrations"])


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
        description="The effective ceiling for this caller. Empty means unrestricted."
    )
    blocked_action_keys: list[str]
    loaded_provider_ids: list[str] = Field(description="Providers with a capability manifest loaded in this process.")
    unrestricted: bool = Field(description="True when no ceiling is configured, i.e. every loaded provider is allowed.")
    managed_externally: bool = Field(description="True when a plugin owns the ceiling instead of the policy bundle.")
    policy_revision: int | None = None


async def _connection_counts(
    session: DbSessionReadOnly,
    *,
    user: CurrentActiveUser,
    provider_ids: frozenset[str],
) -> dict[str, int]:
    """Count the connections the caller can see, per provider.

    Enablement is connection existence, mirroring model-provider enablement by
    stored credential variables: INT-7 adds no per-user state of its own.
    Explicit shares are intentionally not counted here -- this is a hint for the
    picker, and the resolver remains the authority on which row is usable.
    """
    if not provider_ids:
        return {}
    statement = select(Connection.provider_key).where(
        col(Connection.provider_key).in_(provider_ids),
    )
    if not bool(getattr(user, "is_superuser", False)):
        statement = statement.where(
            (Connection.owner_id == user.id) | (Connection.ownership_mode == ConnectionOwnershipMode.INSTANCE.value)
        )
    counts: dict[str, int] = {}
    for provider_key in (await session.exec(statement)).all():
        counts[provider_key] = counts.get(provider_key, 0) + 1
    return counts


@router.get("", response_model=IntegrationListRead)
@router.get("/", response_model=IntegrationListRead, include_in_schema=False)
async def list_integrations(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
    provider: Annotated[str | None, Query(pattern=PROVIDER_ID_PATTERN, max_length=120)] = None,
    *,
    include_blocked: bool = False,
) -> IntegrationListRead:
    """List loaded integration providers and the caller's effective access.

    Blocked providers and actions are omitted by default so a picker cannot
    advertise what execution would refuse. ``include_blocked`` returns them with
    their decision attached, which is what the operator panel renders.
    """
    manifests = {
        integration.provider_id: integration.capability_manifest
        for integration in _loaded_integrations()
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
    counts = await _connection_counts(session, user=current_user, provider_ids=frozenset(manifests))

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
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
) -> EffectiveIntegrationPolicyRead:
    """Return the integration decision set that applies to this caller."""
    loaded_provider_ids = frozenset(integration.provider_id for integration in _loaded_integrations())
    policy = await aresolve_integration_policy(
        user_id=current_user.id,
        provider_ids=loaded_provider_ids,
        purpose=IntegrationPolicyPurpose.DISCOVER,
        attributes=provider_policy_attributes,
    )
    service = get_integration_policy_service()
    external = service.external_approved_integration_provider_ids
    configured_ceiling = external if external is not None else getattr(service, "approved_provider_ids", frozenset())
    return EffectiveIntegrationPolicyRead(
        approved_provider_ids=sorted(policy.allowed_provider_ids),
        blocked_action_keys=sorted(policy.blocked_action_keys),
        loaded_provider_ids=sorted(loaded_provider_ids),
        unrestricted=not configured_ceiling,
        managed_externally=external is not None,
        policy_revision=getattr(service, "policy_version", None),
    )


def _loaded_integrations():
    """Return every integration the bundle registry has loaded in this process."""
    from lfx.extension.bundle_registry import get_default_registry

    return get_default_registry().list_integrations()


__all__ = [
    "EffectiveIntegrationPolicyRead",
    "IntegrationCapabilityRead",
    "IntegrationListRead",
    "IntegrationProviderRead",
    "router",
]
