import asyncio
import platform
import re
import shutil
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.package_installation.model import (
    InstallationStatus,
    PackageInstallation,
    PackageInstallationCreate,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/packages", tags=["Packages"])


class PackageInstallRequest(BaseModel):
    package_name: str  # Supports version specifications like 'pandas==2.3.1' or 'requests>=2.25.0'


class PackageInstallResponse(BaseModel):
    message: str
    package_name: str
    status: str


# No more global variables - we use database for multi-worker compatibility


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or setup.py."""
    current_path = Path(__file__).resolve()

    # Start from current file and go up the directory tree
    for parent in [current_path, *list(current_path.parents)]:
        # Look for common project root indicators
        if any((parent / marker).exists() for marker in ["pyproject.toml", "setup.py", "requirements.txt", ".git"]):
            logger.info(f"Found project root at: {parent}")
            return parent

    # Fallback to current working directory
    logger.warning("Could not find project root, using current working directory")
    return Path.cwd()


def _find_uv_executable() -> str:
    """Find UV executable with Windows compatibility."""
    # Use existing shutil.which - it handles .exe on Windows automatically
    uv_path = shutil.which("uv")
    if uv_path:
        logger.info(f"Found UV executable at: {uv_path}")
        return uv_path

    # Windows fallback - try explicit .exe
    if platform.system() == "Windows":
        uv_exe = shutil.which("uv.exe")
        if uv_exe:
            logger.info(f"Found UV executable at: {uv_exe}")
            return uv_exe

    msg = "UV package manager not found in PATH"
    raise RuntimeError(msg)


def _restart_in_thread() -> None:
    """Restart the application in a separate thread to avoid blocking HTTP connections."""
    import time

    # Give frontend time to poll the completion status
    time.sleep(3)

    # Check if we're in development mode (uvicorn with --reload)
    is_development = any("--reload" in arg for arg in sys.argv) or "watchfiles" in sys.modules

    try:
        logger.info("Initiating application restart...")

        if is_development:
            # Development mode: uvicorn --reload should handle restarts automatically
            # when .venv files change during package installation
            logger.info("Development environment detected.")
            logger.info("Package installation completed. Uvicorn auto-reload should handle restart.")

            # Only touch files as a fallback if needed
            # Wait a bit to see if uvicorn already started reloading
            time.sleep(2)

            try:
                project_root = _find_project_root()
                reload_files = [
                    project_root / "langflow" / "main.py",
                    project_root / "langflow" / "__init__.py",
                ]

                # Only touch files if we're still running (no reload happened)
                for file_path in reload_files:
                    try:
                        if file_path.exists():
                            logger.info(f"Fallback: Triggering uvicorn reload by touching {file_path}")
                            file_path.touch()
                            return
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Failed to touch {file_path}: {e}")
                        continue

            except (OSError, RuntimeError, AttributeError, ImportError) as e:
                logger.info(f"Could not trigger fallback restart: {e}")
                logger.info("Package installation completed. Manual restart may be needed.")
                return
        else:
            # Production/server mode: just log and let process manager handle it
            logger.info("Production environment detected. Package installed successfully.")
            logger.info("Please restart the application manually or let your process manager handle it.")
            return

        # If we get here, restart failed
        logger.warning("Could not restart application automatically. Package installation completed successfully.")
        logger.info("Manual restart recommended to use the new package.")

    except (OSError, RuntimeError, AttributeError, ImportError, PermissionError) as e:
        logger.error(f"Restart attempt failed: {e}")
        logger.info("Package installation completed successfully. Manual restart may be required.")


async def _restart_application_with_delay() -> None:
    """Restart the application with delay for frontend polling."""
    # Start restart in a separate thread to completely detach from HTTP request
    thread = threading.Thread(target=_restart_in_thread, daemon=True)
    thread.start()


def _is_valid_windows_package_name(package_name: str) -> bool:
    """Validate package name for Windows forbidden characters."""
    forbidden_chars = ["<", ">", ":", '"', "|", "?", "*"]
    return not any(char in package_name for char in forbidden_chars)


def _validate_package_specification(package_spec: str) -> bool:
    """Validate package specification with version support (e.g., 'pandas==2.3.1', 'requests>=2.25.0')."""
    if not package_spec or not package_spec.strip():
        return False

    if not _PACKAGE_SPEC_PATTERN.match(package_spec):
        return False

    # Use set intersection for fast forbidden character check
    return not _FORBIDDEN_CHARS.intersection(package_spec)


def _validate_package_name(package_name: str) -> bool:
    """Legacy validation function - redirects to new specification validator."""
    return _validate_package_specification(package_name)


async def install_package_background(installation_id: UUID) -> None:
    """Background task to install package using uv with cross-platform support."""
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        try:
            # Get installation record
            installation = await session.get(PackageInstallation, installation_id)
            if not installation:
                logger.error(f"Installation record not found: {installation_id}")
                return

            # Update status to in progress
            installation.status = InstallationStatus.IN_PROGRESS
            installation.updated_at = datetime.now(timezone.utc)
            session.add(installation)
            await session.commit()

            package_name = installation.package_name

            # Find UV executable and project root
            uv_executable = _find_uv_executable()
            project_root = _find_project_root()

            logger.info(f"Starting installation of package: {package_name}")
            logger.info(f"Found UV executable at: {uv_executable}")
            logger.info(f"Found project root at: {project_root}")

            # Enhanced validation for package name with Windows-specific forbidden characters
            if platform.system() == "Windows" and not _is_valid_windows_package_name(package_name):
                forbidden_chars = ["<", ">", ":", '"', "|", "?", "*"]
                error_message = (
                    f"Invalid package name '{package_name}' for Windows. "
                    f"Contains forbidden characters: {forbidden_chars}"
                )
                logger.error(error_message)
                installation.status = InstallationStatus.FAILED
                installation.message = error_message
                installation.updated_at = datetime.now(timezone.utc)
                session.add(installation)
                await session.commit()
                return

            # Install the package using UV
            command = [str(uv_executable), "add", package_name]

            logger.info(f"Executing command: {' '.join(command)} in {project_root}")

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # Handle encoding properly for Windows - FIXED
            stdout_text = ""
            stderr_text = ""

            if platform.system() == "Windows":
                # Try multiple encodings for Windows
                for encoding in ["utf-8", "cp1252", "latin1"]:
                    try:
                        stdout_text = stdout.decode(encoding) if stdout else ""
                        stderr_text = stderr.decode(encoding) if stderr else ""
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # Fallback with error replacement
                    stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
                    stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
            else:
                stdout_text = stdout.decode("utf-8") if stdout else ""
                stderr_text = stderr.decode("utf-8") if stderr else ""

            # Enhanced error detection for Windows - FIXED
            installation_failed = False

            # Check return code first
            if process.returncode != 0:
                installation_failed = True
                logger.error(f"UV command failed with return code: {process.returncode}")

            # Additional Windows-specific error detection
            if platform.system() == "Windows":
                # Check for specific error patterns in stderr and stdout
                error_patterns = [
                    "No solution found when resolving dependencies",
                    "we can conclude that all versions of",
                    "cannot be used",
                    "requirements are unsatisfiable",
                    "Ã—",  # This is the x character in Windows encoding
                    "error:",
                    "failed",
                    "Error:",
                    "ERROR:",
                ]

                combined_output = f"{stdout_text} {stderr_text}".lower()
                for pattern in error_patterns:
                    if pattern.lower() in combined_output:
                        installation_failed = True
                        logger.error(f"Detected error pattern '{pattern}' in output")
                        break

            if not installation_failed:
                logger.info(f"Successfully installed package: {package_name}")
                installation.status = InstallationStatus.COMPLETED
                installation.message = f"Package '{package_name}' installed successfully"
            else:
                # Combine stdout and stderr for complete error message
                error_message = stderr_text or stdout_text or "Unknown error"

                # Clean up the error message for Windows
                if platform.system() == "Windows":
                    # Remove problematic unicode characters and clean up the message
                    import re

                    # Remove box drawing and other problematic characters
                    error_message = re.sub(r"[^\x00-\x7F]+", " ", error_message)
                    # Clean up multiple spaces
                    error_message = re.sub(r"\s+", " ", error_message).strip()

                logger.error(f"Failed to install package {package_name}: {error_message}")
                installation.status = InstallationStatus.FAILED
                installation.message = f"Failed to install package '{package_name}': {error_message}"

            # Update installation record
            installation.updated_at = datetime.now(timezone.utc)
            session.add(installation)
            await session.commit()

            # Only restart if installation was successful
            if not installation_failed:
                # Give frontend time to poll the completion status before restart
                await asyncio.sleep(1)

                # Check if uvicorn auto-reload is likely to handle restart automatically
                # This happens when .venv files change during package installation
                is_development = any("--reload" in arg for arg in sys.argv) or "watchfiles" in sys.modules

                if is_development:
                    logger.info("Development mode detected. Package installation completed successfully.")
                    logger.info("Uvicorn should automatically restart due to .venv file changes.")
                    # Don't schedule additional restart to avoid conflicts
                else:
                    # Schedule restart with delay only in production mode
                    logger.info("Restarting application after successful package installation...")
                    restart_task = asyncio.create_task(_restart_application_with_delay())
                    restart_task.add_done_callback(lambda _: None)
            else:
                logger.info("Package installation failed. Skipping application restart.")

        except (OSError, RuntimeError) as e:
            logger.exception("Error installing package")
            # Update installation record with error
            installation = await session.get(PackageInstallation, installation_id)
            if installation:
                installation.status = InstallationStatus.FAILED
                installation.message = f"Error installing package: {e!s}"
                installation.updated_at = datetime.now(timezone.utc)
                session.add(installation)
                await session.commit()

            # Give frontend time to poll the failure status before restart
            await asyncio.sleep(1)

            # Check if uvicorn auto-reload is likely to handle restart automatically
            is_development = any("--reload" in arg for arg in sys.argv) or "watchfiles" in sys.modules

            if is_development:
                logger.info("Development mode detected. Package installation failed.")
                logger.info("Uvicorn should automatically restart due to any .venv file changes.")
                # Don't schedule additional restart to avoid conflicts
            else:
                # Schedule restart even after exception in production mode
                logger.info("Restarting application after package installation exception to reset state...")
                restart_task = asyncio.create_task(_restart_application_with_delay())
                restart_task.add_done_callback(lambda _: None)


@router.post("/install", response_model=PackageInstallResponse, status_code=202)
async def install_package(
    *,
    package_request: PackageInstallRequest,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Install a Python package using uv with cross-platform support.

    Supports version specifications:
    - pandas (latest version)
    - pandas==2.3.1 (exact version)
    - requests>=2.25.0 (minimum version)
    - numpy<=1.24.0 (maximum version)
    - scipy!=1.10.0 (exclude specific version)
    """
    if not get_settings_service().settings.package_manager:
        raise HTTPException(status_code=403, detail="Package manager is disabled")

    package_name = package_request.package_name.strip()

    # Validate package name
    if not _validate_package_name(package_name):
        raise HTTPException(status_code=400, detail="Invalid package name")

    # Check if there's already an installation in progress for this user
    result = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .where(PackageInstallation.status == InstallationStatus.IN_PROGRESS)
    )
    if result.first():
        raise HTTPException(status_code=409, detail="Package installation already in progress")

    # Create installation record
    installation_data = PackageInstallationCreate(
        package_name=package_name,
        user_id=current_user.id,
    )
    installation = PackageInstallation.model_validate(installation_data.model_dump())
    session.add(installation)
    await session.commit()
    await session.refresh(installation)

    # Start background installation
    background_tasks.add_task(install_package_background, installation.id)

    return PackageInstallResponse(
        message=f"Package installation started for '{package_name}'", package_name=package_name, status="started"
    )


