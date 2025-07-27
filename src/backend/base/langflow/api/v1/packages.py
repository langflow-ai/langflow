import asyncio
import os
import platform
import shutil
import sys
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


async def _restart_application() -> None:
    """Restart the application with cross-platform compatibility."""
    try:
        # Wait to allow HTTP response to be sent
        await asyncio.sleep(2)
        logger.info("Initiating application restart...")

        # Strategy 1: Try to trigger uvicorn reload by touching Python files
        reload_triggered = await _trigger_uvicorn_reload()
        if reload_triggered:
            return

        # Strategy 2: Platform-specific restart signals
        restart_triggered = await _send_restart_signal()
        if restart_triggered:
            return

        # Strategy 3: Force exit as last resort
        logger.info("Force exiting application to trigger restart...")
        os._exit(0)

    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to restart application: {e}")
        # Emergency fallback
        os._exit(1)


async def _trigger_uvicorn_reload() -> bool:
    """Try to trigger uvicorn reload by touching Python files."""
    project_root = _find_project_root()

    # List of files to try touching (in order of preference)
    reload_files = [
        project_root / "main.py",
        project_root / "langflow" / "main.py",
        project_root / "langflow" / "__init__.py",
        project_root / "__init__.py",
    ]

    for file_path in reload_files:
        try:
            if file_path.exists():
                logger.info(f"Triggering uvicorn reload by touching {file_path}")
                file_path.touch()
                return True
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to touch {file_path}: {e}")
            continue

    logger.warning("Could not trigger uvicorn reload - no suitable files found")
    return False


async def _send_restart_signal() -> bool:
    """Send platform-appropriate restart signal."""
    try:
        import signal

        current_pid = os.getpid()
        system = platform.system()

        if system == "Windows":
            # Windows: Use SIGTERM (CTRL+C equivalent)
            logger.info("Sending SIGTERM signal for Windows restart...")
            try:
                os.kill(current_pid, signal.SIGTERM)
                await asyncio.sleep(1)
            except (OSError, ProcessLookupError) as e:
                logger.warning(f"Failed to send SIGTERM on Windows: {e}")
            else:
                return True

        elif system in ["Linux", "Darwin"]:  # Darwin is macOS
            # Unix-like systems: Try SIGHUP first, then SIGTERM
            for sig_name, sig_value in [("SIGHUP", signal.SIGHUP), ("SIGTERM", signal.SIGTERM)]:
                try:
                    logger.info(f"Sending {sig_name} signal for {system} restart...")
                    os.kill(current_pid, sig_value)
                    await asyncio.sleep(1)
                except (OSError, ProcessLookupError) as e:
                    logger.warning(f"Failed to send {sig_name} on {system}: {e}")
                    continue
                else:
                    return True
        else:
            logger.warning(f"Unknown platform: {system}")

    except ImportError:
        logger.warning("Signal module not available")

    return False


def _validate_package_name(package_name: str) -> bool:
    """Validate package name with enhanced Windows security checks."""
    if not package_name or not package_name.strip():
        return False

    # Your existing validation logic with Windows additions
    forbidden_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">"]

    # Add Windows-specific forbidden characters (same as your original)
    if platform.system() == "Windows":
        forbidden_chars.extend(["%", "^", '"', "'"])

    return not any(char in package_name for char in forbidden_chars)

async def install_package_background(package_name: str) -> None:
    """Background task to install package using uv with cross-platform support."""
    global _installation_in_progress, _last_installation_result  # noqa: PLW0603

    try:
        _installation_in_progress = True
        _last_installation_result = None

        logger.info(f"Starting installation of package: {package_name}")

        # Find UV executable
        uv_cmd = _find_uv_executable()

        # Find project root
        project_root = _find_project_root()

        # Create subprocess with Windows environment handling
        cmd_args = [uv_cmd, "add", package_name]

        # Prepare environment (only modify for Windows if needed)
        env = os.environ.copy()
        if platform.system() == "Windows":
            # Ensure Python Scripts directory is in PATH for Windows
            python_scripts = Path(sys.executable).parent / "Scripts"
            if python_scripts.exists():
                env["PATH"] = f"{python_scripts}{os.pathsep}{env.get('PATH', '')}"

        logger.info(f"Executing command: {' '.join(cmd_args)} in {project_root}")

        process = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
            env=env,
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
                "Ã—",  # This is the × character in Windows encoding
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
            _last_installation_result = {
                "status": "success",
                "package_name": package_name,
                "message": f"Package '{package_name}' installed successfully",
            }
        else:
            # Combine stdout and stderr for complete error message
            error_message = stderr_text or stdout_text or "Unknown error"
            
            # Clean up the error message for Windows
            if platform.system() == "Windows":
                # Remove problematic unicode characters and clean up the message
                import re
                # Remove box drawing and other problematic characters
                error_message = re.sub(r'[^\x00-\x7F]+', ' ', error_message)
                # Clean up multiple spaces
                error_message = re.sub(r'\s+', ' ', error_message).strip()
            
            logger.error(f"Failed to install package {package_name}: {error_message}")
            _last_installation_result = {
                "status": "error",
                "package_name": package_name,
                "message": f"Failed to install package '{package_name}': {error_message}",
            }

        # Schedule restart (keep your existing logic)
        logger.info("Restarting application after package installation...")
        restart_task = asyncio.create_task(_restart_application())
        restart_task.add_done_callback(lambda _: None)

    except (OSError, RuntimeError) as e:
        logger.exception(f"Error installing package {package_name}")
        _last_installation_result = {
            "status": "error",
            "package_name": package_name,
            "message": f"Error installing package '{package_name}': {e!s}",
        }

        # Schedule restart even after exception (keep your existing logic)
        logger.info("Restarting application after package installation exception to reset state...")
        restart_task = asyncio.create_task(_restart_application())
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
    """Install a Python package using uv with cross-platform support."""
    global _installation_in_progress  # noqa: PLW0602

    if _installation_in_progress:
        raise HTTPException(status_code=409, detail="Package installation already in progress")

    package_name = package_request.package_name.strip()

    # Validate package name (keep your existing validation + Windows enhancement)
    if not _validate_package_name(package_name):
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
    """Clear the installation status."""
    global _installation_in_progress, _last_installation_result  # noqa: PLW0603

    _installation_in_progress = False
    _last_installation_result = None

    return {"message": "Installation status cleared"}
