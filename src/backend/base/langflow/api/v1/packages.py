import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser

router = APIRouter(prefix="/packages", tags=["Packages"])


class PackageInstallRequest(BaseModel):
    package_name: str


class PackageInstallResponse(BaseModel):
    message: str
    package_name: str
    status: str


# Global flag to track installation status
_installation_in_progress = False
_last_installation_result: dict | None = None


async def _restart_application() -> None:
    """Restart the application after a short delay."""
    try:
        # Wait 2 seconds to allow HTTP response to be sent
        await asyncio.sleep(2)
        logger.info("Initiating application restart...")

        # Strategy 1: Try to trigger uvicorn reload by touching a Python file
        try:
            from pathlib import Path

            # Touch the main.py file to trigger uvicorn reload
            main_file = Path(__file__).parent.parent.parent / "main.py"
            if main_file.exists():
                logger.info("Triggering uvicorn reload by touching main.py...")
                # Update the modification time to trigger reload
                main_file.touch()
                return
        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.warning(f"Failed to trigger uvicorn reload: {e}")

        # Strategy 1.5: Try touching __init__.py in the langflow package
        try:
            from pathlib import Path

            init_file = Path(__file__).parent.parent.parent / "__init__.py"
            if init_file.exists():
                logger.info("Triggering uvicorn reload by touching __init__.py...")
                init_file.touch()
                return
        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.warning(f"Failed to trigger uvicorn reload via __init__.py: {e}")

        # Strategy 2: Send SIGHUP to current process to trigger graceful restart
        try:
            import signal

            logger.info("Sending SIGHUP signal for graceful restart...")
            os.kill(os.getpid(), signal.SIGHUP)
            await asyncio.sleep(1)  # Give it a moment
        except (OSError, ProcessLookupError) as e:
            logger.warning(f"Failed to send SIGHUP: {e}")

        # Strategy 3: Force exit as last resort
        logger.info("Force exiting application to trigger restart...")
        os._exit(0)

    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to restart application: {e}")
        # Emergency fallback
        os._exit(1)


async def install_package_background(package_name: str) -> None:
    """Background task to install package using uv."""
    global _installation_in_progress, _last_installation_result  # noqa: PLW0603

    try:
        _installation_in_progress = True
        _last_installation_result = None

        logger.info(f"Starting installation of package: {package_name}")

        # Use uv to install the package in the current environment
        # Get the project root directory (6 levels up from this file)
        project_root = Path(__file__).parent.parent.parent.parent.parent.parent

        process = await asyncio.create_subprocess_exec(
            "uv",
            "add",
            package_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"Successfully installed package: {package_name}")
            _last_installation_result = {
                "status": "success",
                "package_name": package_name,
                "message": f"Package '{package_name}' installed successfully",
            }

            # Restart the application after successful installation
            logger.info("Restarting application after package installation...")
            # Use asyncio to schedule the restart after a short delay
            # This allows the HTTP response to be sent before the restart
            restart_task = asyncio.create_task(_restart_application())
            # Store reference to prevent garbage collection
            restart_task.add_done_callback(lambda _: None)

        else:
            error_message = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Failed to install package {package_name}: {error_message}")
            _last_installation_result = {
                "status": "error",
                "package_name": package_name,
                "message": f"Failed to install package '{package_name}': {error_message}",
            }

            # Restart the application even after failed installation to reset state
            logger.info("Restarting application after failed package installation to reset state...")
            # Use asyncio to schedule the restart after a short delay
            # This allows the HTTP response to be sent before the restart
            restart_task = asyncio.create_task(_restart_application())
            # Store reference to prevent garbage collection
            restart_task.add_done_callback(lambda _: None)

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error installing package {package_name}")
        _last_installation_result = {
            "status": "error",
            "package_name": package_name,
            "message": f"Error installing package '{package_name}': {e!s}",
        }

        # Restart the application even after exception to reset state
        logger.info("Restarting application after package installation exception to reset state...")
        # Use asyncio to schedule the restart after a short delay
        # This allows the HTTP response to be sent before the restart
        restart_task = asyncio.create_task(_restart_application())
        # Store reference to prevent garbage collection
        restart_task.add_done_callback(lambda _: None)
    finally:
        _installation_in_progress = False


@router.post("/install", response_model=PackageInstallResponse, status_code=202)
async def install_package(
    *,
    package_request: PackageInstallRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,  # noqa: ARG001
):
    """Install a Python package using uv."""
    global _installation_in_progress  # noqa: PLW0602

    if _installation_in_progress:
        raise HTTPException(status_code=409, detail="Package installation already in progress")

    package_name = package_request.package_name.strip()
    if not package_name:
        raise HTTPException(status_code=400, detail="Package name cannot be empty")

    # Basic validation for package name (prevent command injection)
    if any(char in package_name for char in [";", "&", "|", "`", "$", "(", ")", "<", ">"]):
        raise HTTPException(status_code=400, detail="Invalid package name")

    # Start background installation
    background_tasks.add_task(install_package_background, package_name)

    return PackageInstallResponse(
        message=f"Package installation started for '{package_name}'", package_name=package_name, status="started"
    )


@router.get("/install/status")
async def get_installation_status(current_user: CurrentActiveUser):  # noqa: ARG001
    """Get the current installation status."""
    global _installation_in_progress, _last_installation_result  # noqa: PLW0602

    return {
        "installation_in_progress": _installation_in_progress,
        "last_result": _last_installation_result,
    }


@router.delete("/install/status")
async def clear_installation_status(current_user: CurrentActiveUser):  # noqa: ARG001
    """Clear the installation status (useful for clearing error states)."""
    global _installation_in_progress, _last_installation_result  # noqa: PLW0603

    _installation_in_progress = False
    _last_installation_result = None

    return {"message": "Installation status cleared"}
