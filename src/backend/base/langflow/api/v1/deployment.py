from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from lfx.services.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    InvalidContentError,
    InvalidDeploymentTypeError,
)
from lfx.services.deployment.schema import (
    AccountId,
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
    DeploymentProviderName,
    DeploymentRedeployResult,
    DeploymentType,
    DeploymentUpdate,
    DeploymentUpdateResult,
    SnapshotItem,
    SnapshotItemsCreate,
    SnapshotListResult,
    SnapshotResult,
)
from lfx.services.deps import get_deployment_service
from lfx.services.interfaces import DeploymentServiceProtocol
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


class SnapshotGetResponse(SnapshotItem):
    """Get snapshot response."""


class SnapshotDeleteResponse(BaseModel):
    """Delete snapshot response."""
    id: UUID | str = Field(description="The id of the deleted snapshot")
    message: str = Field(description="Operation status message")


def _get_deployment_provider_slug(deployment_service: DeploymentServiceProtocol) -> str:
    """Return the configured deployment provider slug for routing validation."""
    provider_name = getattr(deployment_service, "provider_name", None)
    if isinstance(provider_name, str) and provider_name.strip():
        return provider_name.strip()

    # Fallback for adapters that have not yet declared provider_name explicitly.
    class_name = deployment_service.__class__.__name__
    class_name = re.sub(r"DeploymentService$", "", class_name)
    slug = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", class_name).replace("_", "-").lower()
    return slug or "default"


def _require_deployment_service(
    *,
    provider: DeploymentProviderName | None = None,
    account_id: AccountId | None = None,
) -> tuple[DeploymentServiceProtocol, str]:
    deployment_service = get_deployment_service()
    if deployment_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployment service is not available.",
        )
    configured_provider = _get_deployment_provider_slug(deployment_service)
    if provider is not None and provider != configured_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment provider '{provider}' is not configured.",
        )
    if account_id is not None:
        # Keep account_id in the API contract even before service-level account routing is implemented.
        _ = account_id
    return deployment_service, configured_provider


async def _create_deployment(
    user: CurrentActiveUser,
    payload: DeploymentCreateRequest,
    db: DbSession,
    *,
    provider: DeploymentProviderName,
):
    """Create a deployment through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider)
    # print(payload)
    try:
        result = await deployment_service.create_deployment(
            user_id=user.id,
            deployment=payload,
            db=db,
        )
    except DeploymentConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from e
    except InvalidContentError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=e.message) from e
    except DeploymentError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message) from e
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return DeploymentCreateResponse(
        **result.model_dump(exclude_unset=True),
        message="Deployment created successfully.",
    )


@router.post("/providers/{provider}/accounts/{account_id}/deploy", response_model=DeploymentCreateResponse)
async def deploy(
    provider: DeploymentProviderName,
    account_id: AccountId,
    user: CurrentActiveUser,
    payload: DeploymentCreateRequest,
    db: DbSession,
):
    """Create a deployment in the specified provider."""
    _require_deployment_service(provider=provider, account_id=account_id)
    return await _create_deployment(
        user=user,
        payload=payload,
        db=db,
        provider=provider,
    )


@router.get(
    "/providers/{provider}/accounts/{account_id}/deployments/types",
    response_model=DeploymentTypesResponse,
)
async def list_deployment_types(
    provider: DeploymentProviderName,
    account_id: AccountId,
    user: CurrentActiveUser,
    db: DbSession,
):
    """List deployment types through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        deployment_types = await deployment_service.list_deployment_types(
            user_id=user.id,
            db=db,
        )
    except DeploymentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return DeploymentTypesResponse(
        deployment_types=deployment_types,
        count=len(deployment_types),
    )


