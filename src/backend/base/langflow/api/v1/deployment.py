from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from lfx.services.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    InvalidContentError,
    InvalidDeploymentTypeError,
)
from lfx.services.deployment.schema import (
    ArtifactType,
    DeploymentCreate,
    DeploymentCreateResult,
    DeploymentDeleteResult,
    DeploymentListResult,
    DeploymentType,
    SnapshotListResult,
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


class DeploymentListResponse(DeploymentListResult):
    """List deployments response."""

    count: int = Field(description="The number of deployments")


class DeploymentDeleteRequest(BaseModel):
    id: str = Field(min_length=1)


class DeploymentDeleteResponse(DeploymentDeleteResult):
    """Delete deployment response."""


class SnapshotListResponse(SnapshotListResult):
    """List snapshots response."""

    count: int = Field(description="The number of snapshots")


def _require_deployment_service() -> DeploymentServiceProtocol:
    deployment_service = get_deployment_service()
    if deployment_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployment service is not available.",
        )
    return deployment_service


@router.post("/deploy", response_model=DeploymentCreateResponse)
async def deploy(
    user: CurrentActiveUser,
    payload: DeploymentCreateRequest,
    db: DbSession,
):
    """Create a deployment through the configured deployment adapter."""
    deployment_service = _require_deployment_service()
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


@router.delete("/deployment", response_model=DeploymentDeleteResponse)
async def delete_deployment(
    payload: DeploymentDeleteRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete a deployment through the configured deployment adapter."""
    deployment_service = _require_deployment_service()
    try:
        deletion_result = await deployment_service.delete_deployment(
            deployment_id=payload.id,
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


@router.get("/snapshot", response_model=SnapshotListResponse)
async def list_snapshots(
    user: CurrentActiveUser,
    db: DbSession,
    artifact_type: ArtifactType | None = None,
):
    """List snapshots through the configured deployment adapter."""
    deployment_service = _require_deployment_service()
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


# list deployments
@router.get("/deployment", response_model=DeploymentListResponse)
async def list_deployments(
    user: CurrentActiveUser,
    db: DbSession,
    deployment_type: DeploymentType | None = None,
):
    """List deployments through the configured deployment adapter."""
    deployment_service = _require_deployment_service()
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
