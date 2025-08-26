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


class PackageRestoreRequest(BaseModel):
    confirm: bool = False


class PackageRestoreResponse(BaseModel):
    message: str
    status: str


class InstalledPackage(BaseModel):
    name: str
    version: str


# No more global variables - we use database for multi-worker compatibility


def _find_project_root() -> Path:
    """Find the main project root (not langflow-base) by looking for the main langflow pyproject.toml."""
    current_path = Path(__file__).resolve()

    # Start from current file and go up the directory tree to find main langflow project
    for parent in [current_path, *list(current_path.parents)]:
        pyproject_file = parent / "pyproject.toml"
        if pyproject_file.exists():
            try:
                import tomllib

                with pyproject_file.open("rb") as f:
                    pyproject_data = tomllib.load(f)
                project_name = pyproject_data.get("project", {}).get("name", "")

                # Look specifically for the main "langflow" project, not "langflow-base"
                if project_name == "langflow":
                    logger.info(f"Found main langflow project root at: {parent}")
                    return parent
            except (OSError, tomllib.TOMLDecodeError):
                logger.debug(f"Could not read pyproject.toml at {pyproject_file}")
                continue

        # Also check for .git as fallback
        if (parent / ".git").exists():
            logger.info(f"Found git root at: {parent}")
            return parent

    # Fallback to current working directory
    logger.warning("Could not find main project root, using current working directory")
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


def _find_python_executable(project_root: Path) -> str:
    """Find the Python executable in the virtual environment with cross-platform support."""
    if platform.system() == "Windows":
        # Windows: .venv/Scripts/python.exe
        python_path = project_root / ".venv" / "Scripts" / "python.exe"
        if python_path.exists():
            logger.info(f"Found Python executable at: {python_path}")
            return str(python_path)
        # Fallback to python without .exe extension
        python_path = project_root / ".venv" / "Scripts" / "python"
        if python_path.exists():
            logger.info(f"Found Python executable at: {python_path}")
            return str(python_path)
    else:
        # Unix-like systems (Linux, macOS): .venv/bin/python
        python_path = project_root / ".venv" / "bin" / "python"
        if python_path.exists():
            logger.info(f"Found Python executable at: {python_path}")
            return str(python_path)

    # If virtual environment Python not found, fall back to system Python
    # This should not happen in normal operation but provides a safety net
    logger.warning("Virtual environment Python not found, falling back to system Python")
    python_executable = shutil.which("python3") or shutil.which("python")
    if python_executable:
        logger.info(f"Using system Python executable: {python_executable}")
        return python_executable

    msg = "Python executable not found in virtual environment or system PATH"
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
    """Get the list of core dependencies from pyproject.toml files to prevent accidental removal."""
    try:
        import re
        from pathlib import Path

        import tomllib

        core_packages = set()

        # Check both main langflow and langflow-base dependencies
        pyproject_paths = []

        # Find the main project root
        current_path = Path(__file__).resolve()
        for parent in [current_path, *list(current_path.parents)]:
            main_pyproject = parent / "pyproject.toml"
            if main_pyproject.exists():
                try:
                    with main_pyproject.open("rb") as f:
                        pyproject_data = tomllib.load(f)
                    project_name = pyproject_data.get("project", {}).get("name", "")
                    if project_name == "langflow":
                        pyproject_paths.append(main_pyproject)
                        logger.info(f"Found main langflow pyproject.toml at: {main_pyproject}")
                        break
                except (OSError, tomllib.TOMLDecodeError):
                    continue

        # Also check langflow-base pyproject.toml
        # Go up from api/v1/packages.py to base/ directory
        base_path = current_path.parent.parent.parent.parent / "pyproject.toml"
        if base_path.exists():
            try:
                with base_path.open("rb") as f:
                    pyproject_data = tomllib.load(f)
                project_name = pyproject_data.get("project", {}).get("name", "")
                if project_name == "langflow-base":
                    pyproject_paths.append(base_path)
                    logger.info(f"Found langflow-base pyproject.toml at: {base_path}")
            except (OSError, tomllib.TOMLDecodeError):
                pass

        # Process all found pyproject.toml files
        for pyproject_path in pyproject_paths:
            with pyproject_path.open("rb") as f:
                pyproject_data = tomllib.load(f)

            dependencies = pyproject_data.get("project", {}).get("dependencies", [])
            project_name = pyproject_data.get("project", {}).get("name", "unknown")

            # Extract base package names from dependency specifications
            for dep in dependencies:
                # Remove version specifiers and extras to get base package name
                # Handle patterns like: package>=1.0.0, package[extra]>=1.0.0, package==1.0.0; condition
                base_name = re.split(r"[<>=!~\[\];]", dep)[0].strip()
                if base_name:
                    core_packages.add(base_name.lower())

            logger.info(f"Found {len(dependencies)} dependencies in {project_name}")

        # Add essential runtime dependencies that might not be in pyproject.toml but are needed
        essential_runtime_deps = {
            "openai",  # Often used by components but not always in core deps
            "anthropic",  # Claude/Anthropic integration
            "google-generativeai",  # Google AI integration
            "mistralai",  # Mistral AI integration
            "cohere",  # Cohere integration
            "tiktoken",  # OpenAI tokenizer
            "langchain-openai",  # OpenAI integration for langchain
            "langchain-anthropic",  # Anthropic integration for langchain
            "langchain-google-genai",  # Google integration for langchain
            "requests",  # HTTP client
            "httpx",  # Async HTTP client
        }

        core_packages.update(essential_runtime_deps)

        logger.info(f"Total core dependencies found: {len(core_packages)}")
        return core_packages  # noqa: TRY300

    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.error(f"Failed to read core dependencies from pyproject.toml: {e}")
        # Return a comprehensive set of critical packages to prevent catastrophic failures
        return {
            "requests",
            "pandas",
            "openai",
            "anthropic",
            "google-generativeai",
            "mistralai",
            "cohere",
            "tiktoken",
            "langchain",
            "langchain-core",
            "langchain-openai",
            "langchain-anthropic",
            "langchain-google-genai",
            "fastapi",
            "uvicorn",
            "sqlmodel",
            "pydantic",
            "langflow-base",
            "httpx",
        }


