from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi_pagination import Params
from lfx.services.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)

# TODO: Import these schemas as Adapter[Original Schema Name]
# this will improve readability and the separation
# between API schemas and deployment service schemas
from lfx.services.deployment.schema import (
    ArtifactType,
    BaseConfigData,
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    BaseFlowArtifact,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    ConfigItemResult,
    ConfigListResult,
    ConfigResult,
    ConfigUpdate,
    DeploymentCreateResult,
    DeploymentDetailItem,
    DeploymentExecution,
    DeploymentExecutionResult,
    DeploymentExecutionStatus,
    DeploymentItem,
    DeploymentListParams,
    DeploymentProviderId,
    DeploymentRedeploymentResult,
    DeploymentStatusResult,
    DeploymentType,
    DeploymentUpdateResult,
    SnapshotDeploymentBindingUpdate,
    SnapshotGetResult,
    SnapshotItems,
    SnapshotItemsCreate,
    SnapshotListResult,
    SnapshotResult,
)
from lfx.services.deployment.schema import (
    DeploymentCreate as AdapterDeploymentCreate,
)
from lfx.services.deployment.schema import (
    DeploymentCreateResult as AdapterDeploymentCreateResult,
)
from lfx.services.deployment.schema import (
    DeploymentUpdate as AdapterDeploymentUpdate,
)
from lfx.services.deployment_router.exceptions import (
    DeploymentAccountNotFoundError,
    DeploymentRouterError,
)
from lfx.services.deps import get_deployment_router_service
from lfx.services.interfaces import DeploymentRouterServiceProtocol, DeploymentServiceProtocol
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import and_, literal, union_all
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.deployment.crud import (
    count_deployment_rows,
    create_deployment_row,
    delete_deployment_row_by_id,
    delete_deployment_row_by_resource_key,
    get_deployment_row,
    get_deployment_row_by_resource_key,
    list_deployment_rows_page,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.crud import (
    create_provider_account as create_provider_account_row,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    delete_provider_account as delete_provider_account_row,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    get_provider_account_by_id as get_provider_account_row_by_id,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    list_provider_accounts as list_provider_account_rows,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    update_provider_account as update_provider_account_row,
)
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_history.crud import get_flow_history_entry_or_raise
from langflow.services.database.models.flow_history.exceptions import FlowHistoryNotFoundError
from langflow.services.database.models.flow_history.model import FlowHistory
from langflow.services.database.models.flow_history_deployment_attachment.crud import (
    create_deployment_attachment,
    delete_deployment_attachment,
    get_deployment_attachment,
    list_deployment_attachments_for_history_ids,
    update_deployment_attachment_snapshot_id,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_variable_service

router = APIRouter(prefix="/deployments", tags=["Deployments"])


ProviderIdQuery = Annotated[
    DeploymentProviderId,
    Query(description="The registered deployment provider account id used for adapter routing."),
]

# API provider-context contract matrix:
# - Query provider_id: list/provider-capability/runtime-status GET endpoints.
# - Body provider_id: POST create operations that cannot derive provider context.
# - Derived provider_id: deployment-scoped endpoints using persisted deployment relationships.


class DeploymentTypesResponse(BaseModel):
    """List deployment types response."""

    deployment_types: list[DeploymentType]


class DeploymentDuplicateRequest(BaseModel):
    """Create deployment duplicate request."""

    deployment_type: DeploymentType


class DeploymentProviderAccountCreateRequest(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, description="Provider tenant/organization identifier.")
    provider_key: str = Field(
        min_length=1,
        description="Deployment adapter routing key.",
    )
    backend_url: str = Field(min_length=1, description="Deployment provider backend URL.")
    api_key: str = Field(min_length=1, description="Deployment provider API key.")

    @field_validator("provider_key", "backend_url", "api_key")
    @classmethod
    def normalize_required_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "Field must not be empty or whitespace."
            raise ValueError(msg)
        return normalized

    @field_validator("account_id")
    @classmethod
    def normalize_optional_account_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "Field must not be empty or whitespace."
            raise ValueError(msg)
        return normalized


class DeploymentProviderUpdateRequest(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, description="Provider tenant/organization identifier.")
    provider_key: str | None = Field(default=None, min_length=1, description="Deployment adapter routing key.")
    backend_url: str | None = Field(default=None, min_length=1, description="Deployment provider backend URL.")
    api_key: str | None = Field(default=None, min_length=1, description="Deployment provider API key.")

    @field_validator("account_id", "provider_key", "backend_url", "api_key")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "Field must not be empty or whitespace."
            raise ValueError(msg)
        return normalized

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentProviderUpdateRequest:
        if all(value is None for value in (self.account_id, self.provider_key, self.backend_url, self.api_key)):
            msg = "At least one field must be provided for update."
            raise ValueError(msg)
        return self


class DeploymentProviderAccountResponse(BaseModel):
    id: UUID
    account_id: str | None
    provider_key: str
    backend_url: str
    registered_at: datetime | None


class DeploymentProviderAccountListResponse(BaseModel):
    deployment_providers: list[DeploymentProviderAccountResponse]
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentListResponse(BaseModel):
    deployments: list["DeploymentListItemResponse"]
    deployment_type: DeploymentType | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentListItemResponse(BaseModel):
    id: str
    resource_key: str
    type: DeploymentType
    name: str
    attached_count: int = Field(default=0, ge=0)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict | None = None


def _deployment_pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Params:
    return Params(page=page, size=size)


class DetectDeploymentEnvVarsRequest(BaseModel):
    reference_ids: list[str] = Field(
        min_length=1,
        description="Flow-history checkpoint ids to inspect for load_from_db global-variable bindings.",
    )

    @field_validator("reference_ids")
    @classmethod
    def validate_reference_ids(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip()
            if not value:
                msg = "reference_ids must not contain empty values."
                raise ValueError(msg)
            if value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        return cleaned


class DetectDeploymentEnvVarsResponse(BaseModel):
    variables: list["DetectedDeploymentEnvVar"] = Field(
        default_factory=list,
        description="Detected load_from_db global-variable bindings from selected checkpoints.",
    )


class DetectedDeploymentEnvVar(BaseModel):
    key: str = Field(description="Environment variable key in component template (e.g. api_key).")
    global_variable_name: str | None = Field(
        default=None,
        description="Global variable reference name when checkpoint uses load_from_db binding.",
    )


class DeploymentHistoryItemsRequest(BaseModel):
    model_config = {"extra": "forbid"}

    artifact_type: ArtifactType = Field(description="The type of history artifact being referenced.")
    reference_ids: list[str] | None = Field(
        None,
        description="History checkpoint reference ids to use for this deployment.",
    )
    raw_payloads: list[BaseFlowArtifact] | None = Field(
        None,
        description="Raw flow payloads for deployment creation from client-side history/export data.",
    )

    @field_validator("reference_ids")
    @classmethod
    def validate_reference_ids(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip()
            if not value:
                msg = "reference_ids must not contain empty values."
                raise ValueError(msg)
            if value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        return cleaned

    @model_validator(mode="after")
    def validate_source(self):
        has_reference_ids = self.reference_ids is not None
        has_raw_payloads = self.raw_payloads is not None
        if has_reference_ids == has_raw_payloads:
            msg = "Exactly one of 'reference_ids' or 'raw_payloads' must be provided."
            raise ValueError(msg)
        return self


class DeploymentHistoryBindingUpdateRequest(BaseModel):
    add: list[str] | None = Field(
        None,
        description="History checkpoint ids to attach to the deployment. Omit to leave unchanged.",
    )
    remove: list[str] | None = Field(
        None,
        description="History checkpoint ids to detach from the deployment. Omit to leave unchanged.",
    )

    @field_validator("add", "remove")
    @classmethod
    def validate_id_lists(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip()
            if not value:
                msg = "history ids must not contain empty values."
                raise ValueError(msg)
            if value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        return cleaned

    @model_validator(mode="after")
    def validate_operations(self):
        add_values = self.add or []
        remove_values = self.remove or []
        overlap = set(add_values).intersection(remove_values)
        if overlap:
            ids = ", ".join(sorted(overlap))
            msg = f"History ids cannot be present in both 'add' and 'remove': {ids}."
            raise ValueError(msg)
        return self


class DeploymentCreateRequest(BaseModel):
    spec: BaseDeploymentData = Field(description="The base metadata of the deployment.")
    project_id: UUID | None = Field(
        default=None,
        description="Langflow Project id to persist the deployment under. Defaults to user's Starter Project.",
    )
    history: DeploymentHistoryItemsRequest | None = Field(
        default=None,
        description="Langflow history checkpoint references used to build provider snapshots.",
    )
    config: ConfigItem | None = Field(default=None, description="Deployment config binding/create payload.")


class DeploymentCreateApiRequest(DeploymentCreateRequest):
    provider_id: DeploymentProviderId = Field(description="Deployment provider account id for adapter routing.")


class DeploymentUpdateRequest(BaseModel):
    spec: BaseDeploymentDataUpdate | None = Field(default=None, description="Deployment metadata updates.")
    history: DeploymentHistoryBindingUpdateRequest | None = Field(
        default=None,
        description="Langflow history checkpoint attach/detach patch payload.",
    )
    config: ConfigDeploymentBindingUpdate | None = Field(default=None, description="Deployment config binding patch.")


class SnapshotItemsCreateApiRequest(SnapshotItemsCreate):
    provider_id: DeploymentProviderId = Field(description="Deployment provider account id for adapter routing.")


class BaseConfigDataApiRequest(BaseConfigData):
    provider_id: DeploymentProviderId = Field(description="Deployment provider account id for adapter routing.")


class DeploymentExecutionApiRequest(DeploymentExecution):
    provider_id: DeploymentProviderId = Field(description="Deployment provider account id for adapter routing.")


def _to_provider_account_response(provider_account: DeploymentProviderAccount) -> DeploymentProviderAccountResponse:
    return DeploymentProviderAccountResponse(
        id=provider_account.id,
        account_id=provider_account.account_id,
        provider_key=provider_account.provider_key,
        backend_url=provider_account.backend_url,
        registered_at=provider_account.registered_at,
    )


# TODO: just use regex
def _extract_watsonx_account_id_from_url(backend_url: str) -> str | None:
    parsed = urlparse(backend_url)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    try:
        instances_index = path_segments.index("instances")
    except ValueError:
        return None

    account_index = instances_index + 1
    if account_index >= len(path_segments):
        return None
    return path_segments[account_index].strip() or None


def _resolve_account_id(*, provider_key: str, backend_url: str, account_id: str | None) -> str | None:
    if account_id:
        return account_id

    if provider_key == "watsonx-orchestrate":
        return _extract_watsonx_account_id_from_url(backend_url)

    return None


@router.post(  # TODO: validate the provider backend url and api key
    "/providers/",
    response_model=DeploymentProviderAccountResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Deployment Providers"],
)
async def create_provider_account(
    payload: DeploymentProviderAccountCreateRequest,
    user: CurrentActiveUser,
    db: DbSession,
):
    resolved_account_id = _resolve_account_id(
        provider_key=payload.provider_key,
        backend_url=payload.backend_url,
        account_id=payload.account_id,
    )
    provider_account = await create_provider_account_row(
        db,
        user_id=user.id,
        account_id=resolved_account_id,
        provider_key=payload.provider_key,
        backend_url=payload.backend_url,
        api_key=payload.api_key,
    )
    return _to_provider_account_response(provider_account)


@router.get("/providers/", response_model=DeploymentProviderAccountListResponse, tags=["Deployment Providers"])
async def list_provider_accounts(
    user: CurrentActiveUser,
    db: DbSession,
    params: Annotated[Params, Depends(_deployment_pagination_params)],
):
    provider_accounts = await list_provider_account_rows(db, user_id=user.id)
    total = len(provider_accounts)
    start = _page_offset(params.page, params.size)
    end = start + params.size
    page_items = provider_accounts[start:end]
    return DeploymentProviderAccountListResponse(
        deployment_providers=[_to_provider_account_response(item) for item in page_items],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/providers/{provider_id}",
    response_model=DeploymentProviderAccountResponse,
    tags=["Deployment Providers"],
)
async def get_provider_account(
    provider_id: DeploymentProviderId,
    user: CurrentActiveUser,
    db: DbSession,
):
    provider_account = await get_provider_account_row_by_id(db, provider_id=provider_id, user_id=user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    return _to_provider_account_response(provider_account)


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Deployment Providers"],
)
async def delete_provider_account(
    provider_id: DeploymentProviderId,
    user: CurrentActiveUser,
    db: DbSession,
):
    provider_account = await get_provider_account_row_by_id(db, provider_id=provider_id, user_id=user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    await delete_provider_account_row(db, provider_account=provider_account)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/providers/{provider_id}",
    response_model=DeploymentProviderAccountResponse,
    tags=["Deployment Providers"],
)
async def update_provider_account(
    provider_id: DeploymentProviderId,
    payload: DeploymentProviderUpdateRequest,
    user: CurrentActiveUser,
    db: DbSession,
):
    provider_account = await get_provider_account_row_by_id(db, provider_id=provider_id, user_id=user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")

    resolved_account_id = _resolve_account_id(
        provider_key=payload.provider_key or provider_account.provider_key,
        backend_url=payload.backend_url or provider_account.backend_url,
        account_id=payload.account_id if payload.account_id is not None else provider_account.account_id,
    )
    updated = await update_provider_account_row(
        db,
        provider_account=provider_account,
        account_id=resolved_account_id if payload.account_id is not None else None,
        provider_key=payload.provider_key,
        backend_url=payload.backend_url,
        api_key=payload.api_key,
    )
    return _to_provider_account_response(updated)


def _require_deployment_router_service() -> DeploymentRouterServiceProtocol:
    deployment_router_service = get_deployment_router_service()
    if deployment_router_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployment router service is not available.",
        )
    return deployment_router_service


async def _resolve_deployment_adapter(
    provider_id: DeploymentProviderId,
    *,
    user_id,
    db,
) -> DeploymentServiceProtocol:
    deployment_router_service = _require_deployment_router_service()
    try:
        return await deployment_router_service.resolve_adapter(provider_id=provider_id, user_id=user_id, db=db)
    except DeploymentAccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentRouterError as exc:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=status_code, detail=exc.message) from exc


async def _get_deployment_row_or_404(
    *,
    deployment_id: str,
    user_id: UUID,
    db,
) -> Deployment:
    deployment_row = await get_deployment_row(
        db,
        user_id=user_id,
        deployment_id=deployment_id,
    )
    if deployment_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")
    return deployment_row


async def _resolve_adapter_from_deployment(
    *,
    deployment_id: str,
    user_id: UUID,
    db,
) -> tuple[Deployment, DeploymentServiceProtocol]:
    deployment_row = await _get_deployment_row_or_404(
        deployment_id=deployment_id,
        user_id=user_id,
        db=db,
    )
    deployment_adapter = await _resolve_deployment_adapter(
        deployment_row.provider_account_id,
        user_id=user_id,
        db=db,
    )
    return deployment_row, deployment_adapter


def _raise_http_for_value_error(exc: ValueError) -> None:
    status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def _build_execution_lookup(
    *,
    execution_id: str,
    deployment_id: str,
    deployment_type: DeploymentType,
) -> DeploymentExecutionStatus:
    provider_input: dict[str, str] = {}
    if execution_id:
        provider_input["run_id"] = execution_id

    return DeploymentExecutionStatus(
        deployment_id=deployment_id,
        deployment_type=deployment_type,
        provider_input=provider_input,
    )


def _page_offset(page: int, size: int) -> int:
    return (page - 1) * size


def _as_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


def _is_secret_template_field(field_data: Any) -> bool:
    if not isinstance(field_data, dict):
        return False
    if field_data.get("type") == "SecretStr":
        return True
    return field_data.get("password") is True and field_data.get("load_from_db") is True


def _is_valid_variable_reference_name(value: str) -> bool:
    return value.isidentifier()


def _collect_secret_template_field_keys(payload: Any, output: dict[str, str | None]) -> None:
    if not isinstance(payload, dict):
        return

    # Graph-style flow payload: { nodes: [...] }
    nodes = payload.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            template = node.get("data", {}).get("node", {}).get("template")
            if isinstance(template, dict):
                for field_name, field_data in template.items():
                    # Avoid expensive function call and repeated .get() work by
                    # doing the same checks inline with minimal lookups.
                    if not isinstance(field_data, dict):
                        continue
                    # secretness: type == "SecretStr" or password is True
                    t = field_data.get("type")
                    if t != "SecretStr" and field_data.get("password") is not True:
                        continue
                    # require load_from_db True as additional filter
                    if field_data.get("load_from_db") is not True:
                        continue
                    if not (isinstance(field_name, str)):
                        continue
                    key = field_name.strip()
                    if not key:
                        continue
                    ref = field_data.get("value")
                    if isinstance(ref, str):
                        v = ref.strip()
                        if v:
                            output[key] = v

    # API object-style payload: { group: { component: { template: {...} } } }

    # API object-style payload: { group: { component: { template: {...} } } }
    for group in payload.values():
        if not isinstance(group, dict):
            continue
        for component in group.values():
            if not isinstance(component, dict):
                continue
            template = component.get("template")
            if not isinstance(template, dict):
                continue
            for field_name, field_data in template.items():
                if not isinstance(field_data, dict):
                    continue
                t = field_data.get("type")
                if t != "SecretStr" and field_data.get("password") is not True:
                    continue
                if field_data.get("load_from_db") is not True:
                    continue
                if not (isinstance(field_name, str)):
                    continue
                key = field_name.strip()
                if not key:
                    continue
                ref = field_data.get("value")
                if isinstance(ref, str):
                    v = ref.strip()
                    if v:
                        output[key] = v


async def _resolve_project_id_for_deployment_create(
    *,
    payload: DeploymentCreateRequest,
    user_id: UUID,
    db: DbSession,
) -> UUID:
    if payload.project_id is not None:
        project = (
            await db.exec(
                select(Folder).where(
                    Folder.user_id == user_id,
                    Folder.id == payload.project_id,
                )
            )
        ).first()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return project.id

    default_folder = await get_or_create_default_folder(db, user_id)
    return default_folder.id


async def _build_adapter_deployment_create_payload(
    *,
    payload: DeploymentCreateRequest,
    project_id: UUID,
    user_id: UUID,
    db,
) -> AdapterDeploymentCreate:
    history = payload.history
    if history is None:
        return AdapterDeploymentCreate(
            spec=payload.spec,
            project_id=project_id,
            snapshot=None,
            config=payload.config,
        )

    if history.artifact_type != ArtifactType.FLOW:
        msg = f"Unsupported history artifact type for deployment create: {history.artifact_type}."
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    if history.raw_payloads is not None:
        raw_payloads = [
            payload_item.model_copy(
                update={
                    "provider_data": {
                        **(payload_item.provider_data or {}),
                        "project_id": str(project_id),
                    }
                },
                deep=True,
            )
            for payload_item in history.raw_payloads
        ]
        adapter_snapshot_payload = SnapshotItems(
            artifact_type=history.artifact_type,
            raw_payloads=raw_payloads,
        )
        return AdapterDeploymentCreate(
            spec=payload.spec,
            project_id=project_id,
            snapshot=adapter_snapshot_payload,
            config=payload.config,
        )

    reference_ids = history.reference_ids or []
    raw_payloads = [
        artifact
        for _, artifact in await _build_flow_artifacts_from_history_references(
            reference_ids=reference_ids,
            user_id=user_id,
            project_id=project_id,
            db=db,
        )
    ]

    adapter_snapshot_payload = SnapshotItems(
        artifact_type=history.artifact_type,
        raw_payloads=raw_payloads,
    )
    return AdapterDeploymentCreate(
        spec=payload.spec,
        project_id=project_id,
        snapshot=adapter_snapshot_payload,
        config=payload.config,
    )


def _normalize_history_reference_ids(reference_ids: list[str]) -> list[UUID]:
    normalized: list[UUID] = []
    for history_ref in reference_ids:
        history_id = _as_uuid(str(history_ref))
        if history_id is None:
            msg = f"Invalid history checkpoint id: {history_ref}"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        normalized.append(history_id)
    return normalized


async def _fetch_project_scoped_history_rows(
    *,
    reference_ids: list[str],
    user_id: UUID,
    project_id: UUID,
    db,
):
    history_ids = _normalize_history_reference_ids(reference_ids)
    if not history_ids:
        return []

    indexed_history_selects = [
        select(
            literal(index).label("position"),
            literal(history_id).label("history_id"),
        )
        for index, history_id in enumerate(history_ids)
    ]
    indexed_history_ids_cte = (
        indexed_history_selects[0] if len(indexed_history_selects) == 1 else union_all(*indexed_history_selects)
    ).cte("indexed_history_ids")

    statement = (
        select(
            indexed_history_ids_cte.c.position,
            indexed_history_ids_cte.c.history_id,
            FlowHistory.id.label("flow_history_id"),
            FlowHistory.data.label("history_data"),
            Flow.id.label("flow_id"),
            Flow.name.label("flow_name"),
            Flow.description.label("flow_description"),
            Flow.tags.label("flow_tags"),
        )
        .select_from(indexed_history_ids_cte)
        .join(
            FlowHistory,
            and_(
                FlowHistory.user_id == user_id,
                FlowHistory.id == indexed_history_ids_cte.c.history_id,
            ),
        )
        .join(
            Flow,
            and_(
                Flow.id == FlowHistory.flow_id,
                Flow.user_id == user_id,
                Flow.folder_id == project_id,
            ),
        )
        .order_by(indexed_history_ids_cte.c.position)
    )
    rows = list((await db.exec(statement)).all())
    if len(rows) < len(history_ids):
        msg = "One or more history checkpoint ids are not checkpoints of flows in the selected project."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    return rows


async def _build_flow_artifacts_from_history_references(
    *,
    reference_ids: list[str],
    user_id: UUID,
    project_id: UUID,
    db,
) -> list[tuple[UUID, BaseFlowArtifact]]:
    rows = await _fetch_project_scoped_history_rows(
        reference_ids=reference_ids,
        user_id=user_id,
        project_id=project_id,
        db=db,
    )
    return [
        (
            row.history_id,
            BaseFlowArtifact(
                id=row.flow_id,
                name=row.flow_name,
                description=row.flow_description,
                data=row.history_data or {},
                tags=row.flow_tags,
                provider_data={"project_id": str(project_id)},
            ),
        )
        for row in rows
    ]


async def _sync_page_with_provider(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    user_id: UUID,
    provider_id: UUID,
    db,
    page: int,
    size: int,
    deployment_type: DeploymentType | None,
) -> tuple[list[tuple[Deployment, int]], int]:
    accepted_rows: list[tuple[Deployment, int]] = []
    cursor = _page_offset(page, size)
    guard = 0
    while len(accepted_rows) < size and guard < (size * 4 + 20):
        guard += 1
        batch = await list_deployment_rows_page(
            db,
            user_id=user_id,
            provider_account_id=provider_id,
            offset=cursor,
            limit=size - len(accepted_rows),
        )
        if not batch:
            break
        resource_keys = [row.resource_key for row, _ in batch]
        list_params = DeploymentListParams(
            deployment_types=[deployment_type] if deployment_type is not None else None,
            provider_params={"ids": resource_keys},
        )
        provider_view = await deployment_adapter.list_deployments(
            user_id=user_id,
            db=db,
            params=list_params,
        )
        provider_ids = {str(item.id) for item in provider_view.deployments if item.id}
        provider_names = {item.name for item in provider_view.deployments if item.name}
        for row, attached_count in batch:
            if row.resource_key in provider_ids or row.resource_key in provider_names:
                accepted_rows.append((row, attached_count))
                cursor += 1
                continue
            await delete_deployment_row_by_resource_key(
                db,
                user_id=user_id,
                provider_account_id=provider_id,
                resource_key=row.resource_key,
            )
    total = await count_deployment_rows(db, user_id=user_id, provider_account_id=provider_id)
    return accepted_rows, total


async def _attach_history_checkpoints(
    *,
    payload: DeploymentCreateRequest,
    user_id: UUID,
    deployment_row_id: UUID,
    snapshot_id_by_history_id: dict[UUID, str] | None = None,
    db,
) -> None:
    history = payload.history
    if history is None:
        return

    reference_ids = history.reference_ids or []
    for ref in reference_ids:
        history_id = _as_uuid(str(ref))
        if history_id is None:
            continue
        await create_deployment_attachment(
            db,
            user_id=user_id,
            history_id=history_id,
            deployment_id=deployment_row_id,
            snapshot_id=(snapshot_id_by_history_id or {}).get(history_id),
        )


async def _apply_checkpoint_patch_attachments(
    *,
    user_id: UUID,
    deployment_row_id: UUID,
    added_snapshot_bindings: list[tuple[UUID, str]],
    remove_history_ids: list[UUID],
    db,
) -> None:
    for history_uuid, snapshot_id in added_snapshot_bindings:
        existing = await get_deployment_attachment(
            db,
            user_id=user_id,
            history_id=history_uuid,
            deployment_id=deployment_row_id,
        )
        if existing is None:
            await create_deployment_attachment(
                db,
                user_id=user_id,
                history_id=history_uuid,
                deployment_id=deployment_row_id,
                snapshot_id=snapshot_id,
            )
            continue
        if existing.snapshot_id != snapshot_id:
            await update_deployment_attachment_snapshot_id(
                db,
                attachment=existing,
                snapshot_id=snapshot_id,
            )

    for history_uuid in remove_history_ids:
        await delete_deployment_attachment(
            db,
            user_id=user_id,
            history_id=history_uuid,
            deployment_id=deployment_row_id,
        )


@router.post(  # TODO: move this to the flows API
    "/variables/detections",
    response_model=DetectDeploymentEnvVarsResponse,
)
async def detect_deployment_environment_variables(
    payload: DetectDeploymentEnvVarsRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Detect environment variable placeholders from selected history checkpoints."""
    detected_by_key: dict[str, str | None] = {}
    try:
        for reference_id in payload.reference_ids:
            history_id = _as_uuid(reference_id)
            if history_id is None:
                msg = f"Invalid history checkpoint id: {reference_id}"
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
            history_entry = await get_flow_history_entry_or_raise(db, history_id, user.id)
            _collect_secret_template_field_keys(history_entry.data, detected_by_key)
    except FlowHistoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    variable_service = get_variable_service()
    existing_variable_names = set(await variable_service.list_variables(user.id, db))
    variables = []
    for key, ref in sorted(detected_by_key.items()):
        if not (isinstance(ref, str) and _is_valid_variable_reference_name(ref) and ref in existing_variable_names):
            continue
        variables.append(DetectedDeploymentEnvVar(key=key, global_variable_name=ref))
    return DetectDeploymentEnvVarsResponse(variables=variables)


@router.post("", response_model=DeploymentCreateResult, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    user: CurrentActiveUser,
    payload: DeploymentCreateApiRequest,
    db: DbSession,
):
    """Create a deployment for the selected provider account."""
    provider_id = payload.provider_id
    deployment_payload = DeploymentCreateRequest.model_validate(payload.model_dump(exclude={"provider_id"}))
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    provider_account = await get_provider_account_row_by_id(db, provider_id=provider_id, user_id=user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    project_id: UUID = await _resolve_project_id_for_deployment_create(
        payload=deployment_payload,
        user_id=user.id,
        db=db,
    )
    adapter_payload: AdapterDeploymentCreate = await _build_adapter_deployment_create_payload(
        payload=deployment_payload,
        project_id=project_id,
        user_id=user.id,
        db=db,
    )
    try:
        result: AdapterDeploymentCreateResult = await deployment_adapter.create_deployment(
            user_id=user.id,
            deployment=adapter_payload,
            db=db,
        )
    # TODO: Create functions that handle mapping
    # from deployment erros to HTTP errors
    except DeploymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except InvalidDeploymentOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except DeploymentSupportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except InvalidDeploymentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    deployment_row: Deployment | None = await get_deployment_row_by_resource_key(
        db,
        user_id=user.id,
        provider_account_id=provider_id,
        resource_key=str(result.id),
    )
    if deployment_row is None:
        deployment_row = await create_deployment_row(
            db,
            user_id=user.id,
            project_id=project_id,
            provider_account_id=provider_id,
            resource_key=str(result.id),
            name=result.name,
        )
    snapshot_id_by_history_id: dict[UUID, str] = {}
    history_reference_ids = deployment_payload.history.reference_ids if deployment_payload.history else None
    if history_reference_ids:
        created_snapshot_ids = [
            str(snapshot_id).strip() for snapshot_id in result.snapshot_ids if str(snapshot_id).strip()
        ]
        history_uuid_ids = [_as_uuid(str(history_id)) for history_id in history_reference_ids]
        valid_history_uuid_ids = [history_id for history_id in history_uuid_ids if history_id is not None]
        snapshot_id_by_history_id = dict(zip(valid_history_uuid_ids, created_snapshot_ids, strict=False))
    await _attach_history_checkpoints(
        payload=deployment_payload,
        user_id=user.id,
        deployment_row_id=deployment_row.id,
        snapshot_id_by_history_id=snapshot_id_by_history_id,
        db=db,
    )
    response_payload = result.model_dump(exclude_unset=True)
    response_payload["id"] = str(deployment_row.id)
    if isinstance(response_payload.get("provider_result"), dict):
        response_payload["provider_result"] = {
            **response_payload["provider_result"],
            "resource_key": deployment_row.resource_key,
        }
    return DeploymentCreateResult(**response_payload)


@router.get("/types", response_model=DeploymentTypesResponse)
async def list_deployment_types(
    provider_id: ProviderIdQuery,
    user: CurrentActiveUser,
    db: DbSession,
):
    """List deployment types for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        deployment_types = await deployment_adapter.list_deployment_types(
            user_id=user.id,
            db=db,
        )
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentTypesResponse(deployment_types=deployment_types)


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    provider_id: ProviderIdQuery,
    user: CurrentActiveUser,
    db: DbSession,
    params: Annotated[Params, Depends(_deployment_pagination_params)],
    deployment_type: Annotated[DeploymentType | None, Query()] = None,
):
    """List deployments for a provider account using lazy provider synchronization."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        rows_with_counts, total = await _sync_page_with_provider(
            deployment_adapter=deployment_adapter,
            user_id=user.id,
            provider_id=provider_id,
            db=db,
            page=params.page,
            size=params.size,
            deployment_type=deployment_type,
        )
        deployments = [
            DeploymentListItemResponse(
                id=str(row.id),
                resource_key=row.resource_key,
                type=deployment_type or DeploymentType.AGENT,
                name=row.name,
                attached_count=attached_count,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row, attached_count in rows_with_counts
        ]
    except InvalidDeploymentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentListResponse(
        deployments=deployments,
        deployment_type=deployment_type,
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get("/snapshots", response_model=SnapshotListResult)
async def list_snapshots(
    provider_id: ProviderIdQuery,
    user: CurrentActiveUser,
    db: DbSession,
    artifact_type: Annotated[ArtifactType | None, Query()] = None,
):
    """List snapshots for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        snapshot_list_result = await deployment_adapter.list_snapshots(
            user_id=user.id,
            artifact_type=artifact_type,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SnapshotListResult(**snapshot_list_result.model_dump(exclude_unset=True))


@router.post("/snapshots", response_model=SnapshotResult, status_code=status.HTTP_201_CREATED)
async def create_snapshots(
    payload: SnapshotItemsCreateApiRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create snapshots for a provider account."""
    provider_id = payload.provider_id
    snapshot_payload = SnapshotItemsCreate.model_validate(payload.model_dump(exclude={"provider_id"}))
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        create_result = await deployment_adapter.create_snapshots(
            user_id=user.id,
            snapshot_items=snapshot_payload,
            db=db,
        )
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SnapshotResult(**create_result.model_dump(exclude_unset=True))


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotGetResult)
async def get_snapshot(
    snapshot_id: str,
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get snapshot for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        snapshot = await deployment_adapter.get_snapshot(
            user_id=user.id,
            snapshot_id=snapshot_id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SnapshotGetResult(**snapshot.model_dump(exclude_unset=True))


@router.delete("/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snapshot(
    snapshot_id: str,
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete snapshot for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        await deployment_adapter.delete_snapshot(
            user_id=user.id,
            snapshot_id=snapshot_id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/configs", response_model=ConfigResult, status_code=status.HTTP_201_CREATED)
async def create_deployment_config(
    payload: BaseConfigDataApiRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create deployment config for a provider account."""
    provider_id = payload.provider_id
    config_payload = BaseConfigData.model_validate(payload.model_dump(exclude={"provider_id"}))
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        create_result = await deployment_adapter.create_deployment_config(
            config=config_payload,
            user_id=user.id,
            db=db,
        )
    except DeploymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ConfigResult(**create_result.model_dump(exclude_unset=True))


@router.get("/configs", response_model=ConfigListResult)
async def list_deployment_configs(
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """List deployment configs for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        configs_result: ConfigListResult = await deployment_adapter.list_deployment_configs(
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return configs_result


@router.get("/configs/{config_id}", response_model=ConfigItemResult)
async def get_deployment_config(
    config_id: str,
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get deployment config for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        config = await deployment_adapter.get_deployment_config(
            config_id=config_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ConfigItemResult(**config.model_dump(exclude_unset=True))


@router.post("/executions", response_model=DeploymentExecutionResult, status_code=status.HTTP_201_CREATED)
async def create_deployment_execution(
    payload: DeploymentExecutionApiRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create a provider-agnostic deployment execution."""
    provider_id = payload.provider_id
    execution_payload = DeploymentExecution.model_validate(payload.model_dump(exclude={"provider_id"}))
    deployment_row = await _get_deployment_row_or_404(
        deployment_id=str(execution_payload.deployment_id),
        user_id=user.id,
        db=db,
    )
    if deployment_row.provider_account_id != provider_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")
    execution_payload.deployment_id = deployment_row.resource_key
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        execution_result = await deployment_adapter.create_execution(
            execution=execution_payload,
            user_id=user.id,
            db=db,
        )
    except InvalidDeploymentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except DeploymentSupportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    result_payload = execution_result.model_dump(exclude_unset=True)
    provider_result = execution_result.provider_result if isinstance(execution_result.provider_result, dict) else {}
    result_payload["execution_id"] = provider_result.get("run_id")
    return DeploymentExecutionResult(**result_payload)


@router.get("/executions/{execution_id}", response_model=DeploymentExecutionResult)
async def get_deployment_execution(
    execution_id: str,
    provider_id: ProviderIdQuery,
    deployment_id: Annotated[str, Query(description="Deployment id for execution polling.")],
    deployment_type: Annotated[DeploymentType, Query(description="Deployment type for execution polling.")],
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get provider-agnostic deployment execution state/output."""
    deployment_row = await _get_deployment_row_or_404(
        deployment_id=deployment_id,
        user_id=user.id,
        db=db,
    )
    if deployment_row.provider_account_id != provider_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    execution_status = _build_execution_lookup(
        execution_id=execution_id,
        deployment_id=deployment_row.resource_key,
        deployment_type=deployment_type,
    )
    try:
        execution_result = await deployment_adapter.get_execution(
            execution_status=execution_status,
            user_id=user.id,
            db=db,
        )
    except InvalidDeploymentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except DeploymentSupportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    result_payload = execution_result.model_dump(exclude_unset=True)
    result_payload["execution_id"] = execution_id
    return DeploymentExecutionResult(**result_payload)


@router.patch("/configs/{config_id}", response_model=ConfigResult)
async def update_deployment_config(
    config_id: str,
    provider_id: ProviderIdQuery,
    payload: ConfigUpdate,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update deployment config for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        update_result = await deployment_adapter.update_deployment_config(
            config_id=config_id,
            update_data=payload,
            user_id=user.id,
            db=db,
        )
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ConfigResult(**update_result.model_dump(exclude_unset=True))


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment_config(
    config_id: str,
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete deployment config for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        await deployment_adapter.delete_deployment_config(
            config_id=config_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{deployment_id}", response_model=DeploymentDetailItem)
async def get_deployment(
    deployment_id: str,
    user: CurrentActiveUser,
    db: DbSession,
):
    """Get a deployment and derive provider routing from persisted deployment metadata."""
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=user.id,
        db=db,
    )
    try:
        deployment = await deployment_adapter.get_deployment(
            user_id=user.id,
            deployment_id=deployment_row.resource_key,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    response_payload = deployment.model_dump(exclude_unset=True)
    response_payload["id"] = str(deployment_row.id)
    provider_data = (
        response_payload.get("provider_data") if isinstance(response_payload.get("provider_data"), dict) else {}
    )
    response_payload["provider_data"] = {**provider_data, "resource_key": deployment_row.resource_key}
    return DeploymentDetailItem(**response_payload)


@router.patch(
    "/{deployment_id}",
    response_model=DeploymentUpdateResult,
)
async def update_deployment(
    deployment_id: str,
    payload: DeploymentUpdateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update a deployment and derive provider routing from persisted deployment metadata."""
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=user.id,
        db=db,
    )

    added_snapshot_bindings: list[tuple[UUID, str]] = []
    remove_history_ids: list[UUID] = []
    snapshot_add_ids: list[str] = []
    snapshot_remove_ids: list[str] = []
    if payload.history is not None:
        add_ids = payload.history.add or []
        remove_ids = payload.history.remove or []

        if add_ids:
            add_artifacts = await _build_flow_artifacts_from_history_references(
                reference_ids=add_ids,
                user_id=user.id,
                project_id=deployment_row.project_id,
                db=db,
            )
            create_snapshot_payload = SnapshotItemsCreate(
                artifact_type=ArtifactType.FLOW,
                raw_payloads=[artifact for _, artifact in add_artifacts],
            )
            snapshot_create_result = await deployment_adapter.create_snapshots(
                user_id=user.id,
                snapshot_items=create_snapshot_payload,
                db=db,
            )
            created_snapshot_ids = [
                str(snapshot_id).strip() for snapshot_id in snapshot_create_result.ids if str(snapshot_id).strip()
            ]
            if len(created_snapshot_ids) != len(add_artifacts):
                msg = "Created snapshot ids did not match the number of history attachments requested."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            added_snapshot_bindings = [
                (history_id, snapshot_id)
                for (history_id, _), snapshot_id in zip(add_artifacts, created_snapshot_ids, strict=False)
            ]
            snapshot_add_ids = [snapshot_id for _, snapshot_id in added_snapshot_bindings]

        if remove_ids:
            remove_history_ids = [_as_uuid(str(history_id)) for history_id in remove_ids]
            remove_history_ids = [history_id for history_id in remove_history_ids if history_id is not None]
            remove_attachments = await list_deployment_attachments_for_history_ids(
                db,
                user_id=user.id,
                deployment_id=deployment_row.id,
                history_ids=remove_history_ids,
            )
            snapshot_remove_ids = list(
                {
                    attachment.snapshot_id.strip()
                    for attachment in remove_attachments
                    if isinstance(attachment.snapshot_id, str) and attachment.snapshot_id.strip()
                }
            )

    snapshot_patch_payload = (
        SnapshotDeploymentBindingUpdate(add=snapshot_add_ids, remove=snapshot_remove_ids)
        if snapshot_add_ids or snapshot_remove_ids
        else None
    )
    adapter_payload = AdapterDeploymentUpdate(
        spec=payload.spec,
        config=payload.config,
        snapshot=snapshot_patch_payload,
    )
    try:
        update_result = await deployment_adapter.update_deployment(
            deployment_id=deployment_row.resource_key,
            update_data=adapter_payload,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except InvalidDeploymentOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except DeploymentSupportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except InvalidDeploymentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    await _apply_checkpoint_patch_attachments(
        user_id=user.id,
        deployment_row_id=deployment_row.id,
        added_snapshot_bindings=added_snapshot_bindings,
        remove_history_ids=remove_history_ids,
        db=db,
    )
    return DeploymentUpdateResult(**update_result.model_dump(exclude_unset=True))


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete a deployment and derive provider routing from persisted deployment metadata."""
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=user.id,
        db=db,
    )
    try:
        await deployment_adapter.delete_deployment(
            deployment_id=deployment_row.resource_key,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    await delete_deployment_row_by_id(
        db,
        user_id=user.id,
        deployment_id=deployment_row.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{deployment_id}/redeploy",
    response_model=DeploymentRedeploymentResult,
    status_code=status.HTTP_201_CREATED,
)
async def redeploy_deployment(
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Redeploy a deployment and derive provider routing from persisted deployment metadata."""
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=user.id,
        db=db,
    )
    try:
        redeploy_result = await deployment_adapter.redeploy_deployment(
            deployment_id=deployment_row.resource_key,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentRedeploymentResult(**redeploy_result.model_dump(exclude_unset=True))


@router.post(
    "/{deployment_id}/duplicate",
    response_model=DeploymentItem,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_deployment(
    deployment_id: str,
    payload: DeploymentDuplicateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Duplicate a deployment and derive provider routing from persisted deployment metadata."""
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=user.id,
        db=db,
    )
    try:
        clone_result = await deployment_adapter.duplicate_deployment(
            deployment_id=deployment_row.resource_key,
            deployment_type=payload.deployment_type,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentItem(**clone_result.model_dump(exclude_unset=True))


@router.get(
    "/{deployment_id}/status",
    response_model=DeploymentStatusResult,
)
async def get_deployment_status(
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get deployment health and derive provider routing from persisted deployment metadata."""
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=user.id,
        db=db,
    )
    try:
        health_result = await deployment_adapter.get_deployment_status(
            deployment_id=deployment_row.resource_key,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentStatusResult(**health_result.model_dump(exclude_unset=True))
