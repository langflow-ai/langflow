from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from lfx.services.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.deployment.schema import (
    ArtifactType,
    BaseFlowArtifact,
    DeploymentCreate,
    DeploymentCreateResult,
    DeploymentDetailItem,
    DeploymentExecution,
    DeploymentExecutionResult,
    DeploymentExecutionStatus,
    DeploymentItem,
    DeploymentListFilterOptions,
    DeploymentProviderId,
    DeploymentRedeploymentResult,
    DeploymentStatusResult,
    DeploymentType,
    DeploymentUpdate,
    DeploymentUpdateResult,
    SnapshotGetResult,
    SnapshotItems,
    SnapshotItemsCreate,
    SnapshotResult,
)
from lfx.services.deployment_router.exceptions import (
    DeploymentAccountNotFoundError,
    DeploymentRouterError,
)
from lfx.services.deps import get_deployment_router_service
from lfx.services.interfaces import DeploymentRouterServiceProtocol, DeploymentServiceProtocol
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.deployment.crud import (
    count_deployment_rows,
    create_deployment_row,
    delete_deployment_row_by_resource_key,
    get_deployment_row_by_resource_key,
    list_deployment_rows_page,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.crud import (
    create_provider_account_for_user,
    delete_provider_account_for_user,
    get_provider_account_by_id_for_user,
    list_provider_accounts_for_user,
    update_provider_account_for_user,
)
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_history.crud import get_flow_history_entry_or_raise
from langflow.services.database.models.flow_history.exceptions import FlowHistoryNotFoundError
from langflow.services.database.models.flow_history_deployment_attachment.crud import (
    create_deployment_attachment,
    delete_deployment_attachment,
    get_deployment_attachment,
)
from langflow.services.deps import get_variable_service

router = APIRouter(prefix="/deployments", tags=["Deployments"])


ProviderIdQuery = Annotated[
    DeploymentProviderId,
    Query(description="The registered deployment provider account id used for adapter routing."),
]


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
    updated_at: datetime | None
    has_api_key: bool


class DeploymentProviderAccountListResponse(BaseModel):
    deployment_providers: list[DeploymentProviderAccountResponse]
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentListResponse(BaseModel):
    deployments: list["DeploymentListItemResponse"]
    deployment_type: DeploymentType | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentListItemResponse(BaseModel):
    id: str
    resource_key: str
    type: DeploymentType
    name: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict | None = None


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


def _to_provider_account_response(provider_account: DeploymentProviderAccount) -> DeploymentProviderAccountResponse:
    return DeploymentProviderAccountResponse(
        id=provider_account.id,
        account_id=provider_account.account_id,
        provider_key=provider_account.provider_key,
        backend_url=provider_account.backend_url,
        registered_at=provider_account.registered_at,
        updated_at=provider_account.updated_at,
        has_api_key=bool(provider_account.api_key),
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
    provider_account = await create_provider_account_for_user(
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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    provider_accounts = await list_provider_accounts_for_user(db, user_id=user.id)
    total = len(provider_accounts)
    start = _page_offset(page, page_size)
    end = start + page_size
    page_items = provider_accounts[start:end]
    return DeploymentProviderAccountListResponse(
        deployment_providers=[_to_provider_account_response(item) for item in page_items],
        page=page,
        page_size=page_size,
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
    provider_account = await get_provider_account_by_id_for_user(db, provider_id=provider_id, user_id=user.id)
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
    provider_account = await get_provider_account_by_id_for_user(db, provider_id=provider_id, user_id=user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    await delete_provider_account_for_user(db, provider_account=provider_account)
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
    provider_account = await get_provider_account_by_id_for_user(db, provider_id=provider_id, user_id=user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")

    resolved_account_id = _resolve_account_id(
        provider_key=payload.provider_key or provider_account.provider_key,
        backend_url=payload.backend_url or provider_account.backend_url,
        account_id=payload.account_id if payload.account_id is not None else provider_account.account_id,
    )
    updated = await update_provider_account_for_user(
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


def _page_offset(page: int, page_size: int) -> int:
    return (page - 1) * page_size


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
                    if not (
                        _is_secret_template_field(field_data) and isinstance(field_name, str) and field_name.strip()
                    ):
                        continue
                    if not (isinstance(field_data, dict) and field_data.get("load_from_db") is True):
                        continue
                    key = field_name.strip()
                    ref = field_data.get("value")
                    if isinstance(ref, str) and ref.strip():
                        output[key] = ref.strip()

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
                if not (_is_secret_template_field(field_data) and isinstance(field_name, str) and field_name.strip()):
                    continue
                if not (isinstance(field_data, dict) and field_data.get("load_from_db") is True):
                    continue
                key = field_name.strip()
                ref = field_data.get("value")
                if isinstance(ref, str) and ref.strip():
                    output[key] = ref.strip()


async def _resolve_project_id_for_deployment_create(
    *,
    payload: DeploymentCreate,
    user_id: UUID,
    db,
) -> UUID:
    snapshot = payload.snapshot
    if snapshot and snapshot.reference_ids:
        for history_ref in snapshot.reference_ids:
            history_id = UUID(history_ref) if isinstance(history_ref, str) else history_ref
            if history_id is None:
                continue
            history_entry = await get_flow_history_entry_or_raise(db, history_id, user_id)
            flow = (
                await db.exec(select(Flow).where(Flow.id == history_entry.flow_id, Flow.user_id == user_id))
            ).first()
            if flow and flow.folder_id:
                return flow.folder_id
    msg = "Could not resolve project_id for deployment. Include flow provider_data.project_id or history references."
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)


async def _build_adapter_deployment_create_payload(
    *,
    payload: DeploymentCreate,
    user_id: UUID,
    db,
) -> DeploymentCreate:
    snapshot = payload.snapshot
    if snapshot is None:
        return payload

    if snapshot.raw_payloads is not None:
        msg = (
            "Deployment create only accepts snapshot.reference_ids. Raw payloads are not allowed on this API endpoint."
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    if snapshot.artifact_type != ArtifactType.FLOW:
        msg = f"Unsupported snapshot artifact type for deployment create: {snapshot.artifact_type}."
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    reference_ids = snapshot.reference_ids or []
    raw_payloads: list[BaseFlowArtifact] = []
    for history_ref in reference_ids:
        history_id = _as_uuid(str(history_ref))
        if history_id is None:
            msg = f"Invalid history checkpoint id: {history_ref}"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        try:
            history_entry = await get_flow_history_entry_or_raise(db, history_id, user_id)
        except FlowHistoryNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        flow = (await db.exec(select(Flow).where(Flow.id == history_entry.flow_id, Flow.user_id == user_id))).first()
        if flow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        if flow.folder_id is None:
            msg = (
                "Could not resolve project_id for deployment. "
                "Include flow provider_data.project_id or history references."
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        raw_payloads.append(
            BaseFlowArtifact(
                id=flow.id,
                name=flow.name,
                description=flow.description,
                data=history_entry.data or {},
                tags=flow.tags,
                provider_data={"project_id": str(flow.folder_id)},
            )
        )

    adapter_snapshot_payload = SnapshotItems(
        artifact_type=snapshot.artifact_type,
        raw_payloads=raw_payloads,
    )
    return payload.model_copy(update={"snapshot": adapter_snapshot_payload}, deep=True)


async def _sync_page_with_provider(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    user_id: UUID,
    provider_id: UUID,
    db,
    page: int,
    page_size: int,
    deployment_type: DeploymentType | None,
) -> tuple[list[Deployment], int]:
    accepted_rows: list[Deployment] = []
    cursor = _page_offset(page, page_size)
    guard = 0
    while len(accepted_rows) < page_size and guard < (page_size * 4 + 20):
        guard += 1
        batch = await list_deployment_rows_page(
            db,
            user_id=user_id,
            provider_account_id=provider_id,
            offset=cursor,
            limit=page_size - len(accepted_rows),
        )
        if not batch:
            break
        resource_keys = [row.resource_key for row in batch]
        filter_options = DeploymentListFilterOptions(
            deployment_type=deployment_type,
            provider_filter={"ids": resource_keys, "names": resource_keys},
        )
        provider_view = await deployment_adapter.list_deployments(
            user_id=user_id,
            deployment_type=deployment_type,
            db=db,
            filter_options=filter_options,
        )
        provider_ids = {str(item.id) for item in provider_view.deployments if item.id}
        provider_names = {item.name for item in provider_view.deployments if item.name}
        for row in batch:
            if row.resource_key in provider_ids or row.resource_key in provider_names:
                accepted_rows.append(row)
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
    payload: DeploymentCreate,
    user_id: UUID,
    deployment_row_id: UUID,
    db,
) -> None:
    snapshot = payload.snapshot
    if snapshot is None:
        return

    reference_ids = snapshot.reference_ids or []
    for ref in reference_ids:
        history_id = _as_uuid(str(ref))
        if history_id is None:
            continue
        await get_flow_history_entry_or_raise(db, history_id, user_id)
        await create_deployment_attachment(
            db,
            user_id=user_id,
            history_id=history_id,
            deployment_id=deployment_row_id,
        )


async def _apply_checkpoint_patch_attachments(
    *,
    payload: DeploymentUpdate,
    user_id: UUID,
    deployment_row_id: UUID,
    db,
) -> None:
    if payload.snapshot is None:
        return

    add_ids = payload.snapshot.add or []
    remove_ids = payload.snapshot.remove or []

    for checkpoint_id in add_ids:
        history_uuid = _as_uuid(str(checkpoint_id))
        if history_uuid is None:
            continue
        await get_flow_history_entry_or_raise(db, history_uuid, user_id)
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
            )

    for checkpoint_id in remove_ids:
        history_uuid = _as_uuid(str(checkpoint_id))
        if history_uuid is None:
            continue
        await delete_deployment_attachment(
            db,
            user_id=user_id,
            history_id=history_uuid,
            deployment_id=deployment_row_id,
        )


@router.post(
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
    provider_id: ProviderIdQuery,
    payload: DeploymentCreate,
    db: DbSession,
):
    """Create a deployment for the selected provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    provider_account = await get_provider_account_by_id_for_user(db, provider_id=provider_id, user_id=user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    adapter_payload = await _build_adapter_deployment_create_payload(
        payload=payload,
        user_id=user.id,
        db=db,
    )
    try:
        result = await deployment_adapter.create_deployment(
            user_id=user.id,
            deployment=adapter_payload,
            db=db,
        )
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

    project_id = await _resolve_project_id_for_deployment_create(
        payload=payload,
        user_id=user.id,
        db=db,
    )
    deployment_row = await get_deployment_row_by_resource_key(
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
    await _attach_history_checkpoints(
        payload=payload,
        user_id=user.id,
        deployment_row_id=deployment_row.id,
        db=db,
    )

    return DeploymentCreateResult(**result.model_dump(exclude_unset=True))


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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    deployment_type: Annotated[DeploymentType | None, Query()] = None,
):
    """List deployments for a provider account using lazy provider synchronization."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        rows, total = await _sync_page_with_provider(
            deployment_adapter=deployment_adapter,
            user_id=user.id,
            provider_id=provider_id,
            db=db,
            page=page,
            page_size=page_size,
            deployment_type=deployment_type,
        )
        deployments = [
            DeploymentListItemResponse(
                id=str(row.id),
                resource_key=row.resource_key,
                type=deployment_type or DeploymentType.AGENT,
                name=row.name,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
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
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/snapshots", response_model=SnapshotResult, status_code=status.HTTP_201_CREATED)
async def create_snapshots(
    provider_id: ProviderIdQuery,
    payload: SnapshotItemsCreate,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create snapshots for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        create_result = await deployment_adapter.create_snapshots(
            user_id=user.id,
            snapshot_items=payload,
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


@router.post("/executions", response_model=DeploymentExecutionResult, status_code=status.HTTP_201_CREATED)
async def create_deployment_execution(
    provider_id: ProviderIdQuery,
    payload: DeploymentExecution,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create a provider-agnostic deployment execution."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        execution_result = await deployment_adapter.create_execution(
            execution=payload,
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
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    execution_status = _build_execution_lookup(
        execution_id=execution_id,
        deployment_id=deployment_id,
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


@router.get("/{deployment_id}", response_model=DeploymentDetailItem)
async def get_deployment(
    deployment_id: str,
    provider_id: ProviderIdQuery,
    user: CurrentActiveUser,
    db: DbSession,
):
    """Get a deployment for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        deployment = await deployment_adapter.get_deployment(
            user_id=user.id,
            deployment_id=deployment_id,
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
    return DeploymentDetailItem(**deployment.model_dump(exclude_unset=True))


@router.patch(
    "/{deployment_id}",
    response_model=DeploymentUpdateResult,
)
async def update_deployment(
    deployment_id: str,
    provider_id: ProviderIdQuery,
    payload: DeploymentUpdate,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update a deployment for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    deployment_row = await get_deployment_row_by_resource_key(
        db,
        user_id=user.id,
        provider_account_id=provider_id,
        resource_key=deployment_id,
    )
    if deployment_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found in deployment table.")

    adapter_payload = payload
    if payload.snapshot is not None:
        adapter_payload = DeploymentUpdate(
            spec=payload.spec,
            config=payload.config,
            snapshot=None,
        )
    try:
        update_result = await deployment_adapter.update_deployment(
            deployment_id=deployment_id,
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
        payload=payload,
        user_id=user.id,
        deployment_row_id=deployment_row.id,
        db=db,
    )
    return DeploymentUpdateResult(**update_result.model_dump(exclude_unset=True))


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: str,
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete a deployment for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        await deployment_adapter.delete_deployment(
            deployment_id=deployment_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    await delete_deployment_row_by_resource_key(
        db,
        user_id=user.id,
        provider_account_id=provider_id,
        resource_key=deployment_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{deployment_id}/redeploy",
    response_model=DeploymentRedeploymentResult,
    status_code=status.HTTP_201_CREATED,
)
async def redeploy_deployment(
    deployment_id: str,
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Redeploy a deployment for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        redeploy_result = await deployment_adapter.redeploy_deployment(
            deployment_id=deployment_id,
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
    provider_id: ProviderIdQuery,
    payload: DeploymentDuplicateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Duplicate a deployment for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        clone_result = await deployment_adapter.duplicate_deployment(
            deployment_id=deployment_id,
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
    provider_id: ProviderIdQuery,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get deployment health for a provider account."""
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=user.id, db=db)
    try:
        health_result = await deployment_adapter.get_deployment_status(
            deployment_id=deployment_id,
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
