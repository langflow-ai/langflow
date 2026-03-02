"""Service interface protocols for lfx package."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import asyncio
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from lfx.services.deployment.schema import (
        ArtifactType,
        BaseConfigData,
        ConfigItemResult,
        ConfigListFilterOptions,
        ConfigListResult,
        ConfigResult,
        ConfigUpdate,
        DeploymentCreate,
        DeploymentCreateResult,
        DeploymentDeleteResult,
        DeploymentDetailItem,
        DeploymentExecution,
        DeploymentExecutionResult,
        DeploymentExecutionStatus,
        DeploymentItem,
        DeploymentList,
        DeploymentListParams,
        DeploymentProviderId,
        DeploymentRedeploymentResult,
        DeploymentStatusResult,
        DeploymentType,
        DeploymentUpdate,
        DeploymentUpdateResult,
        SnapshotGetResult,
        SnapshotItemsCreate,
        SnapshotListFilterOptions,
        SnapshotListResult,
        SnapshotResult,
    )
    from lfx.services.settings.base import Settings


class AuthUserProtocol(Protocol):
    """Auhtenticated user object (id, username, is_active, is_superuser).

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


class DeploymentServiceProtocol(Protocol):
    """Protocol for deployment provider services.

    This protocol exposes adapter-agnostic deployment contracts:
    top-level fields are minimal generic metadata, while provider-specific
    details are carried in ``provider_data``/``provider_result`` fields.
    """

    @abstractmethod
    async def create(
        self,
        *,
        user_id: UUID | str,
        deployment: DeploymentCreate,
        db: Any,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""
        ...

    @abstractmethod
    async def list_types(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> list[DeploymentType]:
        """List deployment types supported by the provider."""
        ...

    @abstractmethod
    async def list(
        self,
        *,
        user_id: UUID | str,
        db: Any,
        params: DeploymentListParams | None = None,
    ) -> DeploymentList:
        """List deployments visible to this adapter."""
        ...

    @abstractmethod
    async def get(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentDetailItem:
        """Return deployment metadata by provider ID."""
        ...

    @abstractmethod
    async def update(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        update_data: DeploymentUpdate,
        db: Any,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""
        ...

    @abstractmethod
    async def redeploy(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentRedeploymentResult:
        """Re-apply current deployment inputs without changing them."""
        ...

    @abstractmethod
    async def duplicate(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        deployment_type: DeploymentType,
        db: Any,
    ) -> DeploymentItem:
        """Create a new deployment using the same inputs as the source."""
        ...

    @abstractmethod
    async def delete(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""
        ...

    @abstractmethod
    async def get_status(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""
        ...

    @abstractmethod
    async def create_execution(
        self,
        *,
        user_id: UUID | str,
        execution: DeploymentExecution,
        db: Any,
    ) -> DeploymentExecutionResult:
        """Run a provider-agnostic deployment execution."""
        ...

    @abstractmethod
    async def get_execution(
        self,
        *,
        user_id: UUID | str,
        execution_status: DeploymentExecutionStatus,
        db: Any,
    ) -> DeploymentExecutionResult:
        """Get provider-agnostic deployment execution state/output."""
        ...

    @abstractmethod
    async def create_config(
        self,
        *,
        user_id: UUID | str,
        config: BaseConfigData,
        db: Any,
    ) -> ConfigResult:
        """Create a provider-scoped deployment configuration."""
        ...

    @abstractmethod
    async def list_configs(
        self,
        *,
        user_id: UUID | str,
        db: Any,
        filter_options: ConfigListFilterOptions | None = None,
    ) -> ConfigListResult:
        """List deployment configurations."""
        ...

    @abstractmethod
    async def get_config(
        self,
        *,
        user_id: UUID | str,
        config_id: str,
        db: Any,
    ) -> ConfigItemResult:
        """Return deployment configuration by provider ID."""
        ...

    @abstractmethod
    async def update_config(
        self,
        *,
        config_id: str,
        update_data: ConfigUpdate,
        user_id: UUID | str,
        db: Any,
    ) -> ConfigResult:
        """Update a deployment configuration's JSON data."""
        ...

    @abstractmethod
    async def delete_config(
        self,
        *,
        user_id: UUID | str,
        config_id: str,
        db: Any,
    ) -> None:
        """Delete a deployment configuration from the provider."""
        ...

    @abstractmethod
    async def create_snapshots(
        self,
        *,
        user_id: UUID | str,
        snapshot_items: SnapshotItemsCreate,
        db: Any,
    ) -> SnapshotResult:
        """Create a provider snapshot (deployed or not)."""
        ...

    @abstractmethod # TODO: allow filtering by flow id or by other criteria
    async def list_snapshots(
        self,
        *,
        user_id: UUID | str,
        artifact_type: ArtifactType | None = None,
        db: Any,
        filter_options: SnapshotListFilterOptions | None = None,
    ) -> SnapshotListResult:
        """List provider snapshots (deployed or not)."""
        ...

    @abstractmethod
    async def get_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: str,
        db: Any,
    ) -> SnapshotGetResult:
        """Return snapshot payload by provider ID."""
        ...

    @abstractmethod
    async def delete_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: str,
        db: Any,
    ) -> None:
        """Delete a provider snapshot."""
        ...


class DeploymentRouterServiceProtocol(Protocol):
    """Protocol for deployment adapter resolver services."""

    @abstractmethod
    async def resolve_adapter(
        self,
        *,
        provider_id: DeploymentProviderId,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentServiceProtocol:
        """Resolve and return adapter for a provider account owned by a user."""
        ...

    @abstractmethod
    def list_adapter_keys(self) -> list[str]:
        """List available adapter keys."""
        ...

