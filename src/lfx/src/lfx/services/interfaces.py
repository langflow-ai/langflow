"""Service interface protocols for lfx package."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import asyncio
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

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
    """Protocol for deployment provider services."""

    @abstractmethod
    async def create_deployment(
        self,
        *,
        user_id: str,
        project_id: str,
        snapshot_id: str,
        config_id: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """Create a new deployment in the provider and track it in Langflow.

        Must create the deployment in the provider and return the resulting
        Langflow-tracked deployment record, including any provider-assigned IDs
        or URLs recorded by Langflow.
        """
        ...

    @abstractmethod
    async def list_deployments(
        self,
        *,
        flow_id: str | None = None,
        config_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List Langflow-tracked deployments visible to this adapter.

        Must return Langflow-tracked records (not live provider truth). Optional
        filters constrain results by related flow, config, or snapshot.
        """
        ...

    @abstractmethod
    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Return the Langflow-tracked deployment record by ID.

        Must return Langflow-tracked metadata and may diverge from live provider
        state.
        """
        ...

    @abstractmethod
    async def update_deployment(
        self,
        deployment_id: str,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """Update deployment inputs and apply changes in the provider.

        Any provided snapshot/config/tag replaces the existing value. Must
        apply the change in the provider and return the updated Langflow-tracked
        deployment record after the provider update is applied.
        """
        ...

    @abstractmethod
    async def redeploy_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Re-apply current deployment inputs without changing them.

        Intended to trigger a provider-side restart/rebuild using existing
        snapshot/config/tag values. Must return the resulting Langflow-tracked
        deployment record after the provider action completes.
        """
        ...

    @abstractmethod
    async def clone_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Create a new deployment using the same inputs as the source.

        Uses the source deployment's snapshot/config/tag to create a new
        deployment identity. Must return the new Langflow-tracked deployment
        record.
        """
        ...

    @abstractmethod
    async def delete_deployment(self, deployment_id: str) -> None:
        """Delete the deployment from the provider and Langflow tracking."""
        ...

    @abstractmethod
    async def get_deployment_health(self, deployment_id: str) -> dict[str, Any]:
        """Return provider-reported health/status for the deployment.

        Must return provider-truth health/status, not a cached value.
        """
        ...

    @abstractmethod
    async def get_live_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Fetch live provider-truth state for this deployment.

        Must return authoritative provider state (no Langflow caching), used
        for drift detection against Langflow-tracked state.
        """
        ...

    @abstractmethod
    async def list_live_deployments(self) -> list[dict[str, Any]]:
        """List live provider-truth deployments visible to this adapter.

        Must return provider-truth data (no Langflow caching).
        """
        ...

    @abstractmethod
    async def create_deployment_config(
        self,
        *,
        user_id: str,
        data: dict,
    ) -> dict[str, Any]:
        """Create a provider-scoped deployment configuration.

        The data payload is provider-specific JSON config. Must return the
        newly created Langflow-tracked config record.
        """
        ...

    @abstractmethod
    async def list_deployment_configs(self) -> list[dict[str, Any]]:
        """List Langflow-tracked deployment configurations for this provider."""
        ...

    @abstractmethod
    async def get_deployment_config(self, config_id: str) -> dict[str, Any]:
        """Return a Langflow-tracked deployment configuration by ID."""
        ...

    @abstractmethod
    async def update_deployment_config(
        self,
        config_id: str,
        *,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Update a deployment configuration's JSON data.

        Must return the updated Langflow-tracked config record.
        """
        ...

    @abstractmethod
    async def clone_deployment_config(self, config_id: str) -> dict[str, Any]:
        """Create a new Langflow-tracked config using the same data as the source."""
        ...

    @abstractmethod
    async def export_deployment_config(self, config_id: str) -> dict:
        """Return a portable JSON export of the Langflow-tracked configuration."""
        ...

    @abstractmethod
    async def import_deployment_config(
        self,
        *,
        user_id: str,
        data: dict,
    ) -> dict[str, Any]:
        """Create a Langflow-tracked configuration from an exported JSON payload."""
        ...

    @abstractmethod
    async def delete_deployment_config(self, config_id: str) -> None:
        """Delete a deployment configuration from Langflow tracking."""
        ...

    @abstractmethod
    async def get_provider_config_schema(self) -> dict:
        """Return provider-specific configuration schema and defaults.

        Must return provider-truth schema/defaults used by UI or validation.
        """
        ...

