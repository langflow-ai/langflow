"""Package manager service implementation."""

import importlib.metadata
import sys

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        import toml as tomllib
import asyncio
import logging
from pathlib import Path

from langflow.services.base import Service

from .models import InstallResponse, OptionalDependency, PackageStatus

logger = logging.getLogger(__name__)


class PackageManagerService(Service):
    """Service for managing optional dependency installations."""

    # Whitelist of allowed optional dependency groups from pyproject.toml
    ALLOWED_GROUPS = {
        "docling", "audio", "couchbase", "cassio", "local",
        "clickhouse-connect", "nv-ingest", "postgresql"
    }

    # Timeout for subprocess (5 minutes)
    MAX_CPU_TIME = 300

    name: str = "package_manager_service"

    def __init__(self):
        self.optional_dependencies: dict[str, OptionalDependency] = {}
        print("PACKAGE MANAGER SERVICE INITIALIZING!", file=sys.stderr, flush=True)
        self._load_optional_dependencies()

    def _load_optional_dependencies(self) -> None:
        """Load optional dependencies from pyproject.toml."""
        try:
            # Find pyproject.toml
            current_dir = Path(__file__).parent
            project_root = current_dir
            print(f"STARTING SEARCH FROM: {current_dir}", file=sys.stderr, flush=True)
            while project_root.parent != project_root:
                pyproject_path = project_root / "pyproject.toml"
                print(f"CHECKING: {pyproject_path}", file=sys.stderr, flush=True)
                if pyproject_path.exists():
                    print(f"FOUND PYPROJECT.TOML AT: {pyproject_path}", file=sys.stderr, flush=True)
                    break
                project_root = project_root.parent

            pyproject_path = project_root / "pyproject.toml"
            if not pyproject_path.exists():
                print("ERROR: Could not find pyproject.toml")
                return

            # Parse pyproject.toml
            try:
                # Try binary mode for tomllib/tomli
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
            except (AttributeError, TypeError):
                # Fallback to text mode for toml library
                with open(pyproject_path) as f:
                    data = tomllib.load(f)

            optional_deps = data.get("project", {}).get("optional-dependencies", {})

            print(f"FOUND OPTIONAL DEPS: {list(optional_deps.keys())}", file=sys.stderr, flush=True)
            print(f"ALLOWED GROUPS: {self.ALLOWED_GROUPS}", file=sys.stderr, flush=True)

            # Create OptionalDependency objects
            for name, packages in optional_deps.items():
                print(f"PROCESSING: {name} -> {packages}", file=sys.stderr, flush=True)
                if name in self.ALLOWED_GROUPS:
                    print(f"ADDING: {name} (allowed)", file=sys.stderr, flush=True)
                    self.optional_dependencies[name] = OptionalDependency(
                        name=name,
                        display_name=self._get_display_name(name),
                        description=self._get_description(name),
                        packages=packages,
                        status=self._check_installation_status(packages)
                    )
                else:
                    print(f"SKIPPING: {name} (not in allowed groups)", file=sys.stderr, flush=True)
        except Exception as e:
            logger.error(f"Error loading optional dependencies: {e}")

    def _get_display_name(self, name: str) -> str:
        """Get user-friendly display name for dependency group."""
        display_names = {
            "docling": "Docling (Document Processing)",
            "audio": "Audio Processing",
            "couchbase": "Couchbase Database",
            "cassio": "Cassandra I/O",
            "local": "Local Models (Llama, Embeddings)",
            "clickhouse-connect": "ClickHouse Database",
            "nv-ingest": "NVIDIA Ingest",
            "postgresql": "PostgreSQL Database"
        }
        return display_names.get(name, name.title())

    def _get_description(self, name: str) -> str:
        """Get description for dependency group."""
        descriptions = {
            "docling": "Advanced document processing and extraction capabilities",
            "audio": "Audio processing with WebRTC VAD support",
            "couchbase": "Couchbase vector database integration",
            "cassio": "Apache Cassandra database integration",
            "local": "Run models locally with llama-cpp and sentence-transformers",
            "clickhouse-connect": "ClickHouse database integration for analytics",
            "nv-ingest": "NVIDIA document ingestion and processing",
            "postgresql": "PostgreSQL database integration with async support"
        }
        return descriptions.get(name, f"Optional dependencies for {name}")

    def _check_installation_status(self, packages: list[str]) -> PackageStatus:
        """Check if all packages in a group are installed."""
        try:
            for package_spec in packages:
                # Extract package name from version spec
                package_name = package_spec.split(">=")[0].split("==")[0].split("~=")[0].split("[")[0]
                try:
                    importlib.metadata.version(package_name)
                except importlib.metadata.PackageNotFoundError:
                    return PackageStatus.NOT_INSTALLED
            return PackageStatus.INSTALLED
        except Exception:
            return PackageStatus.UNKNOWN

    def get_optional_dependencies(self) -> dict[str, OptionalDependency]:
        """Get all optional dependencies with their current status."""
        # Refresh status before returning
        for dep in self.optional_dependencies.values():
            dep.status = self._check_installation_status(dep.packages)
        return self.optional_dependencies

    async def install_dependency(self, dependency_name: str, auto_restart: bool = False) -> InstallResponse:
        """Install an optional dependency group."""
        if dependency_name not in self.ALLOWED_GROUPS:
            return InstallResponse(
                dependency_name=dependency_name,
                status=PackageStatus.FAILED,
                message=f"Dependency group '{dependency_name}' is not allowed",
                error="Invalid dependency group"
            )

        if dependency_name not in self.optional_dependencies:
            return InstallResponse(
                dependency_name=dependency_name,
                status=PackageStatus.FAILED,
                message=f"Dependency group '{dependency_name}' not found",
                error="Dependency not found"
            )

        dep = self.optional_dependencies[dependency_name]

        # Check if already installed
        if dep.status == PackageStatus.INSTALLED:
            return InstallResponse(
                dependency_name=dependency_name,
                status=PackageStatus.INSTALLED,
                message=f"{dep.display_name} is already installed"
            )

        # Mark as installing
        dep.status = PackageStatus.INSTALLING

        try:
            # Install packages using subprocess with resource limits
            result = await self._install_packages(dep.packages)

            if result:
                dep.status = PackageStatus.INSTALLED
                
                message = f"Successfully installed {dep.display_name}."
                if auto_restart:
                    message += " Server will restart automatically."
                else:
                    message += " Please restart the backend to use the new packages."
                
                return InstallResponse(
                    dependency_name=dependency_name,
                    status=PackageStatus.INSTALLED,
                    message=message,
                    restart_required=True,
                    auto_restart=auto_restart
                )
            dep.status = PackageStatus.FAILED
            return InstallResponse(
                dependency_name=dependency_name,
                status=PackageStatus.FAILED,
                message=f"Failed to install {dep.display_name}",
                error="Installation failed"
            )

        except Exception as e:
            dep.status = PackageStatus.FAILED
            dep.error = str(e)
            return InstallResponse(
                dependency_name=dependency_name,
                status=PackageStatus.FAILED,
                message=f"Error installing {dep.display_name}",
                error=str(e)
            )

    async def _install_packages(self, packages: list[str]) -> bool:
        """Install packages using uv pip in a subprocess."""
        try:
            # Use uv pip install instead of regular pip (since this project uses uv)
            cmd = ["uv", "pip", "install"] + packages

            logger.info(f"Installing packages with uv: {packages}")

            # Run in subprocess with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.MAX_CPU_TIME
                )

                if process.returncode == 0:
                    logger.info(f"Successfully installed packages: {packages}")
                    logger.debug(f"Installation output: {stdout.decode()}")
                    return True
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Failed to install packages {packages}: {error_msg}")
                logger.error(f"Command that failed: {' '.join(cmd)}")
                return False

            except asyncio.TimeoutError:
                process.kill()
                logger.error(f"Installation of {packages} timed out after {self.MAX_CPU_TIME} seconds")
                return False

        except Exception as e:
            logger.error(f"Error installing packages {packages}: {e}")
            return False