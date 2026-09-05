"""Typed integration capability metadata shared by manifests and resolvers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

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
ExecutionSubstrate = Literal["sdk", "rest", "mcp"]
CapabilityMaturity = Literal["ga", "preview", "developer_preview", "beta", "deprecated"]


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


class McpToolPin(BaseModel):
    """The frozen MCP contract for one ``substrate == "mcp"`` capability.

    Pinning is manifest data, not component code, so a provider bundle can move an
    action from its SDK/REST adapter to MCP without changing the component class,
    its identity, or the saved-flow schema (see
    ``design/dedicated-integrations/ga-swap-procedure.md``). ``tools_list_hash`` is
    the content digest of the whole pinned ``tools/list``
    (``lfx.base.mcp.pinned.tools_list_digest``); ``server_name`` and
    ``server_version`` are the ``InitializeResult.serverInfo`` values, pinned only
    when the server actually publishes them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    server_url: StrictStr = Field(min_length=1)
    transport: Literal["streamable_http"] = "streamable_http"
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    tools_list_hash: StrictStr | None = None
    server_name: StrictStr | None = None
    server_version: StrictStr | None = None


class IntegrationCapability(BaseModel):
    """One executable provider action and its credential requirements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: StrictStr = Field(min_length=1)
    auth_profile_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    identity: IntegrationIdentity
    required_scopes: tuple[StrictStr, ...] = ()
    conditional_scopes: tuple[ConditionalScopeRequirement, ...] = ()
    policy_keys: tuple[StrictStr, ...] = Field(min_length=1)
    substrate: ExecutionSubstrate
    maturity: CapabilityMaturity
    deployment_contexts: tuple[DeploymentContext, ...] = Field(min_length=1)
    risk: Literal["read", "write", "destructive"]
    component_ref: StrictStr | None = Field(default=None, min_length=1)
    mcp_tool: StrictStr | None = Field(default=None, min_length=1)
    mcp_pin: McpToolPin | None = None

    @field_validator("required_scopes", "policy_keys", "deployment_contexts")
    @classmethod
    def _values_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            msg = "Integration capability lists must not contain duplicate values"
            raise ValueError(msg)
        if any(not item.strip() for item in value):
            msg = "Integration capability values must not be blank"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _has_an_execution_target(self) -> IntegrationCapability:
        if self.component_ref is None and self.mcp_tool is None:
            msg = "An integration capability must declare component_ref or mcp_tool"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _mcp_capabilities_are_pinned(self) -> IntegrationCapability:
        """MCP actions run in pinned mode only: an unpinned MCP action fails validation.

        Runtime discovery may not decide what an MCP action can do, so the manifest
        must name the tool and freeze its endpoint and schemas before the loader
        will accept the capability.
        """
        if self.substrate == "mcp":
            if self.mcp_tool is None:
                msg = "An integration capability with substrate 'mcp' must declare mcp_tool"
                raise ValueError(msg)
            if self.mcp_pin is None:
                msg = (
                    "An integration capability with substrate 'mcp' must declare mcp_pin "
                    "(server endpoint plus argument and result schemas)"
                )
                raise ValueError(msg)
        elif self.mcp_pin is not None:
            msg = "mcp_pin is only valid on a capability whose substrate is 'mcp'"
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
        wrong_provider = sorted(
            capability.id for capability in self.capabilities if not capability.id.startswith(f"{self.provider_id}.")
        )
        if wrong_provider:
            msg = (
                f"Integration provider {self.provider_id!r} has capability ids outside its provider namespace: "
                f"{', '.join(wrong_provider)}"
            )
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


class IntegrationCapabilityManifest(IntegrationProvider):
    """Versioned provider capability catalog stored inside an extension bundle."""

    schema_version: Literal[1]

    @model_validator(mode="after")
    def _has_profiles_and_capabilities(self) -> IntegrationCapabilityManifest:
        if not self.auth_profiles:
            msg = "An integration capability manifest must declare at least one auth profile"
            raise ValueError(msg)
        if not self.capabilities:
            msg = "An integration capability manifest must declare at least one capability"
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
