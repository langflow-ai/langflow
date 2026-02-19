from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from lfx.services.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    InvalidContentError,
    InvalidDeploymentTypeError,
)
from lfx.services.deployment.schema import (
    ArtifactType,
    BaseConfigData,
    ConfigItemResult,
    ConfigListResult,
    ConfigResult,
    ConfigUpdate,
    DeploymentCreate,
    DeploymentCreateResult,
    DeploymentDeleteResult,
    DeploymentHealthResult,
    DeploymentItem,
    DeploymentList,
    DeploymentProviderId,
    DeploymentRedeployResult,
    DeploymentType,
    DeploymentUpdate,
    DeploymentUpdateResult,
    SnapshotGetResult,
    SnapshotItemsCreate,
    SnapshotListResult,
    SnapshotResult,
)
from lfx.services.deps import get_deployment_router_service
from lfx.services.interfaces import DeploymentRouterServiceProtocol, DeploymentServiceProtocol
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser, DbSession

router = APIRouter(tags=["Base"])


class DeploymentCreateRequest(DeploymentCreate):
    """Create deployment request."""


class DeploymentCreateResponse(DeploymentCreateResult):
    """Create deployment response."""

    message: str = Field(description="Operation status message")


class DeploymentListResponse(DeploymentList):
    """List deployments response."""

    count: int = Field(description="The number of deployments")


class DeploymentDeleteResponse(DeploymentDeleteResult):
    """Delete deployment response."""

    message: str = Field(description="Operation status message")


class SnapshotListResponse(SnapshotListResult):
    """List snapshots response."""

    count: int = Field(description="The number of snapshots")


class DeploymentGetResponse(DeploymentItem):
    """Get deployment response."""


class DeploymentUpdateRequest(DeploymentUpdate):
    """Update deployment request."""


class DeploymentUpdateResponse(DeploymentUpdateResult):
    """Update deployment response."""

    message: str = Field(description="Operation status message")


class DeploymentRedeployResponse(DeploymentRedeployResult):
    """Redeploy deployment response."""

    message: str = Field(description="Operation status message")


class DeploymentCloneResponse(DeploymentItem):
    """Clone deployment response."""

    message: str = Field(description="Operation status message")


class DeploymentHealthResponse(DeploymentHealthResult):
    """Deployment health response."""


class DeploymentTypesResponse(BaseModel):
    """List deployment types response."""

    deployment_types: list[DeploymentType] = Field(description="The list of supported deployment types")
    count: int = Field(description="The number of supported deployment types")


class DeploymentConfigCreateRequest(BaseConfigData):
    """Create deployment config request."""


class DeploymentConfigCreateResponse(ConfigResult):
    """Create deployment config response."""

    message: str = Field(description="Operation status message")


class DeploymentConfigListResponse(ConfigListResult):
    """List deployment configs response."""

    count: int = Field(description="The number of deployment configs")


class DeploymentConfigGetResponse(ConfigItemResult):
    """Get deployment config response."""


class DeploymentConfigUpdateRequest(ConfigUpdate):
    """Update deployment config request."""


class DeploymentConfigUpdateResponse(ConfigResult):
    """Update deployment config response."""

    message: str = Field(description="Operation status message")


class DeploymentConfigDeleteResponse(BaseModel):
    """Delete deployment config response."""

    id: UUID | str = Field(description="The id of the deleted deployment config")
    message: str = Field(description="Operation status message")


class SnapshotCreateRequest(SnapshotItemsCreate):
    """Create snapshot request."""


class SnapshotCreateResponse(SnapshotResult):
    """Create snapshot response."""

    message: str = Field(description="Operation status message")


class SnapshotGetResponse(SnapshotGetResult):
    """Get snapshot response."""


class SnapshotDeleteResponse(BaseModel):
    """Delete snapshot response."""

    id: UUID | str = Field(description="The id of the deleted snapshot")
    message: str = Field(description="Operation status message")


def _require_deployment_router_service() -> DeploymentRouterServiceProtocol:
    deployment_router_service = get_deployment_router_service()
    if deployment_router_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployment router service is not available.",
        )
    return deployment_router_service


def _resolve_deployment_adapter(provider_id: DeploymentProviderId) -> DeploymentServiceProtocol:
    deployment_router_service = _require_deployment_router_service()
    return deployment_router_service.resolve_adapter(provider_id=provider_id)


