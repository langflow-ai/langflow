"""Deployment API request and response schemas.

Identifier domains
------------------
Two identifier domains coexist in these schemas:

* **Langflow-managed (UUID)** -- ``id``, ``provider_id``, ``project_id``,
  ``deployment_id``. These reference rows in the Langflow database.
  ``provider_id`` maps to ``deployment_provider_account.id``.

* **Provider-owned (str)** -- ``reference_id``, ``config_id``,
  ``execution_id``.
  Opaque values assigned or consumed by the external deployment provider.
  ``provider_key`` is Langflow-owned adapter vocabulary.
  Provider-specific metadata (for example URL and tenant/account identifiers)
  belongs inside ``provider_data``.

* **Provider-originated but Langflow-owned once persisted** -- ``resource_key``.
  Langflow stores and indexes this as part of its own deployment record.

``provider_data`` dicts are opaque pass-through containers whose contents
are defined by the provider adapter. Langflow forwards them without
interpreting their schema.

DeploymentType is imported from the adapter service layer as shared
vocabulary. Request/response models in this module are API-owned to keep
the client-facing schema minimal and avoid exposing service-only fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from lfx.services.adapters.deployment.schema import DEPLOYMENT_DESCRIPTION_MAX_LENGTH, DeploymentType
from pydantic import AfterValidator, BaseModel, Field, ValidationInfo, model_validator

from langflow.services.database.models.deployment_provider_account.schemas import (
    DeploymentProviderKey,
)
from langflow.services.database.models.deployment_provider_account.utils import (
    validate_provider_url,
)

# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------


def _validate_uuid_list(values: list[UUID], *, field_name: str) -> list[UUID]:
    """Deduplicate (preserving order) and reject empty lists."""
    deduped = list(dict.fromkeys(values))
    if not deduped:
        msg = f"{field_name} must not be empty."
        raise ValueError(msg)
    return deduped


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


ValidatedUrl = Annotated[str, AfterValidator(validate_provider_url)]
"""URL type that enforces HTTPS and normalizes."""


def _validate_flow_version_ids(values: list[UUID] | None) -> list[UUID] | None:
    """AfterValidator for optional flow_version_ids query parameter."""
    if values is None:
        return None
    return _validate_uuid_list(values, field_name="flow_version_ids")


FlowVersionIdsQuery = Annotated[list[UUID] | None, AfterValidator(_validate_flow_version_ids)]
"""Optional flow-version filter query parameter.

``None`` means no filter. Empty lists are rejected by validation.
"""


def _validate_flow_ids(values: list[UUID] | None) -> list[UUID] | None:
    """AfterValidator for optional flow_ids query parameter.

    Deduplicates and enforces max length of 1 today; remove the length
    guard when multi-flow filtering is needed.
    """
    if values is None:
        return None
    validated = _validate_uuid_list(values, field_name="flow_ids")
    if len(validated) > 1:
        msg = "flow_ids currently supports at most 1 value."
        raise ValueError(msg)
    return validated


FlowIdsQuery = Annotated[list[UUID] | None, AfterValidator(_validate_flow_ids)]
"""Optional flow-id filter query parameter.

