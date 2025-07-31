import asyncio
import platform
import re
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


class PackageUninstallRequest(BaseModel):
    package_name: str


class PackageUninstallResponse(BaseModel):
    message: str
    package_name: str
    status: str


class InstalledPackage(BaseModel):
    name: str
    version: str


# No more global variables - we use database for multi-worker compatibility


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or setup.py."""
    current_path = Path(__file__).resolve()
    project_markers = {"pyproject.toml", "setup.py", "requirements.txt", ".git"}

    # Check each parent including self; stop at first found
    for parent in (current_path,) + tuple(current_path.parents):
        if any((parent / marker).exists() for marker in project_markers):
            logger.info(f"Found project root at: {parent}")
            return parent

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


def _get_core_dependencies() -> set[str]:
    """Get the list of core dependencies from pyproject.toml to prevent accidental removal."""
    try:
        import tomllib

        current_path = Path(__file__).resolve()
        pyproject_path = None
        pyproject_data = None
        # Only check pyproject.toml in each parent path, not re-parsing multiple times
        for parent in (current_path,) + tuple(current_path.parents):
            candidate = parent / "pyproject.toml"
            if candidate.exists():
                try:
                    with candidate.open("rb") as f:
                        data = tomllib.load(f)
                    project = data.get("project")
                    # Check for main langflow project name
                    if project and project.get("name") == "langflow":
                        logger.info(f"Found main langflow pyproject.toml at: {candidate}")
                        pyproject_path = candidate
                        pyproject_data = data
                        break
                except (OSError, tomllib.TOMLDecodeError):
                    logger.debug(f"Could not read {candidate}, trying next")
        else:
            # Fallback if not found
            pyproject_path = _find_project_root() / "pyproject.toml"
            if not pyproject_path.exists():
                logger.warning(f"pyproject.toml not found at {pyproject_path}")
                return set()
            with pyproject_path.open("rb") as f:
                pyproject_data = tomllib.load(f)

        # Read dependencies from pyproject.toml dict (already loaded)
        dependencies = []
        if pyproject_data is not None:
            project = pyproject_data.get("project")
            if project is not None:
                dependencies = project.get("dependencies", [])

        # Use precompiled regex to extract base names efficiently
        core_packages = set(
            _DEP_BASE_NAME_RE.split(dep)[0].strip().lower() for dep in dependencies if dep and dep.strip()
        )

        logger.info(f"Found {len(core_packages)} core dependencies in pyproject.toml")
        return core_packages  # noqa: TRY300

    except (OSError, ImportError, Exception) as e:  # Also catch ImportError for tomllib
        logger.error(f"Failed to read core dependencies from pyproject.toml: {e}")
        # Return minimal fallback critical packages to prevent catastrophic failures
        return {
            "requests",
            "openai",
            "langchain",
            "langchain-core",
            "langchain-openai",
            "fastapi",
            "uvicorn",
            "sqlmodel",
            "pydantic",
            "langflow-base",
        }


def _is_core_dependency(package_name: str) -> bool:
    """Check if a package is a core dependency that should not be uninstalled."""
    core_deps = _get_core_dependencies()
    return package_name.lower() in core_deps


async def _get_system_dependencies() -> set[str]:
    """Get all packages currently installed in the system as dependencies."""
    try:
        uv_executable = _find_uv_executable()
        project_root = _find_project_root()

        # Get dependency tree information
        command = [str(uv_executable), "pip", "list", "--format=json"]

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            import json

            packages_data = json.loads(stdout.decode("utf-8"))
            return {pkg["name"].lower() for pkg in packages_data}

    except (OSError, json.JSONDecodeError, subprocess.SubprocessError) as e:
        logger.error(f"Failed to get system dependencies: {e}")
        return set()


def _is_dependency_of_others(package_name: str) -> bool:
    """Check if a package is a dependency of other packages."""
    # For now, we'll use the core dependency check as a proxy
    # A more sophisticated approach would parse dependency trees
    return _is_core_dependency(package_name)


async def uninstall_package_background(installation_id: UUID) -> None:
    """Background task to uninstall package using uv with cross-platform support."""
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

            logger.info(f"Starting uninstallation of package: {package_name}")
            logger.info(f"Found UV executable at: {uv_executable}")
            logger.info(f"Found project root at: {project_root}")

            # Use uv pip uninstall instead of uv remove to avoid dependency resolution issues
            # This only removes the package from the virtual environment without modifying project dependencies
            # which prevents accidentally removing dependencies needed by the main project
            command = [str(uv_executable), "pip", "uninstall", package_name]

            logger.info(f"Executing command: {' '.join(command)} in {project_root}")

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # Handle encoding properly for Windows
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

            # Enhanced error detection
            uninstallation_failed = False

            # Check return code first
            if process.returncode != 0:
                uninstallation_failed = True
                logger.error(f"UV command failed with return code: {process.returncode}")

            # Check for error patterns in output
            # Use more precise error detection to avoid false positives from warnings
            error_patterns = [
                " error:",  # Space before error to avoid matching "warning"
                "error ",  # Space after error
                "\nerror:",  # Error at start of line
                "failed to",
                "failed:",
                " failed ",
                "Error:",
                "ERROR:",
                "not found",
                "No such package",
                "package not found",
                "could not find",
                "uninstallation failed",
            ]

            combined_output = f"{stdout_text} {stderr_text}".lower()
            for pattern in error_patterns:
                if pattern.lower() in combined_output:
                    uninstallation_failed = True
                    logger.error(f"Detected error pattern '{pattern}' in output")
                    break

            logger.info(f"Uninstallation failed status for {package_name}: {uninstallation_failed}")

            if not uninstallation_failed:
                logger.info(f"Successfully uninstalled package: {package_name}")
                installation.status = InstallationStatus.UNINSTALLED
                installation.message = f"Package '{package_name}' uninstalled successfully"
                logger.info(f"Setting installation status to UNINSTALLED for {package_name}")

                # Mark any previously installed packages with the same base name as uninstalled
                # This handles cases where the same package was installed multiple times with different versions
                import re

                base_package_name = re.split(r"[<>=!~]", package_name)[0].strip()

                previous_installations = await session.exec(
                    select(PackageInstallation)
                    .where(PackageInstallation.user_id == installation.user_id)
                    .where(PackageInstallation.status == InstallationStatus.COMPLETED)
                )

                for prev_installation in previous_installations:
                    if prev_installation.id != installation.id:  # Don't update the current uninstall record
                        prev_base_name = re.split(r"[<>=!~]", prev_installation.package_name)[0].strip()
                        if prev_base_name.lower() == base_package_name.lower():
                            prev_installation.status = InstallationStatus.UNINSTALLED
                            prev_installation.updated_at = datetime.now(timezone.utc)
                            session.add(prev_installation)
                            logger.info(f"Marked previous installation {prev_installation.id} as UNINSTALLED")
            else:
                # Combine stdout and stderr for complete error message
                error_message = stderr_text or stdout_text or "Unknown error"

                # Clean up the error message for Windows
                if platform.system() == "Windows":
                    import re

                    # Remove problematic unicode characters and clean up the message
                    error_message = re.sub(r"[^\x00-\x7F]+", " ", error_message)
                    # Clean up multiple spaces
                    error_message = re.sub(r"\s+", " ", error_message).strip()

                logger.error(f"Failed to uninstall package {package_name}: {error_message}")
                installation.status = InstallationStatus.FAILED
                installation.message = f"Failed to uninstall package '{package_name}': {error_message}"
                logger.info(f"Setting installation status to FAILED for {package_name}")

            # Update installation record
            installation.updated_at = datetime.now(timezone.utc)
            session.add(installation)
            await session.commit()
            logger.info(f"Database updated - Final status for {package_name}: {installation.status}")

        except (OSError, RuntimeError, subprocess.CalledProcessError, asyncio.TimeoutError) as e:
            logger.exception(f"Unexpected error during package uninstallation: {e}")
            # Ensure status is always updated even for unexpected errors
            if installation:
                try:
                    installation.status = InstallationStatus.FAILED
                    installation.message = f"Unexpected error during uninstallation: {e!s}"
                    installation.updated_at = datetime.now(timezone.utc)
                    session.add(installation)
                    await session.commit()
                except (SQLAlchemyError, OSError) as commit_error:
                    logger.error(f"Failed to update installation status after error: {commit_error}")
            logger.info("Package uninstallation failed due to unexpected error.")


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
            # Use more precise error detection to avoid false positives from warnings
            error_patterns = [
                "No solution found when resolving dependencies",
                "we can conclude that all versions of",
                "cannot be used",
                "requirements are unsatisfiable",
                " error:",  # Space before error to avoid matching "warning"
                "error ",  # Space after error
                "\nerror:",  # Error at start of line
                "failed to",
                "failed:",
                " failed ",
                "Error:",
                "ERROR:",
                "installation failed",
                "package not found",
                "could not find",
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

    # Extract base package name for validation
    base_package_name = (
        package_name.split("==")[0].split(">=")[0].split("<=")[0].split(">")[0].split("<")[0].split("!=")[0].strip()
    )

    # Check if it's a core dependency (prevent installing core dependencies separately)
    if _is_core_dependency(base_package_name):
        raise HTTPException(
            status_code=409,
            detail=f"Package '{base_package_name}' is already installed as a core dependency. "
            f"Installing it separately could cause conflicts when uninstalling.",
        )

    # Check if user has already installed this package through the package manager
    existing_installations = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .where(PackageInstallation.status == InstallationStatus.COMPLETED)
    )

    import re

    for installation in existing_installations:
        existing_base_name = re.split(r"[<>=!~]", installation.package_name)[0].strip().lower()
        if existing_base_name == base_package_name.lower():
            raise HTTPException(
                status_code=409,
                detail=f"Package '{base_package_name}' is already installed through the package manager.",
            )

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


@router.post("/uninstall", response_model=PackageUninstallResponse, status_code=202)
async def uninstall_package(
    *,
    package_request: PackageUninstallRequest,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Uninstall a Python package using uv."""
    if not get_settings_service().settings.package_manager:
        raise HTTPException(status_code=403, detail="Package manager is disabled")

    package_name = package_request.package_name.strip()

    # Basic validation for package name (no version specifiers for uninstall)
    if not package_name or not package_name.replace("-", "").replace("_", "").replace(".", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid package name")

    # Prevent uninstalling core dependencies
    if _is_core_dependency(package_name):
        raise HTTPException(
            status_code=403,
            detail=f"Cannot uninstall '{package_name}' as it is a core dependency required by Langflow. "
            f"Removing this package could break the application.",
        )

    # Check if the package was actually installed by this user (look at currently installed packages)
    # Use the same logic as get_installed_packages to find currently installed packages
    all_installations = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == current_user.id)
        .where(PackageInstallation.status.in_([InstallationStatus.COMPLETED, InstallationStatus.UNINSTALLED]))
    )

    # Group by base package name to find currently installed packages
    import re
    from collections import defaultdict

    package_status = defaultdict(list)
    for installation in all_installations:
        base_name = re.split(r"[<>=!~]", installation.package_name)[0].strip().lower()
        package_status[base_name].append(installation)

    # Check if the requested package is currently installed (not uninstalled)
    currently_installed_packages = []
    for base_name, installations in package_status.items():
        # Sort by created_at to get chronological order
        installations.sort(key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc))

        # Check the latest status for this package
        latest_installation = installations[-1]
        if latest_installation.status == InstallationStatus.COMPLETED:
            currently_installed_packages.append(base_name)

    if package_name.lower() not in currently_installed_packages:
        # If package is not in our database, check if it's actually installed in the system
        # This handles cases where packages were installed before our tracking system
        try:
            uv_executable = _find_uv_executable()
            project_root = _find_project_root()

            # Check if package is actually installed
            command = [str(uv_executable), "pip", "list", "--format=json"]
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                import json

                packages_data = json.loads(stdout.decode("utf-8"))
                system_packages = [pkg["name"].lower() for pkg in packages_data]

                if package_name.lower() in system_packages:
                    # Package exists in system but not tracked - allow uninstall but warn
                    logger.warning(f"Package '{package_name}' found in system but not in database - allowing uninstall")
                else:
                    raise HTTPException(
                        status_code=404, detail=f"Package '{package_name}' is not installed in the system"
                    )
            else:
                raise HTTPException(
                    status_code=404, detail=f"Package '{package_name}' was not installed through this package manager"
                )
        except (OSError, json.JSONDecodeError, subprocess.SubprocessError) as e:
            logger.error(f"Failed to check system packages: {e}")
            raise HTTPException(
                status_code=404, detail=f"Package '{package_name}' was not installed through this package manager"
            ) from e

    # Check if there's already an installation/uninstallation in progress for this user
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
        stuck_installation.message = "Operation timed out and was cleaned up"
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
        raise HTTPException(status_code=409, detail="Package operation already in progress")

    # Create uninstallation record
    installation_data = PackageInstallationCreate(
        package_name=package_name,
        user_id=current_user.id,
    )
    installation = PackageInstallation.model_validate(installation_data.model_dump())
    session.add(installation)
    await session.commit()
    await session.refresh(installation)

    # Start background uninstallation
    background_tasks.add_task(uninstall_package_background, installation.id)

    return PackageUninstallResponse(
        message=f"Package uninstallation started for '{package_name}'", package_name=package_name, status="started"
    )