@router.get("/install/status")
async def get_installation_status(
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get the current installation status."""
    if not get_settings_service().settings.package_manager:
        raise HTTPException(status_code=403, detail="Package manager is disabled")

    # Get latest installation status for user
    from sqlalchemy import desc

    _FORBIDDEN_CHARS.update({"%", "^", '"', "'"})

    result = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .order_by(desc(PackageInstallation.created_at))
    )
    latest_installation = result.first()

    installation_in_progress = (
        latest_installation.status == InstallationStatus.IN_PROGRESS if latest_installation else False
    )

    last_result = None
    if latest_installation and latest_installation.status in [InstallationStatus.COMPLETED, InstallationStatus.FAILED]:
        last_result = {
            "id": str(latest_installation.id),
            "package_name": latest_installation.package_name,
            "status": latest_installation.status.value,
            "message": latest_installation.message,
            "created_at": latest_installation.created_at.isoformat() if latest_installation.created_at else None,
            "updated_at": latest_installation.updated_at.isoformat() if latest_installation.updated_at else None,
            "user_id": str(latest_installation.user_id),
        }

    return {
        "installation_in_progress": installation_in_progress,
        "last_result": last_result,
    }


@router.delete("/install/status")
async def clear_installation_status(
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Clear the installation status."""
    if not get_settings_service().settings.package_manager:
        raise HTTPException(status_code=403, detail="Package manager is disabled")

    # Delete completed/failed installations for this user
    completed_installations = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .where(PackageInstallation.status == InstallationStatus.COMPLETED)
    )
    failed_installations = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .where(PackageInstallation.status == InstallationStatus.FAILED)
    )

    installations_to_delete = list(completed_installations.all()) + list(failed_installations.all())

    for installation in installations_to_delete:
        await session.delete(installation)

    await session.commit()

    return {"message": "Installation status cleared"}


_PACKAGE_SPEC_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?(([><=!~]+|===)[0-9]+(\.[0-9]+)*([a-zA-Z0-9._-]*)?)?$"
)

_FORBIDDEN_CHARS = {";", "&", "|", "`", "$", "(", ")"}