def _is_core_dependency(package_name: str) -> bool:
    """Check if a package is a core dependency that should not be uninstalled."""
    core_deps = _get_core_dependencies()
    return package_name.lower() in core_deps


async def cleanup_orphaned_installation_records(session, user_id: UUID) -> int:
    """Clean up orphaned package installation records that no longer exist in the system."""
    import asyncio
    import json

    # Get all user installations that are marked as COMPLETED
    user_installations = await session.exec(
        select(PackageInstallation)
        .where(PackageInstallation.user_id == user_id)
        .where(PackageInstallation.status == InstallationStatus.COMPLETED)
    )

    # Get actual installed packages from system
    try:
        uv_executable = _find_uv_executable()
        project_root = _find_project_root()

        # Get system packages with explicit Python path to ensure consistent environment
        python_executable = _find_python_executable(project_root)
        process = await asyncio.create_subprocess_exec(
            str(uv_executable),
            "pip",
            "list",
            "--format=json",
            "--python",
            python_executable,
            cwd=project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            system_packages_data = json.loads(stdout.decode("utf-8"))
            system_packages = {pkg["name"].lower() for pkg in system_packages_data}
        else:
            logger.warning("Could not get system package list for cleanup")
            return 0

    except (OSError, RuntimeError, json.JSONDecodeError) as e:
        logger.warning(f"Error getting system packages for cleanup: {e}")
        return 0

    # Remove installation records for packages not in system
    cleaned_count = 0
    import re

    for installation in user_installations:
        base_name = re.split(r"[<>=!~]", installation.package_name)[0].strip().lower()
        if base_name not in system_packages:
            logger.info(f"Cleaning up orphaned installation record: {installation.package_name}")
            await session.delete(installation)
            cleaned_count += 1

    if cleaned_count > 0:
        await session.commit()
        logger.info(f"Cleaned up {cleaned_count} orphaned installation records")

    return cleaned_count


async def restore_langflow_background(installation_id: UUID) -> None:
    """Background task to restore langflow by reinstalling from zero and clearing all user packages."""
    import asyncio

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

            # Find UV executable and project root
            uv_executable = _find_uv_executable()
            project_root = _find_project_root()

            logger.info("Starting Langflow restore process")
            logger.info(f"Found UV executable at: {uv_executable}")
            logger.info(f"Found project root at: {project_root}")

            # Step 1: Get list of user-installed packages to remove
            user_installations = await session.exec(
                select(PackageInstallation)
                .where(PackageInstallation.user_id == installation.user_id)
                .where(PackageInstallation.status == InstallationStatus.COMPLETED)
            )

            packages_to_remove = []
            import re

            for user_installation in user_installations:
                if user_installation.id != installation.id:  # Don't include current restore record
                    base_name = re.split(r"[<>=!~]", user_installation.package_name)[0].strip()
                    packages_to_remove.append(base_name)

            logger.info(f"Found {len(packages_to_remove)} user-installed packages to remove: {packages_to_remove}")

            # Step 2: Remove user-installed packages individually to avoid removing core dependencies
            restore_failed = False
            error_messages = []

            if packages_to_remove:
                for package in packages_to_remove:
                    # Skip trying to remove the restore marker package
                    if package == "langflow-restore":
                        logger.info(f"Skipping removal of restore marker package: {package}")
                        continue

                    # On Windows, use pip uninstall for packages installed via pip
                    if platform.system() == "Windows":
                        python_executable = _find_python_executable(project_root)
                        remove_command = [
                            str(uv_executable),
                            "pip",
                            "uninstall",
                            package,
                            "--python",
                            python_executable,
                        ]
                    else:
                        remove_command = [str(uv_executable), "remove", package]
                    logger.info(f"Removing package: {package}")

                    process = await asyncio.create_subprocess_exec(
                        *remove_command,
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

                    # Check if removal failed for critical reasons
                    if process.returncode != 0:
                        combined_output = f"{stdout_text} {stderr_text}".lower()
                        # Only fail if it's a real error, not just "package not found"
                        not_found_phrases = [
                            "not found",
                            "no packages",
                            "already removed",
                            "could not be found in",
                            "dependency could not be found",
                            "not in dependencies",
                        ]
                        if not any(phrase in combined_output for phrase in not_found_phrases):
                            restore_failed = True
                            error_msg = stderr_text or stdout_text or f"Failed to remove {package}"
                            error_messages.append(error_msg)
                            logger.error(f"Failed to remove package {package}: {error_msg}")
                        else:
                            logger.info(f"Package {package} was not found or already removed - this is expected")
                    else:
                        logger.info(f"Successfully removed package: {package}")

            # Step 3: Detect if we have a lock file, otherwise use pip install
            lock_file = project_root / "uv.lock"
            if lock_file.exists():
                # Use frozen sync when lock file exists
                sync_command = [str(uv_executable), "sync", "--frozen"]
                logger.info(
                    f"Found lock file, running sync with frozen lock: {' '.join(sync_command)} in {project_root}"
                )
            else:
                # No lock file - likely running with 'uv run langflow run'
                # Use pip install to reinstall langflow
                sync_command = [str(uv_executable), "pip", "install", "langflow"]
                logger.info(f"No lock file found, reinstalling langflow: {' '.join(sync_command)} in {project_root}")

            process = await asyncio.create_subprocess_exec(
                *sync_command,
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

            # Check final sync result
            if process.returncode != 0:
                sync_error = stderr_text or stdout_text or "Sync failed"
                error_messages.append(sync_error)
                restore_failed = True
                logger.error(f"Final sync failed: {sync_error}")
            else:
                logger.info("Final sync completed successfully")

            logger.info(f"Restore failed status: {restore_failed}")

            if not restore_failed:
                logger.info("Successfully restored Langflow to original state")
                installation.status = InstallationStatus.COMPLETED
                installation.message = "Langflow restored successfully - all user-installed packages removed"
                logger.info("Setting restore status to COMPLETED")

                # Completely remove all user package installation records to ensure clean state
                user_installations_to_delete = await session.exec(
                    select(PackageInstallation)
                    .where(PackageInstallation.user_id == installation.user_id)
                    .where(
                        PackageInstallation.status.in_(
                            [InstallationStatus.COMPLETED, InstallationStatus.FAILED, InstallationStatus.UNINSTALLED]
                        )
                    )
                )

                deleted_count = 0
                for user_installation in user_installations_to_delete:
                    if user_installation.id != installation.id:  # Don't delete the current restore record
                        logger.info(
                            f"Removing installation record: {user_installation.package_name} "
                            f"(ID: {user_installation.id})"
                        )
                        await session.delete(user_installation)
                        deleted_count += 1

                logger.info(f"Clean restore completed - removed {deleted_count} package installation records")

                # Mark restore as completed first so frontend can detect success
                installation.status = InstallationStatus.COMPLETED
                installation.message = "Langflow restored successfully - all user-installed packages removed"
                installation.updated_at = datetime.now(timezone.utc)
                session.add(installation)
                await session.commit()
                logger.info("Setting restore status to COMPLETED")

                # Wait longer to allow frontend to detect completion before cleanup
                import asyncio

                await asyncio.sleep(10)

                # Now remove the restore operation record to leave completely clean table
                logger.info(f"Removing restore operation record: {installation.package_name} (ID: {installation.id})")
                await session.delete(installation)
                await session.commit()
                logger.info("Package installation table completely cleaned - restore process complete")
                # After deletion, we cannot update the installation record anymore
                return
            # Combine all error messages
            error_message = "; ".join(error_messages) if error_messages else "Unknown error during restore"

            # Clean up the error message for Windows
            if platform.system() == "Windows":
                import re

                # Remove problematic unicode characters and clean up the message
                error_message = re.sub(r"[^\x00-\x7F]+", " ", error_message)
                # Clean up multiple spaces
                error_message = re.sub(r"\s+", " ", error_message).strip()

            logger.error(f"Failed to restore Langflow: {error_message}")
            installation.status = InstallationStatus.FAILED
            installation.message = f"Failed to restore Langflow: {error_message}"
            logger.info("Setting restore status to FAILED")

            # Update installation record for failure case
            installation.updated_at = datetime.now(timezone.utc)
            session.add(installation)
            await session.commit()
            logger.info(f"Database updated - Final restore status: {installation.status}")

        except (OSError, RuntimeError, subprocess.CalledProcessError, asyncio.TimeoutError) as e:
            logger.exception(f"Unexpected error during Langflow restore: {e}")
            # Ensure status is always updated even for unexpected errors
            if installation:
                try:
                    installation.status = InstallationStatus.FAILED
                    installation.message = f"Unexpected error during restore: {e!s}"
                    installation.updated_at = datetime.now(timezone.utc)
                    session.add(installation)
                    await session.commit()
                except (SQLAlchemyError, OSError) as commit_error:
                    logger.error(f"Failed to update installation status after error: {commit_error}")
            logger.info("Langflow restore failed due to unexpected error.")


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

            # Install the package using UV with explicit Python path
            python_executable = _find_python_executable(project_root)

            # On Windows, use pip install directly to avoid file locking issues with langflow.exe
            if platform.system() == "Windows":
                # Use pip install on Windows to avoid rebuilding the running langflow.exe
                command = [str(uv_executable), "pip", "install", package_name, "--python", python_executable]
                logger.info("Using 'uv pip install' on Windows to avoid file locking issues")
            else:
                # Use uv add on other platforms for better dependency management
                # Note: uv add doesn't need --python flag as it works with the project environment
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


@router.post("/restore", response_model=PackageRestoreResponse, status_code=202)
async def restore_langflow(
    *,
    restore_request: PackageRestoreRequest,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Restore Langflow by reinstalling from zero and removing all user-installed packages."""
    if not get_settings_service().settings.package_manager:
        raise HTTPException(status_code=403, detail="Package manager is disabled")

    if not restore_request.confirm:
        error_detail = (
            "Restore confirmation is required. This will remove all user-installed packages and restart the backend."
        )
        raise HTTPException(status_code=400, detail=error_detail)

    # Check if there's already an operation in progress for this user
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

    # Create restore record
    installation_data = PackageInstallationCreate(
        package_name="langflow-restore",  # Special marker for restore operations
        user_id=current_user.id,
    )
    installation = PackageInstallation.model_validate(installation_data.model_dump())
    session.add(installation)
    await session.commit()
    await session.refresh(installation)

    # Start background restore
    background_tasks.add_task(restore_langflow_background, installation.id)

    return PackageRestoreResponse(
        message="Langflow restore started - all user-installed packages will be removed and the backend will restart",
        status="started",
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
        # Clean up any orphaned installation records first
        cleaned_count = await cleanup_orphaned_installation_records(session, current_user.id)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} orphaned package records")

        # Get successfully installed packages for the current user from database
        # We need to find packages that are COMPLETED (installed) but not UNINSTALLED
        result = await session.exec(
            select(PackageInstallation)
            .where(PackageInstallation.user_id == current_user.id)
            .where(PackageInstallation.status.in_([InstallationStatus.COMPLETED, InstallationStatus.UNINSTALLED]))
        )
        all_installations = list(result)

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

        # Get installed packages using UV with explicit Python path
        python_executable = _find_python_executable(project_root)
        command = [str(uv_executable), "pip", "list", "--format=json", "--python", python_executable]

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
                    # or if the restore process removed it but database cleanup is pending
                    logger.debug(
                        f"Package {base_package_name} was installed by user but not found in system - "
                        f"may have been removed externally"
                    )

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