``None`` means no filter. Empty lists are rejected by validation.
Max supported length is 1 today.
"""


def _validate_detect_vars_request_ids(values: list[UUID]) -> list[UUID]:
    """AfterValidator for DetectVarsRequest.flow_version_ids."""
    return _validate_uuid_list(values, field_name="flow_version_ids")


# ---------------------------------------------------------------------------
# Provider sub-resource schemas
# ---------------------------------------------------------------------------


class DeploymentProviderAccountCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: NonEmptyStr = Field(
        description=(
            "User-chosen display name for this provider account. Must be unique per user within a provider_key."
        ),
    )
    provider_key: DeploymentProviderKey = Field(description="Deployment provider key.")
    provider_data: dict[str, Any] = Field(
        min_length=1,
        description=(
            "Provider-specific credential/metadata payload. "
            "Contents are opaque to the API schema; the deployment mapper "
            "for the target provider_key validates and extracts credentials "
            "and provider metadata (for example URL/region and tenant/account identifiers)."
        ),
    )


class DeploymentProviderAccountUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: NonEmptyStr | None = Field(
        default=None,
        description="User-chosen display name. Omit to keep existing value; cannot be set to null.",
    )
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Provider-specific credential payload. "
            "Omit to keep existing credentials; provided value replaces stored credentials. "
            "Cannot be set to null."
        ),
    )

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentProviderAccountUpdateRequest:
        if not self.model_fields_set:
            msg = "At least one field must be provided for update."
            raise ValueError(msg)
        for field_name in ("name", "provider_data"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                msg = f"'{field_name}' cannot be set to null."
                raise ValueError(msg)
        return self


class DeploymentProviderAccountGetResponse(BaseModel):
    id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
    name: str = Field(description="User-chosen display name for this provider account.")
    provider_key: DeploymentProviderKey = Field(description="Official provider name used by Langflow.")
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Provider-owned non-sensitive metadata for this provider account "
            "(for example URL, tenant/account identifiers). Credentials are excluded."
        ),
    )
    created_at: datetime | None = Field(default=None, description="Langflow DB row creation timestamp.")
    updated_at: datetime | None = Field(default=None, description="Langflow DB row update timestamp.")


# ---------------------------------------------------------------------------
# Deployment resource schemas
# ---------------------------------------------------------------------------


class DeploymentTypeListResponse(BaseModel):
    """Supported deployment types for a provider account."""

    deployment_types: list[DeploymentType]


class DeploymentLlmListResponse(BaseModel):
    """Provider model catalog payload for deployment LLM listing."""

    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque model catalog payload returned by the deployment provider.",
    )


class _DeploymentResponseCommon(BaseModel):
    """Shared non-provider-data fields for deployment response schemas."""

    id: UUID = Field(description="Langflow DB deployment UUID.")
    provider_id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
    provider_key: str = Field(description="Provider identifier (e.g. 'watsonx-orchestrate').")
    name: str
    description: str | None = None
    type: DeploymentType
    created_at: datetime | None = None
    updated_at: datetime | None = None


class _DeploymentResponseWithProviderData(_DeploymentResponseCommon):
    """Shared fields for responses that include provider_data."""

    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque payload returned by the deployment provider.",
    )


class DeploymentGetResponse(_DeploymentResponseWithProviderData):
    """Full deployment detail.

    Intentionally separate from ``DeploymentListItem`` even though both
    currently share the same fields.  The detail response is expected to
    grow (e.g. full config, attached flow versions, audit log) while the
    list item stays lean.
    """

    resource_key: str = Field(description="Langflow-persisted stable provider resource identifier.")
    attached_count: int = Field(default=0, ge=0, description="Number of flow versions attached to this deployment.")


class DeploymentListItem(_DeploymentResponseCommon):
    """Deployment representation used in list responses.

    See ``DeploymentGetResponse`` docstring for rationale on the separate class.
    """

    resource_key: str = Field(description="Langflow-persisted stable provider resource identifier.")
    attached_count: int = Field(default=0, ge=0, description="Number of flow versions attached to this deployment.")
    flow_version_ids: list[UUID] | None = Field(
        default=None,
        description=(
            "Flow-version ids that matched the active flow_ids or "
            "flow_version_ids filter. Omitted when no such filter is active."
        ),
    )


class _PaginatedResponse(BaseModel):
    """Shared pagination fields for list responses."""

    page: int | None = Field(default=None, ge=1)
    size: int | None = Field(default=None, ge=1)
    total: int | None = Field(default=None, ge=0)


class DeploymentListResponse(_PaginatedResponse):
    deployments: list[DeploymentListItem] | None = None
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque payload for list-specific provider metadata.",
    )


class DeploymentProviderAccountListResponse(_PaginatedResponse):
    provider_accounts: list[DeploymentProviderAccountGetResponse]


class DeploymentConfigListResponse(_PaginatedResponse):
    """Paginated config list with all provider-owned data in a single opaque blob."""

    provider_data: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Provider-owned opaque payload containing the list of connections "
            "and any response-level metadata supplied by the provider."
        ),
    )


class DeploymentSnapshotListResponse(_PaginatedResponse):
    """Paginated snapshot list with all provider-owned data in a single opaque blob."""

    provider_data: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Provider-owned opaque payload containing the list of snapshots "
            "and any response-level metadata supplied by the provider."
        ),
    )


class DeploymentFlowVersionListItem(BaseModel):
    """Flow version metadata attached to a deployment.

    **Identity model:** Langflow tracks provider tools by their immutable
    ``provider_snapshot_id`` (the wxO tool_id), never by name.  This
    distinguishes the following cases:

    * **Tool renamed in provider** — Same ``provider_snapshot_id``, different
      ``provider_data.tool_name``.  Langflow picks up the new name on the next fetch.
    * **Tool deleted in provider** — ``provider_snapshot_id`` no longer
      resolves.  ``provider_data.tool_name`` may be missing/``None``.
    * **Tool deleted + new tool created with same name** — The new tool has
      a different ID.  Langflow's attachment still points to the old
      (missing) ID.  The new tool is invisible to Langflow until explicitly
      attached via an update operation.

    Frontends should use ``provider_data.tool_name`` for display and
    ``provider_snapshot_id`` for identity / operations.
    """

    id: UUID = Field(description="Langflow flow version UUID (`flow_version.id`).")
    flow_id: UUID = Field(description="Langflow flow UUID (`flow.id`) for this version.")
    flow_name: str | None = Field(
        default=None,
        description="Name of the flow owning this version (`flow.name`).",
    )
    version_number: int = Field(ge=1, description="Flow version number.")
    attached_at: datetime | None = Field(
        default=None,
        description="Timestamp when this flow version was attached to the deployment.",
    )
    provider_snapshot_id: str | None = Field(
        default=None,
        description="Provider-owned snapshot/tool identifier linked by the attachment.",
    )
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque payload for this attached flow version.",
    )


class DeploymentFlowVersionListResponse(_PaginatedResponse):
    flow_versions: list[DeploymentFlowVersionListItem]


class DeploymentCreateResponse(_DeploymentResponseWithProviderData):
    """API response for deployment creation."""

    resource_key: str = Field(description="Langflow-persisted stable provider resource identifier.")


class DeploymentUpdateResponse(_DeploymentResponseWithProviderData):
    """API response for deployment update."""

    resource_key: str = Field(description="Langflow-persisted stable provider resource identifier.")


class DeploymentStatusResponse(_DeploymentResponseWithProviderData):
    """API response for deployment status/health."""


# ---------------------------------------------------------------------------
# Deployment create / update request schemas
# ---------------------------------------------------------------------------


class DeploymentCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
    name: NonEmptyStr = Field(description="Deployment display name.")
    description: str = Field(
        default="",
        max_length=DEPLOYMENT_DESCRIPTION_MAX_LENGTH,
        description="Deployment description.",
    )
    type: DeploymentType = Field(description="Deployment type.")
    project_id: UUID | None = Field(
        default=None,
        description="Langflow DB project id to persist the deployment under. Defaults to user's Starter Project.",
    )
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque create payload.",
    )


class DeploymentUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: NonEmptyStr | None = Field(default=None, description="Updated deployment display name.")
    description: str | None = Field(
        default=None,
        max_length=DEPLOYMENT_DESCRIPTION_MAX_LENGTH,
        description="Updated deployment description.",
    )
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque update payload.",
    )

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentUpdateRequest:
        if not self.model_fields_set:
            msg = "At least one of 'name', 'description', or 'provider_data' must be provided."
            raise ValueError(msg)
        if self.name is None and self.description is None and self.provider_data is None:
            msg = "At least one of 'name', 'description', or 'provider_data' must be provided."
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Execution sub-resource schemas
# ---------------------------------------------------------------------------


class ExecutionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque execution input payload.",
    )


class _ExecutionResponseBase(BaseModel):
    """Shared fields for execution responses.

    Only Langflow-owned identifiers live at the top level.  All
    provider-owned data (including the provider's ``execution_id``)
    is returned inside ``provider_data`` so that ownership boundaries
    stay clear and a future Langflow-managed execution id won't
    collide with provider terminology.
    """

    deployment_id: UUID = Field(description="Langflow DB deployment UUID.")
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Provider-owned opaque execution result payload.  "
            "Contains at least ``execution_id`` (the provider's opaque run identifier) "
            "when the provider has assigned one."
        ),
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


# ---------------------------------------------------------------------------
# Snapshot sub-resource schemas
# ---------------------------------------------------------------------------


class SnapshotUpdateRequest(BaseModel):
    """Request body for PATCH /deployments/snapshots/{provider_snapshot_id}.

    Updates the content of an existing provider snapshot with a new
    flow version's artifact.  The ``provider_snapshot_id`` is supplied
    as a path parameter; only ``flow_version_id`` is in the body.
    """

    model_config = {"extra": "forbid"}

    flow_version_id: UUID = Field(
        description="Langflow flow version whose artifact will replace the snapshot content.",
    )


class SnapshotUpdateResponse(BaseModel):
    """Response for PATCH /deployments/snapshots/{provider_snapshot_id}."""

    flow_version_id: UUID
    provider_snapshot_id: str


class DetectVarsRequest(BaseModel):
    """Request body for detecting environment variables from flow version IDs."""

    flow_version_ids: Annotated[
        list[UUID],
        AfterValidator(_validate_detect_vars_request_ids),
    ] = Field(
        min_length=1,
        max_length=50,
        description="Flow version UUIDs to scan for global variable references.",
    )


class DetectVarsResponse(BaseModel):
    """Response containing detected global variable names."""

    variables: list[str] = Field(default_factory=list, description="Detected global variable names.")
