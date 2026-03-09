"""Deployment API request and response schemas.

Identifier domains
------------------
Two identifier domains coexist in these schemas:

* **Langflow-managed (UUID)** -- ``id``, ``provider_id``, ``project_id``,
  ``deployment_id``. These reference rows in the Langflow database.
  ``provider_id`` maps to ``deployment_provider_account.id``.

* **Provider-owned (str)** -- ``reference_id``, ``config_id``,
  ``resource_key``, ``execution_id``, ``provider_tenant_id``,
  ``provider_key``, ``provider_url``, and ``api_key``. Opaque values
  assigned or consumed by the external deployment provider.

``provider_data`` dicts are opaque pass-through containers whose contents
are defined by the provider adapter. Langflow forwards them without
interpreting their schema.

Service-layer schema reuse (shared-kernel pattern)
---------------------------------------------------
Three service-layer data schemas are imported and subclassed (via
``_Strict*`` wrappers) rather than redefined in this module.  They act as
a **shared kernel**: field definitions owned by the service layer that the
API layer extends with stricter validation (``extra = "forbid"``).

* ``BaseDeploymentData`` -- deployment metadata for creation
* ``BaseDeploymentDataUpdate`` -- deployment metadata for partial updates
* ``DeploymentConfig`` -- deployment configuration payload

Additionally, ``DeploymentType`` is imported as a shared vocabulary enum.

This coupling is intentional -- these schemas carry no Langflow-managed
identifiers and describe provider-facing data whose shape the API should
track automatically.  If the service layer later introduces fields that
must *not* be API-visible, replace the ``_Strict*`` subclass with an
API-owned model and a mapping function.

``BaseDeploymentData`` also carries an optional ``provider_spec`` dict
(inherited from ``ProviderSpecModel``), an opaque provider-owned input
payload similar to ``provider_data``.  ``DeploymentConfig`` carries an
analogous ``provider_config`` dict.  ``BaseDeploymentDataUpdate`` has no
opaque provider fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from lfx.services.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    DeploymentConfig,
    DeploymentType,
)
from pydantic import AfterValidator, BaseModel, Field, SecretStr, ValidationInfo, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------


def _validate_str_id_list(values: list[str], *, field_name: str) -> list[str]:
    """Strip, reject empty values, reject empty lists, and reject duplicates in a list of string identifiers."""
    if not values:
        msg = f"{field_name} must not be empty."
        raise ValueError(msg)
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            msg = f"{field_name} must not contain empty values."
            raise ValueError(msg)
        if value in seen:
            msg = f"{field_name} must not contain duplicate values: '{value}'."
            raise ValueError(msg)
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _normalize_str(value: str, *, field_name: str = "Field") -> str:
    """Strip whitespace from a string, rejecting empty or whitespace-only values."""
    normalized = value.strip()
    if not normalized:
        msg = f"'{field_name}' must not be empty or whitespace."
        raise ValueError(msg)
    return normalized


def _normalize_optional_str(value: str | None, *, field_name: str = "Field") -> str | None:
    """Strip whitespace from an optional string, rejecting whitespace-only values."""
    if value is None:
        return None
    return _normalize_str(value, field_name=field_name)


def _strip_nonempty(value: str, info: ValidationInfo) -> str:
    """AfterValidator function: strip whitespace, reject empty/whitespace-only."""
    return _normalize_str(value, field_name=info.field_name or "Field")


NonEmptyStr = Annotated[str, AfterValidator(_strip_nonempty)]
"""String type that strips whitespace and rejects empty/whitespace-only values."""


def validate_flow_version_id_query(values: list[str]) -> list[str]:
    """Validate flow_version_ids received as query parameters."""
    return _validate_str_id_list(values, field_name="flow_version_ids")


# ---------------------------------------------------------------------------
# Provider sub-resource schemas
# ---------------------------------------------------------------------------


class DeploymentProviderAccountCreate(BaseModel):
    model_config = {"extra": "forbid"}

    provider_tenant_id: NonEmptyStr | None = Field(
        default=None,
        description="Provider-owned tenant/organization id. Langflow persists this opaque value.",
    )
    provider_key: NonEmptyStr = Field(description="Deployment provider key.")
    provider_url: NonEmptyStr = Field(
        description="Provider service URL persisted in Langflow DB for provider-account resolution.",
    )
    api_key: SecretStr = Field(
        min_length=1,
        description=(
            "Provider credential material. Stored by Langflow as secret data and never returned in read responses."
        ),
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: str, info: ValidationInfo) -> str:
        return _normalize_str(value, field_name=info.field_name)


class DeploymentProviderAccountUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    provider_tenant_id: NonEmptyStr | None = Field(
        default=None,
        description="Provider-owned tenant/organization id. Omit to keep existing value, null to clear.",
    )
    provider_key: NonEmptyStr | None = Field(
        default=None,
        description="Deployment provider key. Omit to keep existing value; cannot be set to null.",
    )
    provider_url: NonEmptyStr | None = Field(
        default=None,
        description="Provider service URL. Omit to keep existing value; cannot be set to null.",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description=(
            "Provider credential material. Omit to keep existing value; "
            "provided value replaces stored secret. Cannot be set to null."
        ),
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: str | None, info: ValidationInfo) -> str | None:
        return _normalize_optional_str(value, field_name=info.field_name)

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentProviderAccountUpdate:
        if not self.model_fields_set:
            msg = "At least one field must be provided for update."
            raise ValueError(msg)
        # provider_key, provider_url, and api_key are required-on-create;
        # reject explicit null to prevent clearing these fields.
        for field_name in ("provider_key", "provider_url", "api_key"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                msg = f"'{field_name}' cannot be set to null."
                raise ValueError(msg)
        return self


class DeploymentProviderAccountResponse(BaseModel):
    id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
    provider_tenant_id: str | None = Field(
        default=None,
        description="Provider-owned tenant/organization identifier persisted as opaque text.",
    )
    provider_key: str = Field(description="Provider adapter key used by Langflow.")
    provider_url: str = Field(description="Provider service URL persisted in Langflow DB.")
    created_at: datetime | None = Field(default=None, description="Langflow DB row creation timestamp.")
    updated_at: datetime | None = Field(default=None, description="Langflow DB row update timestamp.")


# ---------------------------------------------------------------------------
# Deployment resource schemas
# ---------------------------------------------------------------------------


class DeploymentTypeListResponse(BaseModel):
    """Supported deployment types for a provider account."""

    deployment_types: list[DeploymentType]


class _DeploymentResponseBase(BaseModel):
    """Shared fields for deployment response schemas."""

    id: UUID = Field(description="Langflow DB deployment UUID.")
    name: str
    description: str | None = None
    type: DeploymentType
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque payload returned by the deployment provider.",
    )


class DeploymentGetResponse(_DeploymentResponseBase):
    """Full deployment detail.

    Intentionally separate from ``DeploymentListItem`` even though both
    currently share the same fields.  The detail response is expected to
    grow (e.g. full config, attached flow versions, audit log) while the
    list item stays lean.
    """

    resource_key: str = Field(description="Provider-owned stable resource identifier.")
    attached_count: int = Field(default=0, ge=0, description="Number of flow versions attached to this deployment.")


class DeploymentListItem(_DeploymentResponseBase):
    """Deployment representation used in list responses.

    See ``DeploymentGetResponse`` docstring for rationale on the separate class.
    """

    resource_key: str = Field(description="Provider-owned stable resource identifier.")
    attached_count: int = Field(default=0, ge=0, description="Number of flow versions attached to this deployment.")


class _PaginatedResponse(BaseModel):
    """Shared pagination fields for list responses."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentListResponse(_PaginatedResponse):
    deployments: list[DeploymentListItem]
    deployment_type: DeploymentType | None = None


