from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi_pagination import Params
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.adapters.deployment.schema import (
    BaseFlowArtifact,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    DeploymentListParams,
    DeploymentListTypesResult,
    DeploymentType,
    ExecutionCreate,
    SnapshotDeploymentBindingUpdate,
    SnapshotItems,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentCreate as AdapterDeploymentCreate,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentCreateResult as AdapterDeploymentCreateResult,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentUpdate as AdapterDeploymentUpdate,
)
from lfx.services.deps import get_deployment_adapter
from lfx.services.interfaces import DeploymentServiceProtocol
from sqlalchemy import and_, literal, union_all
from sqlmodel import func, select

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentCreateResponse,
    DeploymentDuplicateResponse,
    DeploymentGetResponse,
    DeploymentListItem,
    DeploymentListResponse,
    DeploymentProviderAccountCreate,
    DeploymentProviderAccountListResponse,
    DeploymentProviderAccountResponse,
    DeploymentProviderAccountUpdate,
    DeploymentStatusResponse,
    DeploymentTypeListResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    ExecutionCreateRequest,
    ExecutionCreateResponse,
    ExecutionStatusResponse,
    FlowVersionIdsQuery,
    RedeployResponse,
)
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.adapters.deployment.context import deployment_provider_scope
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    delete_deployment_by_id,
    delete_deployment_by_resource_key,
    get_deployment_by_resource_key,
    list_deployments_page,
)
from langflow.services.database.models.deployment.crud import (
    create_deployment as create_deployment_db,
)
from langflow.services.database.models.deployment.crud import (
    get_deployment as get_deployment_db,
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
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    create_deployment_attachment,
    delete_deployment_attachment,
    get_deployment_attachment,
    list_deployment_attachments_for_flow_version_ids,
    update_deployment_attachment_snapshot_id,
)
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.database.models.folder.model import Folder

router = APIRouter(prefix="/deployments", tags=["Deployments"])

DeploymentProviderAccountIdQuery = Annotated[
    UUID,
    Query(description="Langflow DB provider-account UUID (`deployment_provider_account.id`)."),
]
DeploymentProviderAccountIdPath = Annotated[
    UUID,
    Path(description="Langflow DB provider-account UUID (`deployment_provider_account.id`)."),
]
DeploymentIdPath = Annotated[
    UUID,
    Path(description="Langflow DB deployment UUID (`deployment.id`)."),
]


def _deployment_pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Params:
    return Params(page=page, size=size)


def _page_offset(page: int, size: int) -> int:
    return (page - 1) * size


def _as_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


def _raise_http_for_value_error(exc: ValueError) -> None:
    status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def _extract_watsonx_account_id_from_url(provider_url: str) -> str | None:
    parsed = urlparse(provider_url)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    try:
        instances_index = path_segments.index("instances")
    except ValueError:
        return None

    account_index = instances_index + 1
    if account_index >= len(path_segments):
        return None
    return path_segments[account_index].strip() or None


def _resolve_provider_tenant_id(*, provider_key: str, provider_url: str, provider_tenant_id: str | None) -> str | None:
    if provider_tenant_id:
        return provider_tenant_id
    if provider_key == "watsonx-orchestrate":
        return _extract_watsonx_account_id_from_url(provider_url)
    return None


def _to_provider_account_response(provider_account: DeploymentProviderAccount) -> DeploymentProviderAccountResponse:
    return DeploymentProviderAccountResponse(
        id=provider_account.id,
        provider_tenant_id=provider_account.account_id,
        provider_key=provider_account.provider_key,
        provider_url=provider_account.backend_url,
        created_at=provider_account.registered_at,
        updated_at=provider_account.updated_at,
    )


def _normalize_flow_version_query_ids(flow_version_ids: list[str] | None) -> list[UUID]:
    if not flow_version_ids:
        return []
    normalized: list[UUID] = []
    seen: set[UUID] = set()
    for raw in flow_version_ids:
        flow_version_uuid = _as_uuid(raw.strip())
        if flow_version_uuid is None or flow_version_uuid in seen:
            continue
        seen.add(flow_version_uuid)
        normalized.append(flow_version_uuid)
    return normalized


