"""Typed integration capability metadata shared by manifests and resolvers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from lfx.integrations.models import PROVIDER_ID_PATTERN

OAuthKind = Literal[
    "oauth2_authorization_code",
    "oauth2_client_credentials",
    "oauth2_device_code",
    "service_account",
    "service_account_domain_wide_delegation",
    "bot_token_install",
    "api_key",
]
IntegrationIdentity = Literal["user_delegated", "bot", "service"]
DeploymentContext = Literal["hosted", "self_managed", "desktop", "headless"]


class ScopeCondition(BaseModel):
    """Input predicate controlling whether a conditional scope is active."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["input_present", "input_truthy"]
    input: StrictStr = Field(pattern=r"^[a-z][a-z0-9_]*$")

    def is_active(self, inputs: dict[str, Any]) -> bool:
        if self.kind == "input_present":
            return self.input in inputs and inputs[self.input] is not None
        return bool(inputs.get(self.input))


class ConditionalScopeRequirement(BaseModel):
    """Scope activated only when its declared input predicate matches."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: StrictStr = Field(min_length=1)
    role: Literal["optional", "alternative"]
    condition: ScopeCondition


class OAuthProfile(BaseModel):
    """One named provider authentication profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    kind: OAuthKind
    identity: IntegrationIdentity
    authorization_url: StrictStr | None = None
    token_url: StrictStr | None = None
    supports_pkce: bool = False
    supports_refresh: bool = False
    scope_separator: StrictStr = " "
    default_scopes: tuple[StrictStr, ...] = ()
    client_type_by_context: dict[DeploymentContext, Literal["confidential", "public", "external"]] = Field(
        default_factory=dict
    )
    owner_by_context: dict[DeploymentContext, Literal["langflow", "customer", "either"]] = Field(default_factory=dict)
    tenant_param: StrictStr | None = None


class IntegrationCapability(BaseModel):
    """One executable provider action and its credential requirements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: StrictStr = Field(min_length=1)
    auth_profile_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    identity: IntegrationIdentity
    required_scopes: tuple[StrictStr, ...] = ()
    conditional_scopes: tuple[ConditionalScopeRequirement, ...] = ()
    risk: Literal["read", "write", "destructive"]
    component_ref: StrictStr | None = None
    mcp_tool: StrictStr | None = None

    @model_validator(mode="after")
    def _has_an_execution_target(self) -> IntegrationCapability:
        if self.component_ref is None and self.mcp_tool is None:
            msg = "An integration capability must declare component_ref or mcp_tool"
            raise ValueError(msg)
        return self


class IntegrationProvider(BaseModel):
    """Provider metadata and the capability/profile catalog it exposes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: StrictStr = Field(pattern=PROVIDER_ID_PATTERN)
    display_name: StrictStr = Field(min_length=1)
    icon: StrictStr | None = None
    auth_profiles: tuple[OAuthProfile, ...]
    capabilities: tuple[IntegrationCapability, ...]
    docs_url: StrictStr | None = None

    @model_validator(mode="after")
    def _references_known_profiles(self) -> IntegrationProvider:
        profile_ids = [profile.id for profile in self.auth_profiles]
        if len(set(profile_ids)) != len(profile_ids):
            msg = f"Integration provider {self.provider_id!r} has duplicate auth profile ids"
            raise ValueError(msg)
        capability_ids = [capability.id for capability in self.capabilities]
        if len(set(capability_ids)) != len(capability_ids):
            msg = f"Integration provider {self.provider_id!r} has duplicate capability ids"
            raise ValueError(msg)
        unknown = sorted({cap.auth_profile_id for cap in self.capabilities} - set(profile_ids))
        if unknown:
            msg = f"Integration provider {self.provider_id!r} references unknown auth profiles: {', '.join(unknown)}"
            raise ValueError(msg)
        identities = {profile.id: profile.identity for profile in self.auth_profiles}
        mismatched = sorted(
            capability.id
            for capability in self.capabilities
            if identities[capability.auth_profile_id] != capability.identity
        )
        if mismatched:
            msg = (
                f"Integration provider {self.provider_id!r} has capabilities whose identity does not match "
                f"their auth profile: {', '.join(mismatched)}"
            )
            raise ValueError(msg)
        return self


class ScopeSet:
    """Provider-aware scope coverage shared by pickers and resolvers."""

    @staticmethod
    def _normalize(provider: str, scope: str) -> str:
        normalized = scope.strip()
        if provider == "google":
            normalized = normalized.removeprefix("https://www.googleapis.com/auth/")
        elif provider == "microsoft":
            normalized = normalized.removeprefix("https://graph.microsoft.com/")
        return normalized.casefold()

    @classmethod
    def covers(
        cls,
        capability: IntegrationCapability,
        inputs: dict[str, Any],
        granted: set[str] | frozenset[str],
        *,
        provider: str | None = None,
    ) -> frozenset[str]:
        """Return required active scopes not covered by ``granted``."""
        provider_id = provider or capability.id.partition(".")[0]
        required = set(capability.required_scopes)
        required.update(
            requirement.scope
            for requirement in capability.conditional_scopes
            if requirement.condition.is_active(inputs)
        )
        normalized_granted = {cls._normalize(provider_id, scope) for scope in granted}
        return frozenset(scope for scope in required if cls._normalize(provider_id, scope) not in normalized_granted)
