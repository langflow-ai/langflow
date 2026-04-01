"""Service interface protocols for lfx package."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import asyncio
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from lfx.services.adapters.deployment.schema import (
        ConfigListParams,
        ConfigListResult,
        DeploymentCreate,
        DeploymentCreateResult,
        DeploymentDeleteResult,
        DeploymentDuplicateResult,
        DeploymentGetResult,
        DeploymentListParams,
        DeploymentListResult,
        DeploymentListTypesResult,
        DeploymentStatusResult,
        DeploymentType,
        DeploymentUpdate,
        DeploymentUpdateResult,
        ExecutionCreate,
        ExecutionCreateResult,
        ExecutionStatusResult,
        IdLike,
        RedeployResult,
        SnapshotListParams,
        SnapshotListResult,
    )
    from lfx.services.settings.base import Settings


class AuthUserProtocol(Protocol):
    """Authenticated user object (id, username, is_active, is_superuser).

    Implementations may use User or UserRead from the database layer; this protocol
    describes the surface needed by consumers of the auth service.
    """

    id: UUID
    username: str
    is_active: bool
    is_superuser: bool


class AuthServiceProtocol(Protocol):
    """Protocol for auth service (minimal surface for dependency injection)."""

    @abstractmethod
    async def get_current_user(
        self,
        token: str | None,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
    ) -> AuthUserProtocol:
        """Get the current authenticated user from token or API key."""
        ...

    @abstractmethod
    async def api_key_security(
        self,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession | None = None,
    ) -> AuthUserProtocol | None:
        """Validate API key from query or header. Returns user or None."""
        ...


class DatabaseServiceProtocol(Protocol):
    """Protocol for database service."""

    @abstractmethod
    def with_session(self) -> Any:
        """Get database session."""
        ...


class StorageServiceProtocol(Protocol):
    """Protocol for storage service."""

    @abstractmethod
    def save(self, data: Any, filename: str) -> str:
        """Save data to storage."""
        ...

    @abstractmethod
    def get_file(self, path: str) -> Any:
        """Get file from storage."""
        ...

    @abstractmethod
    def get_file_paths(self, files: list[str | dict]) -> list[str]:
        """Get file paths from storage."""
        ...

    @abstractmethod
    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full path of a file in the storage."""
        ...

    @abstractmethod
    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        """Parse a full storage path to extract flow_id and file_name."""
        ...


class SettingsServiceProtocol(Protocol):
    """Protocol for settings service."""

    @property
    @abstractmethod
    def settings(self) -> Settings:
        """Get settings object."""
        ...


class VariableServiceProtocol(Protocol):
    """Protocol for variable service."""

    @abstractmethod
    def get_variable(self, name: str, **kwargs) -> Any:
        """Get variable value."""
        ...

    @abstractmethod
    def set_variable(self, name: str, value: Any, **kwargs) -> None:
        """Set variable value."""
        ...

    @abstractmethod
    async def get_all_decrypted_variables(self, user_id: Any, session: Any) -> dict[str, str]:
        """Get all variables for a user with decrypted values.

        Args:
            user_id: The user ID to get variables for
            session: Database session

        Returns:
            Dictionary mapping variable names to decrypted values
        """
        ...


class CacheServiceProtocol(Protocol):
    """Protocol for cache service."""

    @abstractmethod
    def get(self, key: str) -> Any:
        """Get cached value."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set cached value."""
        ...


class ChatServiceProtocol(Protocol):
    """Protocol for chat service."""

    @abstractmethod
    async def get_cache(self, key: str, lock: asyncio.Lock | None = None) -> Any:
        """Get cached value."""
        ...

    @abstractmethod
    async def set_cache(self, key: str, data: Any, lock: asyncio.Lock | None = None) -> bool:
        """Set cached value."""
        ...


class TracingServiceProtocol(Protocol):
    """Protocol for tracing service."""

    @abstractmethod
    def log(self, message: str, **kwargs) -> None:
        """Log tracing information."""
        ...


@runtime_checkable
class TransactionServiceProtocol(Protocol):
    """Protocol for transaction logging service.

    This service handles logging of component execution transactions,
    tracking inputs, outputs, and status of each vertex build.
    """

    @abstractmethod
    async def log_transaction(
        self,
        flow_id: str,
        vertex_id: str,
        inputs: dict[str, Any] | None,
        outputs: dict[str, Any] | None,
        status: str,
        target_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Log a transaction record for a vertex execution.

        Args:
            flow_id: The flow ID (as string)
            vertex_id: The vertex/component ID
            inputs: Input parameters for the component
            outputs: Output results from the component
            status: Execution status (success/error)
            target_id: Optional target vertex ID
            error: Optional error message
        """
        ...

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if transaction logging is enabled.

        Returns:
            True if transaction logging is enabled, False otherwise.
        """
        ...


@runtime_checkable
class DeploymentServiceProtocol(Protocol):
    """Protocol for deployment provider services.

    This protocol exposes adapter-agnostic deployment contracts:
    top-level fields are minimal generic metadata, while provider-specific
    details are carried in ``provider_data``/``provider_result`` fields.

    Keep this protocol intentionally narrow (consumer-facing CRUD + status).
    Adapter-specific or advanced operations are defined on concrete deployment
    service classes.

    ``deployment_type`` is accepted as an optional routing hint by all
    operations that act on a specific deployment (including executions).
    """

    @abstractmethod
    async def create(
        self,
        *,
        user_id: IdLike,
        payload: DeploymentCreate,
        db: AsyncSession,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""
        ...

    @abstractmethod
    async def list_types(
        self,
        *,
        user_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        ...

    @abstractmethod
    async def list(
        self,
        *,
        user_id: IdLike,
        params: DeploymentListParams | None = None,
        db: AsyncSession,
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""
        ...

    @abstractmethod
    async def get(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""
        ...

    @abstractmethod
    async def update(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        payload: DeploymentUpdate,
        db: AsyncSession,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""
        ...

    @abstractmethod
    async def redeploy(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""
        ...

    @abstractmethod
    async def duplicate(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""
        ...

    @abstractmethod
    async def delete(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""
        ...

    @abstractmethod
    async def get_status(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""
        ...

    @abstractmethod
    async def create_execution(
        self,
        *,
        user_id: IdLike,
        deployment_type: DeploymentType | None = None,
        payload: ExecutionCreate,
        db: AsyncSession,
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""
        ...

    @abstractmethod
    async def get_execution(
        self,
        *,
        user_id: IdLike,
        execution_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        ...

    @abstractmethod
    async def list_configs(
        self,
        *,
        user_id: IdLike,
        params: ConfigListParams | None = None,
        db: AsyncSession,
    ) -> ConfigListResult:
        """List configs visible to this adapter."""
        ...

    @abstractmethod
    async def list_snapshots(
        self,
        *,
        user_id: IdLike,
        params: SnapshotListParams | None = None,
        db: AsyncSession,
    ) -> SnapshotListResult:
        """List snapshots visible to this adapter."""
        ...

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the deployment service."""
        ...