async def _get_owned_provider_account_or_404(
    *,
    provider_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> DeploymentProviderAccount:
    provider_account = await get_provider_account_row_by_id(db, provider_id=provider_id, user_id=user_id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    return provider_account


async def _resolve_deployment_adapter(
    provider_id: UUID,
    *,
    user_id: UUID,
    db: DbSession,
) -> DeploymentServiceProtocol:
    provider_account = await _get_owned_provider_account_or_404(provider_id=provider_id, user_id=user_id, db=db)
    adapter_key = (provider_account.provider_key or "").strip()
    if not adapter_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deployment provider account has no provider_key configured.",
        )

    try:
        deployment_adapter = get_deployment_adapter(adapter_key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    if deployment_adapter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No deployment adapter registered for provider_key '{adapter_key}'.",
        )
    return deployment_adapter


async def _get_deployment_row_or_404(
    *,
    deployment_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> Deployment:
    deployment_row = await get_deployment_db(db, user_id=user_id, deployment_id=str(deployment_id))
    if deployment_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")
    return deployment_row


async def _resolve_adapter_from_deployment(
    *,
    deployment_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> tuple[Deployment, DeploymentServiceProtocol]:
    deployment_row = await _get_deployment_row_or_404(deployment_id=deployment_id, user_id=user_id, db=db)
    deployment_adapter = await _resolve_deployment_adapter(
        deployment_row.provider_account_id,
        user_id=user_id,
        db=db,
    )
    return deployment_row, deployment_adapter


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


async def _fetch_project_scoped_flow_version_rows(
    *,
    reference_ids: list[str],
    user_id: UUID,
    project_id: UUID,
    db: DbSession,
):
    flow_version_ids: list[UUID] = []
    for flow_version_ref in reference_ids:
        flow_version_id = _as_uuid(flow_version_ref)
        if flow_version_id is None:
            msg = f"Invalid flow version id: {flow_version_ref}"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        flow_version_ids.append(flow_version_id)
    if not flow_version_ids:
        return []

    indexed_flow_version_selects = [
        select(
            literal(index).label("position"),
            literal(flow_version_id).label("flow_version_id"),
        )
        for index, flow_version_id in enumerate(flow_version_ids)
    ]
    indexed_flow_version_ids_cte = (
        indexed_flow_version_selects[0]
        if len(indexed_flow_version_selects) == 1
        else union_all(*indexed_flow_version_selects)
    ).cte("indexed_flow_version_ids")

    statement = (
        select(
            indexed_flow_version_ids_cte.c.position,
            indexed_flow_version_ids_cte.c.flow_version_id,
            FlowVersion.id.label("flow_version_id"),
            FlowVersion.data.label("flow_version_data"),
            Flow.id.label("flow_id"),
            Flow.name.label("flow_name"),
            Flow.description.label("flow_description"),
            Flow.tags.label("flow_tags"),
        )
        .select_from(indexed_flow_version_ids_cte)
        .join(
            FlowVersion,
            and_(
                FlowVersion.user_id == user_id,
                FlowVersion.id == indexed_flow_version_ids_cte.c.flow_version_id,
            ),
        )
        .join(
            Flow,
            and_(
                Flow.id == FlowVersion.flow_id,
                Flow.user_id == user_id,
                Flow.folder_id == project_id,
            ),
        )
        .order_by(indexed_flow_version_ids_cte.c.position)
    )
    rows = list((await db.exec(statement)).all())
    if len(rows) < len(flow_version_ids):
        msg = "One or more flow version ids are not checkpoints of flows in the selected project."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    return rows


async def _build_flow_artifacts_from_flow_versions(
    *,
    flow_version_ids: list[str],
    user_id: UUID,
    project_id: UUID,
    db: DbSession,
) -> list[tuple[UUID, BaseFlowArtifact]]:
    rows = await _fetch_project_scoped_flow_version_rows(
        reference_ids=flow_version_ids,
        user_id=user_id,
        project_id=project_id,
        db=db,
    )
    return [
        (
            row.flow_version_id,
            BaseFlowArtifact(
                id=row.flow_id,
                name=row.flow_name,
                description=row.flow_description,
                data=row.flow_version_data or {},
                tags=row.flow_tags,
                provider_data={"project_id": str(project_id)},
            ),
        )
        for row in rows
    ]


def _to_adapter_create_config(payload: DeploymentCreateRequest) -> ConfigItem | None:
    if payload.config is None:
        return None
    if payload.config.reference_id is not None:
        return ConfigItem(reference_id=payload.config.reference_id)
    return ConfigItem(raw_payload=payload.config.raw_payload)


def _to_adapter_update_config(payload: DeploymentUpdateRequest) -> ConfigDeploymentBindingUpdate | None:
    if payload.config is None:
        return None
    return ConfigDeploymentBindingUpdate(config_id=payload.config.config_id)


async def _build_adapter_deployment_create_payload(
    *,
    payload: DeploymentCreateRequest,
    project_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> AdapterDeploymentCreate:
    flow_version_ids = payload.flow_version_ids
    if flow_version_ids is None:
        return AdapterDeploymentCreate(spec=payload.spec, snapshot=None, config=_to_adapter_create_config(payload))

    artifacts = await _build_flow_artifacts_from_flow_versions(
        flow_version_ids=flow_version_ids.ids,
        user_id=user_id,
        project_id=project_id,
        db=db,
    )
    return AdapterDeploymentCreate(
        spec=payload.spec,
        snapshot=SnapshotItems(raw_payloads=[artifact for _, artifact in artifacts]),
        config=_to_adapter_create_config(payload),
    )


async def _sync_page_with_provider(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    user_id: UUID,
    provider_id: UUID,
    db: DbSession,
    page: int,
    size: int,
    deployment_type: DeploymentType | None,
    flow_version_ids: list[UUID] | None = None,
) -> tuple[list[tuple[Deployment, int, list[str]]], int]:
    accepted_rows: list[tuple[Deployment, int, list[str]]] = []
    cursor = _page_offset(page, size)
    guard = 0
    while len(accepted_rows) < size and guard < (size * 4 + 20):
        guard += 1
        batch = await list_deployments_page(
            db,
            user_id=user_id,
            deployment_provider_account_id=provider_id,
            offset=cursor,
            limit=size - len(accepted_rows),
            flow_version_ids=flow_version_ids,
        )
        if not batch:
            break

        resource_keys = [row.resource_key for row, _, _ in batch]
        provider_view = await deployment_adapter.list(
            user_id=user_id,
            db=db,
            params=DeploymentListParams(
                deployment_types=[deployment_type] if deployment_type is not None else None,
                provider_params={"ids": resource_keys},
            ),
        )
        provider_ids = {str(item.id) for item in provider_view.deployments if item.id}
        provider_names = {item.name for item in provider_view.deployments if item.name}
        for row, attached_count, matched_flow_versions in batch:
            if row.resource_key in provider_ids or row.resource_key in provider_names:
                accepted_rows.append((row, attached_count, matched_flow_versions))
                cursor += 1
                continue
            await delete_deployment_by_resource_key(
                db,
                user_id=user_id,
                deployment_provider_account_id=provider_id,
                resource_key=row.resource_key,
            )
    total = await count_deployments_by_provider(
        db,
        user_id=user_id,
        deployment_provider_account_id=provider_id,
        flow_version_ids=flow_version_ids,
    )
    return accepted_rows, total


async def _attach_flow_versions(
    *,
    payload: DeploymentCreateRequest,
    user_id: UUID,
    deployment_row_id: UUID,
    snapshot_id_by_flow_version_id: dict[UUID, str] | None = None,
    db: DbSession,
) -> None:
    if payload.flow_version_ids is None:
        return

    for ref in payload.flow_version_ids.ids:
        flow_version_id = _as_uuid(ref)
        if flow_version_id is None:
            continue
        await create_deployment_attachment(
            db,
            user_id=user_id,
            flow_version_id=flow_version_id,
            deployment_id=deployment_row_id,
            snapshot_id=(snapshot_id_by_flow_version_id or {}).get(flow_version_id),
        )


async def _apply_flow_version_patch_attachments(
    *,
    user_id: UUID,
    deployment_row_id: UUID,
    added_snapshot_bindings: list[tuple[UUID, str]],
    remove_flow_version_ids: list[UUID],
    db: DbSession,
) -> None:
    for flow_version_uuid, snapshot_id in added_snapshot_bindings:
        existing = await get_deployment_attachment(
            db,
            user_id=user_id,
            flow_version_id=flow_version_uuid,
            deployment_id=deployment_row_id,
        )
        if existing is None:
            await create_deployment_attachment(
                db,
                user_id=user_id,
                flow_version_id=flow_version_uuid,
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

    for flow_version_uuid in remove_flow_version_ids:
        await delete_deployment_attachment(
            db,
            user_id=user_id,
            flow_version_id=flow_version_uuid,
            deployment_id=deployment_row_id,
        )


def _extract_execution_id(provider_result: dict | None) -> str | None:
    if not isinstance(provider_result, dict):
        return None
    return str(provider_result.get("run_id") or provider_result.get("execution_id") or "").strip() or None


def _to_deployment_create_response(
    result: AdapterDeploymentCreateResult, deployment_id: UUID
) -> DeploymentCreateResponse:
    payload = result.model_dump(exclude_unset=True)
    return DeploymentCreateResponse(
        id=deployment_id,
        name=result.name,
        description=result.description,
        type=result.type,
        provider_data=payload.get("provider_result"),
    )


@router.post(
    "/providers",
    response_model=DeploymentProviderAccountResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Deployment Providers"],
)
async def create_provider_account(
    session: DbSession,
    payload: DeploymentProviderAccountCreate,
    current_user: CurrentActiveUser,
):
    resolved_provider_tenant_id = _resolve_provider_tenant_id(
        provider_key=payload.provider_key,
        provider_url=payload.provider_url,
        provider_tenant_id=payload.provider_tenant_id,
    )
    provider_account = await create_provider_account_row(
        session,
        user_id=current_user.id,
        account_id=resolved_provider_tenant_id,
        provider_key=payload.provider_key,
        backend_url=payload.provider_url,
        api_key=payload.api_key.get_secret_value(),
    )
    return _to_provider_account_response(provider_account)


@router.get("/providers", response_model=DeploymentProviderAccountListResponse, tags=["Deployment Providers"])
async def list_provider_accounts(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    provider_accounts = await list_provider_account_rows(session, user_id=current_user.id)
    total = len(provider_accounts)
    start = _page_offset(page, size)
    end = start + size
    page_items = provider_accounts[start:end]
    return DeploymentProviderAccountListResponse(
        providers=[_to_provider_account_response(item) for item in page_items],
        page=page,
        size=size,
        total=total,
    )


@router.get(
    "/providers/{provider_id}",
    response_model=DeploymentProviderAccountResponse,
    tags=["Deployment Providers"],
)
async def get_provider_account(
    provider_id: DeploymentProviderAccountIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    provider_account = await get_provider_account_row_by_id(session, provider_id=provider_id, user_id=current_user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    return _to_provider_account_response(provider_account)


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Deployment Providers"],
)
async def delete_provider_account(
    provider_id: DeploymentProviderAccountIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    provider_account = await get_provider_account_row_by_id(session, provider_id=provider_id, user_id=current_user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    await delete_provider_account_row(session, provider_account=provider_account)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/providers/{provider_id}",
    response_model=DeploymentProviderAccountResponse,
    tags=["Deployment Providers"],
)
async def update_provider_account(
    provider_id: DeploymentProviderAccountIdPath,
    session: DbSession,
    payload: DeploymentProviderAccountUpdate,
    current_user: CurrentActiveUser,
):
    provider_account = await get_provider_account_row_by_id(session, provider_id=provider_id, user_id=current_user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")

    # Allow explicit null to clear provider_tenant_id.
    if "provider_tenant_id" in payload.model_fields_set and payload.provider_tenant_id is None:
        provider_account.account_id = None

    resolved_provider_tenant_id = _resolve_provider_tenant_id(
        provider_key=payload.provider_key or provider_account.provider_key,
        provider_url=payload.provider_url or provider_account.backend_url,
        provider_tenant_id=payload.provider_tenant_id
        if payload.provider_tenant_id is not None
        else provider_account.account_id,
    )
    updated = await update_provider_account_row(
        session,
        provider_account=provider_account,
        account_id=resolved_provider_tenant_id if payload.provider_tenant_id is not None else None,
        provider_key=payload.provider_key,
        backend_url=payload.provider_url,
        api_key=payload.api_key.get_secret_value() if payload.api_key is not None else None,
    )
    return _to_provider_account_response(updated)


@router.post("", response_model=DeploymentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    session: DbSession,
    payload: DeploymentCreateRequest,
    current_user: CurrentActiveUser,
):
    provider_id = payload.provider_id
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=current_user.id, db=session)
    project_id = await _resolve_project_id_for_deployment_create(payload=payload, user_id=current_user.id, db=session)
    adapter_payload = await _build_adapter_deployment_create_payload(
        payload=payload,
        project_id=project_id,
        user_id=current_user.id,
        db=session,
    )
    try:
        with deployment_provider_scope(provider_id):
            result = await deployment_adapter.create(
                user_id=current_user.id,
                payload=adapter_payload,
                db=session,
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

    deployment_row = await get_deployment_by_resource_key(
        session,
        user_id=current_user.id,
        deployment_provider_account_id=provider_id,
        resource_key=str(result.id),
    )
    if deployment_row is None:
        deployment_row = await create_deployment_db(
            session,
            user_id=current_user.id,
            project_id=project_id,
            deployment_provider_account_id=provider_id,
            resource_key=str(result.id),
            name=result.name,
        )

    snapshot_id_by_flow_version_id: dict[UUID, str] = {}
    flow_version_ids = payload.flow_version_ids.ids if payload.flow_version_ids else None
    if flow_version_ids:
        created_snapshot_ids = [
            str(snapshot_id).strip() for snapshot_id in result.snapshot_ids if str(snapshot_id).strip()
        ]
        flow_version_uuid_ids = [_as_uuid(flow_version_id) for flow_version_id in flow_version_ids]
        valid_flow_version_uuid_ids = [
            flow_version_id for flow_version_id in flow_version_uuid_ids if flow_version_id is not None
        ]
        snapshot_id_by_flow_version_id = dict(zip(valid_flow_version_uuid_ids, created_snapshot_ids, strict=False))
    await _attach_flow_versions(
        payload=payload,
        user_id=current_user.id,
        deployment_row_id=deployment_row.id,
        snapshot_id_by_flow_version_id=snapshot_id_by_flow_version_id,
        db=session,
    )
    return _to_deployment_create_response(result, deployment_row.id)


@router.get("/types", response_model=DeploymentTypeListResponse)
async def list_deployment_types(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=current_user.id, db=session)
    try:
        with deployment_provider_scope(provider_id):
            deployment_types_result: DeploymentListTypesResult = await deployment_adapter.list_types(
                user_id=current_user.id,
                db=session,
            )
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentTypeListResponse(deployment_types=deployment_types_result.deployment_types)


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    params: Annotated[Params, Depends(_deployment_pagination_params)],
    deployment_type: Annotated[DeploymentType | None, Query()] = None,
    flow_version_ids: Annotated[
        FlowVersionIdsQuery,
        Query(
            description=(
                "Optional Langflow flow version ids (pass as repeated query params, "
                "e.g. ?flow_version_ids=id1&flow_version_ids=id2). When provided, "
                "deployments are filtered to those with at least one matching "
                "attachment (OR semantics across ids)."
            )
        ),
    ] = None,
):
    normalized_flow_version_ids = _normalize_flow_version_query_ids(flow_version_ids)
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=current_user.id, db=session)
    try:
        with deployment_provider_scope(provider_id):
            rows_with_counts, total = await _sync_page_with_provider(
                deployment_adapter=deployment_adapter,
                user_id=current_user.id,
                provider_id=provider_id,
                db=session,
                page=params.page,
                size=params.size,
                deployment_type=deployment_type,
                flow_version_ids=normalized_flow_version_ids or None,
            )
        deployments = [
            DeploymentListItem(
                id=row.id,
                resource_key=row.resource_key,
                type=deployment_type or DeploymentType.AGENT,
                name=row.name,
                attached_count=attached_count,
                created_at=row.created_at,
                updated_at=row.updated_at,
                provider_data={"matched_flow_version_ids": matched_flow_versions}
                if normalized_flow_version_ids
                else None,
            )
            for row, attached_count, matched_flow_versions in rows_with_counts
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


@router.post("/executions", response_model=ExecutionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_execution(
    session: DbSession,
    payload: ExecutionCreateRequest,
    current_user: CurrentActiveUser,
):
    deployment_row = await _get_deployment_row_or_404(
        deployment_id=payload.deployment_id,
        user_id=current_user.id,
        db=session,
    )
    if deployment_row.provider_account_id != payload.provider_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")

    deployment_adapter = await _resolve_deployment_adapter(payload.provider_id, user_id=current_user.id, db=session)
    try:
        with deployment_provider_scope(payload.provider_id):
            execution_result = await deployment_adapter.create_execution(
                payload=ExecutionCreate(
                    deployment_id=deployment_row.resource_key,
                    provider_data=payload.provider_data,
                ),
                user_id=current_user.id,
                db=session,
            )
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

    provider_result = execution_result.provider_result if isinstance(execution_result.provider_result, dict) else None
    return ExecutionCreateResponse(
        execution_id=execution_result.execution_id or _extract_execution_id(provider_result),
        deployment_id=deployment_row.id,
        provider_data=provider_result,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionStatusResponse)
async def get_deployment_execution(
    execution_id: Annotated[str, Path(min_length=1, description="Provider-owned opaque execution identifier.")],
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    deployment_adapter = await _resolve_deployment_adapter(provider_id, user_id=current_user.id, db=session)
    execution_lookup_id = execution_id.strip()
    try:
        with deployment_provider_scope(provider_id):
            execution_result = await deployment_adapter.get_execution(
                execution_id=execution_lookup_id,
                user_id=current_user.id,
                db=session,
            )
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

    provider_result = execution_result.provider_result if isinstance(execution_result.provider_result, dict) else {}
    provider_deployment_id = str(
        provider_result.get("agent_id") or provider_result.get("deployment_id") or execution_result.deployment_id or ""
    ).strip()
    deployment_row = await get_deployment_by_resource_key(
        session,
        user_id=current_user.id,
        deployment_provider_account_id=provider_id,
        resource_key=provider_deployment_id,
    )
    if deployment_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")

    return ExecutionStatusResponse(
        execution_id=execution_result.execution_id or execution_id,
        deployment_id=deployment_row.id,
        provider_data=provider_result or None,
    )


@router.get("/{deployment_id}", response_model=DeploymentGetResponse)
async def get_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    try:
        with deployment_provider_scope(deployment_row.provider_account_id):
            deployment = await deployment_adapter.get(
                user_id=current_user.id,
                deployment_id=deployment_row.resource_key,
                db=session,
            )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    payload = deployment.model_dump(exclude_unset=True)
    provider_data = payload.get("provider_data") if isinstance(payload.get("provider_data"), dict) else {}
    provider_data = {**provider_data, "resource_key": deployment_row.resource_key}
    attached_count = int(
        (
            await session.exec(
                select(func.count(FlowVersionDeploymentAttachment.id)).where(
                    FlowVersionDeploymentAttachment.user_id == current_user.id,
                    FlowVersionDeploymentAttachment.deployment_id == deployment_row.id,
                )
            )
        ).one()
        or 0
    )
    return DeploymentGetResponse(
        id=deployment_row.id,
        name=deployment.name,
        description=getattr(deployment, "description", None),
        type=deployment.type,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        provider_data=provider_data,
        resource_key=deployment_row.resource_key,
        attached_count=attached_count,
    )


@router.patch(
    "/{deployment_id}",
    response_model=DeploymentUpdateResponse,
)
async def update_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    payload: DeploymentUpdateRequest,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )

    added_snapshot_bindings: list[tuple[UUID, str]] = []
    remove_flow_version_ids: list[UUID] = []
    snapshot_add_ids: list[str] = []
    snapshot_remove_ids: list[str] = []

    flow_version_patch = payload.flow_version_ids
    if flow_version_patch is not None:
        add_ids = flow_version_patch.add or []
        remove_ids = flow_version_patch.remove or []

        if add_ids:
            add_artifacts = await _build_flow_artifacts_from_flow_versions(
                flow_version_ids=add_ids,
                user_id=current_user.id,
                project_id=deployment_row.project_id,
                db=session,
            )
            materialize_snapshots = getattr(deployment_adapter, "materialize_snapshots", None)
            if materialize_snapshots is None:
                msg = "Deployment adapter does not support flow version snapshot materialization."
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
            with deployment_provider_scope(deployment_row.provider_account_id):
                created_snapshot_ids = await materialize_snapshots(
                    user_id=current_user.id,
                    raw_payloads=[artifact for _, artifact in add_artifacts],
                    config_id=payload.config.config_id if payload.config else None,
                    db=session,
                )
            created_snapshot_ids = [
                str(snapshot_id).strip() for snapshot_id in created_snapshot_ids if str(snapshot_id).strip()
            ]
            if len(created_snapshot_ids) != len(add_artifacts):
                msg = "Created snapshot ids did not match the number of flow version attachments requested."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            added_snapshot_bindings = [
                (flow_version_id, snapshot_id)
                for (flow_version_id, _), snapshot_id in zip(add_artifacts, created_snapshot_ids, strict=False)
            ]
            snapshot_add_ids = [snapshot_id for _, snapshot_id in added_snapshot_bindings]

        if remove_ids:
            remove_flow_version_ids = [_as_uuid(flow_version_id) for flow_version_id in remove_ids]
            remove_flow_version_ids = [
                flow_version_id for flow_version_id in remove_flow_version_ids if flow_version_id
            ]
            remove_attachments = await list_deployment_attachments_for_flow_version_ids(
                session,
                user_id=current_user.id,
                deployment_id=deployment_row.id,
                flow_version_ids=remove_flow_version_ids,
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
        config=_to_adapter_update_config(payload),
        snapshot=snapshot_patch_payload,
    )
    try:
        with deployment_provider_scope(deployment_row.provider_account_id):
            update_result = await deployment_adapter.update(
                deployment_id=deployment_row.resource_key,
                payload=adapter_payload,
                user_id=current_user.id,
                db=session,
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

    await _apply_flow_version_patch_attachments(
        user_id=current_user.id,
        deployment_row_id=deployment_row.id,
        added_snapshot_bindings=added_snapshot_bindings,
        remove_flow_version_ids=remove_flow_version_ids,
        db=session,
    )
    provider_data = update_result.provider_result if isinstance(update_result.provider_result, dict) else None
    return DeploymentUpdateResponse(
        id=deployment_row.id,
        name=payload.spec.name if payload.spec and payload.spec.name else deployment_row.name,
        description=payload.spec.description if payload.spec else None,
        type=DeploymentType.AGENT,
        created_at=deployment_row.created_at,
        updated_at=deployment_row.updated_at,
        provider_data=provider_data,
    )


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    try:
        with deployment_provider_scope(deployment_row.provider_account_id):
            await deployment_adapter.delete(
                deployment_id=deployment_row.resource_key,
                user_id=current_user.id,
                db=session,
            )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    await delete_deployment_by_id(session, user_id=current_user.id, deployment_id=deployment_row.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{deployment_id}/redeploy",
    response_model=RedeployResponse,
)
async def redeploy_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    try:
        with deployment_provider_scope(deployment_row.provider_account_id):
            redeploy_result = await deployment_adapter.redeploy(
                deployment_id=deployment_row.resource_key,
                user_id=current_user.id,
                db=session,
            )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    provider_data = redeploy_result.provider_result if isinstance(redeploy_result.provider_result, dict) else None
    return RedeployResponse(
        id=deployment_row.id,
        name=deployment_row.name,
        description=None,
        type=DeploymentType.AGENT,
        created_at=deployment_row.created_at,
        updated_at=deployment_row.updated_at,
        provider_data=provider_data,
    )


@router.post(
    "/{deployment_id}/duplicate",
    response_model=DeploymentDuplicateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    try:
        with deployment_provider_scope(deployment_row.provider_account_id):
            clone_result = await deployment_adapter.duplicate(
                deployment_id=deployment_row.resource_key,
                user_id=current_user.id,
                db=session,
            )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    duplicate_row = await get_deployment_by_resource_key(
        session,
        user_id=current_user.id,
        deployment_provider_account_id=deployment_row.provider_account_id,
        resource_key=str(clone_result.id),
    )
    if duplicate_row is None:
        duplicate_row = await create_deployment_db(
            session,
            user_id=current_user.id,
            project_id=deployment_row.project_id,
            deployment_provider_account_id=deployment_row.provider_account_id,
            resource_key=str(clone_result.id),
            name=clone_result.name,
        )
    return DeploymentDuplicateResponse(
        id=duplicate_row.id,
        name=clone_result.name,
        description=getattr(clone_result, "description", None),
        type=clone_result.type,
        created_at=clone_result.created_at,
        updated_at=clone_result.updated_at,
        provider_data=clone_result.provider_data,
    )


@router.get(
    "/{deployment_id}/status",
    response_model=DeploymentStatusResponse,
)
async def get_deployment_status(
    deployment_id: DeploymentIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter = await _resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    try:
        with deployment_provider_scope(deployment_row.provider_account_id):
            health_result = await deployment_adapter.get_status(
                deployment_id=deployment_row.resource_key,
                user_id=current_user.id,
                db=session,
            )
    except ValueError as exc:
        _raise_http_for_value_error(exc)
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentStatusResponse(
        id=deployment_row.id,
        name=deployment_row.name,
        description=None,
        type=DeploymentType.AGENT,
        created_at=deployment_row.created_at,
        updated_at=deployment_row.updated_at,
        provider_data=health_result.provider_data,
    )
