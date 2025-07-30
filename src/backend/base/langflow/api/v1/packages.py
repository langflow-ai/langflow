import asyncio
import platform
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
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


def _is_valid_windows_package_name(package_name: str) -> bool:
    """Validate package name for Windows forbidden characters."""
    forbidden_chars = ["<", ">", ":", '"', "|", "?", "*"]
    return not any(char in package_name for char in forbidden_chars)


def _validate_package_specification(package_spec: str) -> bool:
    """Validate package specification with version support (e.g., 'pandas==2.3.1', 'requests>=2.25.0')."""
    import re

    if not package_spec or not package_spec.strip():
        return False

    # Pattern to match: package_name[version_operators]
    # Allows: letters, numbers, hyphens, underscores, dots for package names
    # Allows: ==, >=, <=, >, <, !=, ~=, === and version numbers
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?(([><=!~]+|===)[0-9]+(\.[0-9]+)*([a-zA-Z0-9._-]*)?)?$"

    if not re.match(pattern, package_spec):
        return False

    # Security checks: forbidden command injection characters
    forbidden_chars = [";", "&", "|", "`", "$", "(", ")"]

    # Add Windows-specific forbidden characters
    if platform.system() == "Windows":
        forbidden_chars.extend(["%", "^", '"', "'"])

    return not any(char in package_spec for char in forbidden_chars)


def _validate_package_name(package_name: str) -> bool:
    """Legacy validation function - redirects to new specification validator."""
    return _validate_package_specification(package_name)


async def install_package_background(installation_id: UUID) -> None:
    """Background task to install package using uv with cross-platform support."""
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        installation = None
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

            # Enhanced error detection - FIXED
            installation_failed = False

            # Check return code first
            if process.returncode != 0:
                installation_failed = True
                logger.error(f"UV command failed with return code: {process.returncode}")

            # Check for error patterns in output (all platforms)
            error_patterns = [
                "No solution found when resolving dependencies",
                "we can conclude that all versions of",
                "cannot be used",
                "requirements are unsatisfiable",
                "error:",
                "failed",
                "Error:",
                "ERROR:",
            ]

            # Add Windows-specific patterns
            if platform.system() == "Windows":
                error_patterns.append("Ã—")  # This is the x character in Windows encoding

            combined_output = f"{stdout_text} {stderr_text}".lower()
            for pattern in error_patterns:
                if pattern.lower() in combined_output:
                    installation_failed = True
                    logger.error(f"Detected error pattern '{pattern}' in output")
                    break

            logger.info(f"Installation failed status for {package_name}: {installation_failed}")

            if not installation_failed:
                logger.info(f"Successfully installed package: {package_name}")
                installation.status = InstallationStatus.COMPLETED
                installation.message = f"Package '{package_name}' installed successfully"
                logger.info(f"Setting installation status to COMPLETED for {package_name}")
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
                logger.info(f"Setting installation status to FAILED for {package_name}")

            # Update installation record
            installation.updated_at = datetime.now(timezone.utc)
            session.add(installation)
            await session.commit()
            logger.info(f"Database updated - Final status for {package_name}: {installation.status}")

            # Package installation completed - no restart needed
            if not installation_failed:
                logger.info("Package installation completed successfully. Package is now available for import.")
            else:
                logger.info("Package installation failed.")

        except (OSError, RuntimeError, subprocess.CalledProcessError, asyncio.TimeoutError) as e:
            logger.exception(f"Unexpected error during package installation: {e}")
            # Ensure status is always updated even for unexpected errors
            if installation:
                try:
                    installation.status = InstallationStatus.FAILED
                    installation.message = f"Unexpected error during installation: {e!s}"
                    installation.updated_at = datetime.now(timezone.utc)
                    session.add(installation)
                    await session.commit()
                except (SQLAlchemyError, OSError) as commit_error:
                    logger.error(f"Failed to update installation status after error: {commit_error}")
            logger.info("Package installation failed due to unexpected error.")


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
    # Also clean up any stuck installations (older than 10 minutes)

    stuck_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stuck_installations = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .where(PackageInstallation.status == InstallationStatus.IN_PROGRESS)
        .where(PackageInstallation.updated_at < stuck_cutoff)
    )

    # Clean up any stuck installations
    for stuck_installation in stuck_installations:
        logger.warning(f"Cleaning up stuck installation: {stuck_installation.id}")
        stuck_installation.status = InstallationStatus.FAILED
        stuck_installation.message = "Installation timed out and was cleaned up"
        stuck_installation.updated_at = datetime.now(timezone.utc)
        session.add(stuck_installation)

    # Now check for active installations
    active_result = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .where(PackageInstallation.status == InstallationStatus.IN_PROGRESS)
        .where(PackageInstallation.updated_at >= stuck_cutoff)
    )
    if active_result.first():
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