@router.delete(
    "/providers/{provider}/accounts/{account_id}/deployments/{deployment_id}",
    response_model=DeploymentDeleteResponse,
)
async def delete_deployment(
    provider: DeploymentProviderName,
    account_id: AccountId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete a deployment through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        deletion_result = await deployment_service.delete_deployment(
            deployment_id=deployment_id,
            user_id=user.id,
            db=db,
        )
    except HTTPException as e:
        message = "Something went wrong while deleting the deployment."
        raise HTTPException(status_code=e.status_code, detail=message) from e
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return DeploymentDeleteResponse(
        **deletion_result.model_dump(exclude_unset=True),
        message="Deployment deleted successfully.",
    )


@router.patch(
    "/providers/{provider}/accounts/{account_id}/deployments/{deployment_id}",
    response_model=DeploymentUpdateResponse,
)
async def update_deployment(
    provider: DeploymentProviderName,
    account_id: AccountId,
    deployment_id: str,
    payload: DeploymentUpdateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update a deployment through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    if str(payload.id) != deployment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload id '{payload.id}' must match path deployment_id '{deployment_id}'.",
        )
    try:
        update_result = await deployment_service.update_deployment(
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


@router.post(
    "/providers/{provider}/accounts/{account_id}/deployments/{deployment_id}/redeploy",
    response_model=DeploymentRedeployResponse,
)
async def redeploy_deployment(
    provider: DeploymentProviderName,
    account_id: AccountId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Redeploy a deployment through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        redeploy_result = await deployment_service.redeploy_deployment(
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
    "/providers/{provider}/accounts/{account_id}/deployments/{deployment_id}/clone",
    response_model=DeploymentCloneResponse,
)
async def clone_deployment(
    provider: DeploymentProviderName,
    account_id: AccountId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Clone a deployment through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        clone_result = await deployment_service.clone_deployment(
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
    "/providers/{provider}/accounts/{account_id}/deployments/{deployment_id}/health",
    response_model=DeploymentHealthResponse,
)
async def get_deployment_health(
    provider: DeploymentProviderName,
    account_id: AccountId,
    deployment_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get deployment health through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        health_result = await deployment_service.get_deployment_health(
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

    return DeploymentHealthResponse(
        **health_result.model_dump(exclude_unset=True),
    )


@router.get("/deployments/snapshots", response_model=SnapshotListResponse)
async def list_snapshots(
    user: CurrentActiveUser,
    db: DbSession,
    provider: DeploymentProviderName | None = None,
    artifact_type: ArtifactType | None = None,
):
    """List snapshots through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider)
    try:
        snapshot_list_result = await deployment_service.list_snapshots(
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


@router.post(
    "/providers/{provider}/accounts/{account_id}/snapshots",
    response_model=SnapshotCreateResponse,
)
async def create_snapshots(
    provider: DeploymentProviderName,
    account_id: AccountId,
    payload: SnapshotCreateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create snapshots through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        create_result = await deployment_service.create_snapshots(
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


@router.get(
    "/providers/{provider}/accounts/{account_id}/snapshots/{snapshot_id}",
    response_model=SnapshotGetResponse,
)
async def get_snapshot(
    provider: DeploymentProviderName,
    account_id: AccountId,
    snapshot_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get snapshot through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        snapshot = await deployment_service.get_snapshot(
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


@router.delete(
    "/providers/{provider}/accounts/{account_id}/snapshots/{snapshot_id}",
    response_model=SnapshotDeleteResponse,
)
async def delete_snapshot(
    provider: DeploymentProviderName,
    account_id: AccountId,
    snapshot_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete snapshot through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        await deployment_service.delete_snapshot(
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

    return SnapshotDeleteResponse(
        id=snapshot_id,
        message="Snapshot deleted successfully.",
    )


@router.post(
    "/providers/{provider}/accounts/{account_id}/configs",
    response_model=DeploymentConfigCreateResponse,
)
async def create_deployment_config(
    provider: DeploymentProviderName,
    account_id: AccountId,
    payload: DeploymentConfigCreateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create deployment config through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        create_result = await deployment_service.create_deployment_config(
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


@router.get("/deployments/configs", response_model=DeploymentConfigListResponse)
async def list_deployment_configs(
    db: DbSession,
    user: CurrentActiveUser,
    provider: DeploymentProviderName | None = None,
):
    """List deployment configs through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider)
    try:
        configs_result = await deployment_service.list_deployment_configs(
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


@router.get(
    "/providers/{provider}/accounts/{account_id}/configs/{config_id}",
    response_model=DeploymentConfigGetResponse,
)
async def get_deployment_config(
    provider: DeploymentProviderName,
    account_id: AccountId,
    config_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Get deployment config through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        config = await deployment_service.get_deployment_config(
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


@router.patch(
    "/providers/{provider}/accounts/{account_id}/configs/{config_id}",
    response_model=DeploymentConfigUpdateResponse,
)
async def update_deployment_config(
    provider: DeploymentProviderName,
    account_id: AccountId,
    config_id: str,
    payload: DeploymentConfigUpdateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update deployment config through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    if str(payload.id) != config_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload id '{payload.id}' must match path config_id '{config_id}'.",
        )
    try:
        update_result = await deployment_service.update_deployment_config(
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


@router.delete(
    "/providers/{provider}/accounts/{account_id}/configs/{config_id}",
    response_model=DeploymentConfigDeleteResponse,
)
async def delete_deployment_config(
    provider: DeploymentProviderName,
    account_id: AccountId,
    config_id: str,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete deployment config through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        await deployment_service.delete_deployment_config(
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

    return DeploymentConfigDeleteResponse(
        id=config_id,
        message="Deployment config deleted successfully.",
    )


# list deployments
@router.get("/deployments", response_model=DeploymentListResponse)
async def list_deployments(
    user: CurrentActiveUser,
    db: DbSession,
    provider: DeploymentProviderName | None = None,
    deployment_type: DeploymentType | None = None,
):
    """List deployments through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider)
    try:
        deployments = await deployment_service.list_deployments(
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

    return DeploymentListResponse(
        **deployments.model_dump(exclude_unset=True),
        count=len(deployments.deployments),
    )


@router.get(
    "/providers/{provider}/accounts/{account_id}/deployments/{deployment_id}",
    response_model=DeploymentGetResponse,
)
async def get_deployment(
    provider: DeploymentProviderName,
    account_id: AccountId,
    deployment_id: str,
    user: CurrentActiveUser,
    db: DbSession,
):
    """Get a deployment through the configured deployment adapter."""
    deployment_service, _ = _require_deployment_service(provider=provider, account_id=account_id)
    try:
        deployment = await deployment_service.get_deployment(
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