class DeploymentProviderAccountListResponse(_PaginatedResponse):
    providers: list[DeploymentProviderAccountResponse]


class DeploymentCreateResponse(_DeploymentResponseBase):
    """API response for deployment creation."""


class DeploymentUpdateResponse(_DeploymentResponseBase):
    """API response for deployment update."""


class DeploymentStatusResponse(_DeploymentResponseBase):
    """API response for deployment status/health."""


class RedeployResponse(_DeploymentResponseBase):
    """API response for redeployment."""


class DeploymentDuplicateResponse(_DeploymentResponseBase):
    """API response for deployment duplication."""


# ---------------------------------------------------------------------------
# Flow versions sub-resource schemas
# ---------------------------------------------------------------------------


class FlowVersionsAttach(BaseModel):
    """Flow version ids to attach to a deployment."""

    model_config = {"extra": "forbid"}

    # Typed as str (not UUID) because the service layer uses a flexible IdLike
    # type (UUID | NormalizedId). The same str typing is used for the
    # query-parameter variant in list_deployments for consistency.
    ids: list[str] = Field(
        min_length=1,
        description="Langflow flow version ids to attach to the deployment.",
    )

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, values: list[str]) -> list[str]:
        return _validate_str_id_list(values, field_name="ids")


class FlowVersionsPatch(BaseModel):
    """Add or remove flow version bindings on an existing deployment."""

    model_config = {"extra": "forbid"}

    add: list[str] | None = Field(
        None,
        description="Langflow flow version ids to attach to the deployment. Omit to leave unchanged.",
    )
    remove: list[str] | None = Field(
        None,
        description="Langflow flow version ids to detach from the deployment. Omit to leave unchanged.",
    )

    @field_validator("add", "remove")
    @classmethod
    def validate_id_lists(cls, values: list[str] | None, info: ValidationInfo) -> list[str] | None:
        if values is None:
            return None
        return _validate_str_id_list(values, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_operations(self):
        add_values = self.add or []
        remove_values = self.remove or []

        if not add_values and not remove_values:
            msg = "At least one of 'add' or 'remove' must be provided."
            raise ValueError(msg)

        overlap = set(add_values).intersection(remove_values)
        if overlap:
            ids = ", ".join(sorted(overlap))
            msg = f"Flow version ids cannot be present in both 'add' and 'remove': {ids}."
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Strict API-layer wrappers (shared-kernel boundary)
# ---------------------------------------------------------------------------
# These thin subclasses inherit field definitions from the service layer and
# add ``extra = "forbid"`` so API callers receive a 422 for unexpected fields
# instead of having data silently dropped.  Subclassing (rather than
# redefining fields) keeps the API in lock-step with the service contract.
# If a service-layer field should NOT be API-visible, replace the relevant
# subclass with an API-owned model and a mapping function.


class _StrictBaseDeploymentData(BaseDeploymentData):
    model_config = {"extra": "forbid"}


class _StrictBaseDeploymentDataUpdate(BaseDeploymentDataUpdate):
    model_config = {"extra": "forbid"}


class _StrictDeploymentConfig(DeploymentConfig):
    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Deployment config sub-resource schemas (API-owned)
# ---------------------------------------------------------------------------


class DeploymentConfigCreate(BaseModel):
    """Config input for deployment creation.

    Exactly one of ``reference_id`` or ``raw_payload`` must be provided.
    """

    model_config = {"extra": "forbid"}

    reference_id: NonEmptyStr | None = Field(
        default=None,
        description="Provider-owned config reference id to bind to the deployment.",
    )
    raw_payload: _StrictDeploymentConfig | None = Field(
        default=None,
        description="Config payload to create and bind to the deployment.",
    )

    @model_validator(mode="after")
    def validate_exactly_one(self) -> DeploymentConfigCreate:
        if (self.reference_id is None) == (self.raw_payload is None):
            msg = "Exactly one of 'reference_id' or 'raw_payload' must be provided."
            raise ValueError(msg)
        return self


class DeploymentConfigBindingUpdate(BaseModel):
    """Config binding patch for an existing deployment."""

    model_config = {"extra": "forbid"}

    config_id: NonEmptyStr | None = Field(
        default=None,
        description="Provider-owned config id to bind to the deployment. Use null to unbind.",
    )


# ---------------------------------------------------------------------------
# Deployment create / update request schemas
# ---------------------------------------------------------------------------


class DeploymentCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
    spec: _StrictBaseDeploymentData = Field(description="Deployment metadata (service-layer schema, no ID fields).")
    project_id: UUID | None = Field(
        default=None,
        description="Langflow DB project id to persist the deployment under. Defaults to user's Starter Project.",
    )
    flow_version_ids: FlowVersionsAttach | None = Field(
        default=None,
        description="Flow version ids to attach to the deployment.",
    )
    config: DeploymentConfigCreate | None = Field(default=None, description="Deployment configuration.")


class DeploymentUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    spec: _StrictBaseDeploymentDataUpdate | None = Field(
        default=None, description="Deployment metadata updates (service-layer schema, no ID fields)."
    )
    flow_version_ids: FlowVersionsPatch | None = Field(
        default=None,
        description="Flow version attach/detach operations.",
    )
    config: DeploymentConfigBindingUpdate | None = Field(default=None, description="Deployment configuration update.")

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentUpdateRequest:
        if not self.model_fields_set:
            msg = "At least one of 'spec', 'flow_version_ids', or 'config' must be provided."
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Execution sub-resource schemas
# ---------------------------------------------------------------------------


class ExecutionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_id: UUID = Field(
        description=(
            "Langflow DB provider-account UUID (`deployment_provider_account.id`). "
            "Included alongside deployment_id to allow provider routing without an extra DB lookup."
        ),
    )
    deployment_id: UUID = Field(description="Langflow DB deployment UUID.")
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque execution input payload.",
    )


class _ExecutionResponseBase(BaseModel):
    """Shared fields for execution responses."""

    execution_id: str | None = Field(
        default=None,
        description=(
            "Provider-owned opaque execution identifier. "
            "May be None when the provider acknowledges the request but has not yet assigned an id."
        ),
    )
    deployment_id: UUID = Field(description="Langflow DB deployment UUID.")
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque execution result payload.",
    )


class ExecutionCreateResponse(_ExecutionResponseBase):
    """Response returned when an execution is created.

    Intentionally distinct from ``ExecutionStatusResponse`` even though both
    currently share the same shape, mirroring the service-layer separation.
    """


class ExecutionStatusResponse(_ExecutionResponseBase):
    """Response returned when querying an execution status.

    Intentionally distinct from ``ExecutionCreateResponse`` even though both
    currently share the same shape, mirroring the service-layer separation.
    """