@router.post("/deployment-providers/{provider_id}/deploy", response_model=DeploymentCreateResponse)
async def deploy(
    provider_id: DeploymentProviderId,
    user: CurrentActiveUser,
    payload: DeploymentCreateRequest,
    db: DbSession,
):
    """Create a deployment using the provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        result = await deployment_adapter.create_deployment(
            user_id=user.id,
            deployment=payload,
            db=db,
        )
    except DeploymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return DeploymentCreateResponse(**result.model_dump(exclude_unset=True), message="Deployment created successfully.")


@router.get("/deployment-providers/{provider_id}/deployments/types", response_model=DeploymentTypesResponse)
async def list_deployment_types(
    provider_id: DeploymentProviderId,
    user: CurrentActiveUser,
    db: DbSession,
):
    """List deployment types for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        deployment_types = await deployment_adapter.list_deployment_types(
            user_id=user.id,
            db=db,
        )
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentTypesResponse(deployment_types=deployment_types, count=len(deployment_types))


@router.get("/deployment-providers/{provider_id}/deployments", response_model=DeploymentListResponse)
async def list_deployments(
    provider_id: DeploymentProviderId,
    user: CurrentActiveUser,
    db: DbSession,
    deployment_type: DeploymentType | None = None,
):
    """List deployments for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        deployments = await deployment_adapter.list_deployments(
            user_id=user.id,
            deployment_type=deployment_type,
            db=db,
        )
    except InvalidDeploymentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentListResponse(**deployments.model_dump(exclude_unset=True), count=len(deployments.deployments))


@router.get("/deployment-providers/{provider_id}/deployments/{deployment_id}", response_model=DeploymentGetResponse)
async def get_deployment(
    provider_id: DeploymentProviderId,
    deployment_id: str,
    user: CurrentActiveUser,
    db: DbSession,
):
    """Get a deployment for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        deployment = await deployment_adapter.get_deployment(
            user_id=user.id,
            deployment_id=deployment_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentGetResponse(**deployment.model_dump(exclude_unset=True))


@router.patch(
    "/deployment-providers/{provider_id}/deployments/{deployment_id}",
    response_model=DeploymentUpdateResponse,
)
async def update_deployment(
    provider_id: DeploymentProviderId,
    deployment_id: str,
    payload: DeploymentUpdateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update a deployment for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    if str(payload.id) != deployment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload id '{payload.id}' must match path deployment_id '{deployment_id}'.",
        )
    try:
        update_result = await deployment_adapter.update_deployment(
            update_data=payload,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentUpdateResponse(
        **update_result.model_dump(exclude_unset=True),
        message="Deployment updated successfully.",
    )


@router.delete(
    "/deployment-providers/{provider_id}/deployments/{deployment_id}",
    response_model=DeploymentDeleteResponse,
)
async def delete_deployment(
    provider_id: DeploymentProviderId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete a deployment for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        deletion_result = await deployment_adapter.delete_deployment(
            deployment_id=deployment_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentDeleteResponse(
        **deletion_result.model_dump(exclude_unset=True),
        message="Deployment deleted successfully.",
    )


@router.post(
    "/deployment-providers/{provider_id}/deployments/{deployment_id}/redeploy",
    response_model=DeploymentRedeployResponse,
)
async def redeploy_deployment(
    provider_id: DeploymentProviderId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Redeploy a deployment for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        redeploy_result = await deployment_adapter.redeploy_deployment(
            deployment_id=deployment_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentRedeployResponse(
        **redeploy_result.model_dump(exclude_unset=True),
        message="Deployment redeployed successfully.",
    )


@router.post(
    "/deployment-providers/{provider_id}/deployments/{deployment_id}/clone",
    response_model=DeploymentCloneResponse,
)
async def clone_deployment(
    provider_id: DeploymentProviderId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Clone a deployment for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        clone_result = await deployment_adapter.clone_deployment(
            deployment_id=deployment_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentCloneResponse(
        **clone_result.model_dump(exclude_unset=True),
        message="Deployment cloned successfully.",
    )


@router.get(
    "/deployment-providers/{provider_id}/deployments/{deployment_id}/health",
    response_model=DeploymentHealthResponse,
)
async def get_deployment_health(
    provider_id: DeploymentProviderId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get deployment health for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        health_result = await deployment_adapter.get_deployment_health(
            deployment_id=deployment_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentHealthResponse(**health_result.model_dump(exclude_unset=True))


@router.get("/deployment-providers/{provider_id}/snapshots", response_model=SnapshotListResponse)
async def list_snapshots(
    provider_id: DeploymentProviderId,
    user: CurrentActiveUser,
    db: DbSession,
    artifact_type: ArtifactType | None = None,
):
    """List snapshots for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        snapshot_list_result = await deployment_adapter.list_snapshots(
            user_id=user.id,
            artifact_type=artifact_type,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SnapshotListResponse(
        **snapshot_list_result.model_dump(exclude_unset=True),
        count=len(snapshot_list_result.snapshots),
    )


@router.post("/deployment-providers/{provider_id}/snapshots", response_model=SnapshotCreateResponse)
async def create_snapshots(
    provider_id: DeploymentProviderId,
    payload: SnapshotCreateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create snapshots for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        create_result = await deployment_adapter.create_snapshots(
            user_id=user.id,
            snapshot_items=payload,
            db=db,
        )
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SnapshotCreateResponse(
        **create_result.model_dump(exclude_unset=True),
        message="Snapshot created successfully.",
    )


@router.get("/deployment-providers/{provider_id}/snapshots/{snapshot_id}", response_model=SnapshotGetResponse)
async def get_snapshot(
    provider_id: DeploymentProviderId,
    snapshot_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get snapshot for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        snapshot = await deployment_adapter.get_snapshot(
            user_id=user.id,
            snapshot_id=snapshot_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SnapshotGetResponse(**snapshot.model_dump(exclude_unset=True))


@router.delete("/deployment-providers/{provider_id}/snapshots/{snapshot_id}", response_model=SnapshotDeleteResponse)
async def delete_snapshot(
    provider_id: DeploymentProviderId,
    snapshot_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete snapshot for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        await deployment_adapter.delete_snapshot(
            user_id=user.id,
            snapshot_id=snapshot_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SnapshotDeleteResponse(id=snapshot_id, message="Snapshot deleted successfully.")


@router.post("/deployment-providers/{provider_id}/configs", response_model=DeploymentConfigCreateResponse)
async def create_deployment_config(
    provider_id: DeploymentProviderId,
    payload: DeploymentConfigCreateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create deployment config for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        create_result = await deployment_adapter.create_deployment_config(
            config=payload,
            user_id=user.id,
            db=db,
        )
    except DeploymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentConfigCreateResponse(
        **create_result.model_dump(exclude_unset=True),
        message="Deployment config created successfully.",
    )


@router.get("/deployment-providers/{provider_id}/configs", response_model=DeploymentConfigListResponse)
async def list_deployment_configs(
    provider_id: DeploymentProviderId,
    db: DbSession,
    user: CurrentActiveUser,
):
    """List deployment configs for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        configs_result = await deployment_adapter.list_deployment_configs(
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentConfigListResponse(
        **configs_result.model_dump(exclude_unset=True),
        count=len(configs_result.configs),
    )


@router.get("/deployment-providers/{provider_id}/configs/{config_id}", response_model=DeploymentConfigGetResponse)
async def get_deployment_config(
    provider_id: DeploymentProviderId,
    config_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get deployment config for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        config = await deployment_adapter.get_deployment_config(
            config_id=config_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentConfigGetResponse(**config.model_dump(exclude_unset=True))


@router.patch("/deployment-providers/{provider_id}/configs/{config_id}", response_model=DeploymentConfigUpdateResponse)
async def update_deployment_config(
    provider_id: DeploymentProviderId,
    config_id: str,
    payload: DeploymentConfigUpdateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update deployment config for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    if str(payload.id) != config_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload id '{payload.id}' must match path config_id '{config_id}'.",
        )
    try:
        update_result = await deployment_adapter.update_deployment_config(
            update_data=payload,
            user_id=user.id,
            db=db,
        )
    except InvalidContentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentConfigUpdateResponse(
        **update_result.model_dump(exclude_unset=True),
        message="Deployment config updated successfully.",
    )


@router.delete("/deployment-providers/{provider_id}/configs/{config_id}", response_model=DeploymentConfigDeleteResponse)
async def delete_deployment_config(
    provider_id: DeploymentProviderId,
    config_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete deployment config for a provider routing ID."""
    deployment_adapter = _resolve_deployment_adapter(provider_id)
    try:
        await deployment_adapter.delete_deployment_config(
            config_id=config_id,
            user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DeploymentConfigDeleteResponse(id=config_id, message="Deployment config deleted successfully.")
