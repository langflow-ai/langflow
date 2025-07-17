"""API endpoints for package manager."""

import os
import signal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_service
from langflow.services.package_manager import PackageManagerService
from langflow.services.package_manager.models import InstallRequest, InstallResponse, OptionalDependency, PackageStatus
from langflow.services.schema import ServiceType


class RestartResponse(BaseModel):
    """Response from a restart request."""
    message: str
    restarting: bool


async def restart_server():
    """Restart the server process."""
    import asyncio
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Give a small delay to let the response be sent
    await asyncio.sleep(1)
    
    try:
        # Send SIGTERM to the current process to trigger a graceful shutdown
        # This works well with process managers like uvicorn, gunicorn, etc.
        logger.info("Triggering server restart via SIGTERM")
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception as e:
        logger.error(f"Error during restart: {e}")


def get_package_manager_service() -> PackageManagerService:
    """Get the PackageManagerService instance."""
    from langflow.services.package_manager.factory import PackageManagerServiceFactory

    return get_service(ServiceType.PACKAGE_MANAGER_SERVICE, PackageManagerServiceFactory())


router = APIRouter(prefix="/package-manager", tags=["Package Manager"])


@router.get("/optional-dependencies", response_model=dict[str, OptionalDependency])
async def get_optional_dependencies(
    current_user: CurrentActiveUser,
    package_service: PackageManagerService = Depends(lambda: get_package_manager_service())
) -> dict[str, OptionalDependency]:
    """Get all optional dependencies and their installation status.
    
    Returns:
        Dict mapping dependency names to their metadata and status
    """
    try:
        return package_service.get_optional_dependencies()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching optional dependencies: {e!s}"
        )


@router.post("/install", response_model=InstallResponse)
async def install_dependency(
    request: InstallRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,
    package_service: PackageManagerService = Depends(lambda: get_package_manager_service())
) -> InstallResponse:
    """Install an optional dependency group.
    
    Args:
        request: Installation request with dependency name
        
    Returns:
        Installation response with status and messages
        
    Raises:
        HTTPException: If user doesn't have permission or installation fails
    """
    # Check if user has permission (you might want to restrict this to admins)
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can install packages"
        )

    try:
        # Install the dependency with auto_restart option
        result = await package_service.install_dependency(request.dependency_name, request.auto_restart)
        
        # If auto_restart is requested and installation was successful, schedule restart
        if request.auto_restart and result.status == PackageStatus.INSTALLED:
            background_tasks.add_task(restart_server)
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error installing dependency: {e!s}"
        )


@router.post("/restart", response_model=RestartResponse)
async def restart_backend(
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,
) -> RestartResponse:
    """Restart the backend server.
    
    This endpoint triggers a graceful restart of the backend process.
    Useful after installing new packages that require a restart.
    
    Raises:
        HTTPException: If user doesn't have permission
    """
    # Check if user has permission (restrict to admins)
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can restart the server"
        )
    
    # Schedule the restart in the background so we can send a response first
    background_tasks.add_task(restart_server)
    
    return RestartResponse(
        message="Server restart initiated. The backend will be available shortly.",
        restarting=True
    )