@router.get("/installed", response_model=list[InstalledPackage])
async def get_installed_packages(
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get list of packages installed through the package manager by the current user."""
    if not get_settings_service().settings.package_manager:
        raise HTTPException(status_code=403, detail="Package manager is disabled")

    try:
        # Get successfully installed packages for the current user from database
        # We need to find packages that are COMPLETED (installed) but not UNINSTALLED
        all_installations = await session.exec(
            select(PackageInstallation)
            .where(PackageInstallation.user_id == current_user.id)
            .where(PackageInstallation.status.in_([InstallationStatus.COMPLETED, InstallationStatus.UNINSTALLED]))
        )

        # Group by base package name to find currently installed packages
        import re
        from collections import defaultdict

        package_status = defaultdict(list)
        for installation in all_installations:
            base_name = re.split(r"[<>=!~]", installation.package_name)[0].strip().lower()
            package_status[base_name].append(installation)

        # Filter to only currently installed packages (COMPLETED and not later UNINSTALLED)
        user_installed_packages = []
        for installations in package_status.values():
            # Sort by created_at to get chronological order
            installations.sort(key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc))

            # Check the latest status for this package
            latest_installation = installations[-1]
            if latest_installation.status == InstallationStatus.COMPLETED:
                user_installed_packages.append(latest_installation)

        if not user_installed_packages:
            return []

        # Get the actual installed packages from the system to check versions
        uv_executable = _find_uv_executable()
        project_root = _find_project_root()

        logger.info(f"Getting installed packages list using {uv_executable} in {project_root}")

        # Get installed packages using UV
        command = [str(uv_executable), "pip", "list", "--format=json"]

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode("utf-8") if stderr else "Unknown error"
            logger.error(f"Failed to get installed packages: {error_message}")
            # Still return user-installed packages even if we can't get versions
            import re

            return [
                InstalledPackage(name=re.split(r"[<>=!~]", pkg.package_name)[0].strip(), version="unknown")
                for pkg in user_installed_packages
            ]

        # Parse JSON output and match with user-installed packages
        import json

        try:
            all_packages_data = json.loads(stdout.decode("utf-8"))
            system_packages = {pkg["name"].lower(): pkg["version"] for pkg in all_packages_data}

            # Only return packages that were installed by the user AND are still installed in the system
            user_packages = []
            for installation in user_installed_packages:
                # Extract base package name (remove version specifiers)
                import re

                base_package_name = re.split(r"[<>=!~]", installation.package_name)[0].strip()
                package_name_lower = base_package_name.lower()

                if package_name_lower in system_packages:
                    user_packages.append(
                        InstalledPackage(name=base_package_name, version=system_packages[package_name_lower])
                    )
                else:
                    # Package was installed by user but no longer in system
                    # This could happen if it was manually uninstalled outside our system
                    logger.warning(f"Package {base_package_name} was installed by user but not found in system")

            return user_packages  # noqa: TRY300

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse packages JSON: {e}")
            # Fallback: return user-installed packages without version info
            import re

            return [
                InstalledPackage(name=re.split(r"[<>=!~]", pkg.package_name)[0].strip(), version="unknown")
                for pkg in user_installed_packages
            ]

    except (OSError, RuntimeError) as e:
        logger.error(f"Error getting installed packages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get installed packages") from e


_DEP_BASE_NAME_RE = re.compile(r"[<>=!~\[\];]")
