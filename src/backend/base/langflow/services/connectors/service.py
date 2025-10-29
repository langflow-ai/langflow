"""Connector service for managing connector operations with security enhancements."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from lfx.log import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.base import Service
from langflow.services.connectors.encryption import (
    decrypt_sensitive_field,
    encrypt_sensitive_field,
)
from langflow.services.database.models.connector import (
    ConnectorConnection,
    ConnectorOAuthToken,
    create_oauth_token,
    update_oauth_token,
)
from langflow.services.database.models.connector import create_connection as db_create_connection
from langflow.services.database.models.connector import delete_connection as db_delete_connection
from langflow.services.database.models.connector import get_connection as db_get_connection
from langflow.services.database.models.connector import get_user_connections as db_get_user_connections
from langflow.services.database.models.connector import update_connection as db_update_connection
from langflow.services.database.models.connector.crud import add_to_dlq

from .base import BaseConnector
from .retry import (
    ErrorCategory,
    RetryConfig,
    categorize_error,
    is_retryable,
)


class ConnectorPermissionError(Exception):
    """Raised when user doesn't have permission for an operation."""


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""


class ConnectorService(Service):
    """Service for managing cloud storage connectors with security enhancements."""

    name = "connector_service"

    def __init__(self, settings_service=None):
        """Initialize the connector service."""
        super().__init__()
        self.settings_service = settings_service

        # Connection-level locks to prevent race conditions
        self._connection_locks: dict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Rate limiting semaphores (max concurrent operations per user)
        self._user_rate_limits: dict[UUID, asyncio.Semaphore] = {}
        self.max_concurrent_operations = 10  # Configurable

        # Subscription renewal tracking
        self._subscription_renewal_tasks: dict[UUID, asyncio.Task] = {}

    def _get_user_semaphore(self, user_id: UUID) -> asyncio.Semaphore:
        """Get or create rate limiting semaphore for user.

        Args:
            user_id: User ID

        Returns:
            Semaphore for rate limiting
        """
        if user_id not in self._user_rate_limits:
            self._user_rate_limits[user_id] = asyncio.Semaphore(self.max_concurrent_operations)
        return self._user_rate_limits[user_id]

    async def _validate_user_ownership(
        self, session: AsyncSession, connection_id: UUID, user_id: UUID, operation: str = "access"
    ) -> ConnectorConnection:
        """Validate that user owns the connection.

        Args:
            session: Database session
            connection_id: Connection ID to validate
            user_id: User ID claiming ownership
            operation: Operation being performed (for logging)

        Returns:
            ConnectorConnection if valid

        Raises:
            PermissionError: If user doesn't own connection
        """
        connection = await db_get_connection(session, connection_id, user_id=None)

        if not connection:
            logger.warning(f"Connection {connection_id} not found for {operation}")
            msg = "Connection not found"
            raise ConnectorPermissionError(msg)

        if connection.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted {operation} on connection {connection_id} owned by {connection.user_id}"
            )
            msg = "Access denied to connection"
            raise ConnectorPermissionError(msg)

        return connection

    async def create_connection(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_type: str,
        name: str,
        config: dict[str, Any],
        knowledge_base_id: str | None = None,
    ) -> ConnectorConnection:
        """Create a new connector connection with rate limiting.

        Args:
            session: Database session
            user_id: User creating the connection
            connector_type: Type of connector (google_drive, onedrive, etc.)
            name: Display name for the connection
            config: Connector-specific configuration (sensitive data will be encrypted)
            knowledge_base_id: Optional KB to associate with

        Returns:
            Created ConnectorConnection
        """
        # Apply rate limiting
        semaphore = self._get_user_semaphore(user_id)
        async with semaphore:
            # Encrypt sensitive config fields if present
            if "client_secret" in config:
                config["client_secret"] = encrypt_sensitive_field(config["client_secret"])
            if "api_key" in config:
                config["api_key"] = encrypt_sensitive_field(config["api_key"])

            connection_data = {
                "user_id": user_id,
                "connector_type": connector_type,
                "name": name,
                "config": config,
                "knowledge_base_id": knowledge_base_id,
            }

            connection = await db_create_connection(session, connection_data)
            logger.info(f"Created connection {connection.id} for user {user_id}")

            # Schedule webhook renewal if applicable
            if connector_type in ["google_drive", "onedrive"]:
                await self._schedule_webhook_renewal(connection.id)

            return connection

    async def get_connection(
        self, session: AsyncSession, connection_id: UUID, user_id: UUID
    ) -> ConnectorConnection | None:
        """Get a connection by ID with ownership validation.

        Args:
            session: Database session
            connection_id: Connection ID
            user_id: User ID for access control

        Returns:
            ConnectorConnection or None

        Raises:
            PermissionError: If user doesn't own connection
        """
        try:
            connection = await self._validate_user_ownership(session, connection_id, user_id, "get")

            # Decrypt sensitive config fields before returning
            if connection.config:
                config = connection.config.copy()
                if config.get("client_secret"):
                    try:
                        config["client_secret"] = decrypt_sensitive_field(config["client_secret"])
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to decrypt client_secret for {connection_id}")
                if config.get("api_key"):
                    try:
                        config["api_key"] = decrypt_sensitive_field(config["api_key"])
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to decrypt api_key for {connection_id}")
                connection.config = config
        except ConnectorPermissionError:
            return None
        else:
            return connection

    async def get_user_connections(
        self, session: AsyncSession, user_id: UUID, knowledge_base_id: str | None = None
    ) -> list[ConnectorConnection]:
        """Get all connections for a user.

        Args:
            session: Database session
            user_id: User ID
            knowledge_base_id: Optional filter by KB

        Returns:
            List of ConnectorConnection
        """
        connections = await db_get_user_connections(session, user_id, knowledge_base_id)

        # Decrypt sensitive fields in each connection
        for connection in connections:
            if connection.config:
                config = connection.config.copy()
                if config.get("client_secret"):
                    try:
                        config["client_secret"] = decrypt_sensitive_field(config["client_secret"])
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to decrypt client_secret for {connection.id}")
                if config.get("api_key"):
                    try:
                        config["api_key"] = decrypt_sensitive_field(config["api_key"])
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to decrypt api_key for {connection.id}")
                connection.config = config

        return connections

    async def delete_connection(self, session: AsyncSession, connection_id: UUID, user_id: UUID) -> bool:
        """Delete a connection with ownership validation and cleanup.

        Args:
            session: Database session
            connection_id: Connection to delete
            user_id: User ID for access control

        Returns:
            True if deleted, False if not found or access denied
        """
        # Use connection-level lock to prevent race conditions
        async with self._connection_locks[connection_id]:
            try:
                # Validate ownership
                await self._validate_user_ownership(session, connection_id, user_id, "delete")

                # Cancel any renewal tasks
                if connection_id in self._subscription_renewal_tasks:
                    self._subscription_renewal_tasks[connection_id].cancel()
                    del self._subscription_renewal_tasks[connection_id]

                # Delete from database
                result = await db_delete_connection(session, connection_id, user_id)

                if result:
                    logger.info(f"Deleted connection {connection_id} for user {user_id}")
                    # Clean up lock
                    del self._connection_locks[connection_id]
            except ConnectorPermissionError:
                return False
            else:
                return result

    async def update_connection(
        self, session: AsyncSession, connection_id: UUID, user_id: UUID, update_data: dict[str, Any]
    ) -> ConnectorConnection | None:
        """Update a connection with ownership validation and locking.

        Args:
            session: Database session
            connection_id: Connection to update
            user_id: User ID for access control
            update_data: Fields to update

        Returns:
            Updated ConnectorConnection or None
        """
        # Use connection-level lock to prevent race conditions
        async with self._connection_locks[connection_id]:
            try:
                # Validate ownership
                await self._validate_user_ownership(session, connection_id, user_id, "update")

                # Encrypt sensitive fields if being updated
                if "config" in update_data:
                    config = update_data["config"]
                    if "client_secret" in config:
                        config["client_secret"] = encrypt_sensitive_field(config["client_secret"])
                    if "api_key" in config:
                        config["api_key"] = encrypt_sensitive_field(config["api_key"])
                    update_data["config"] = config

                result = await db_update_connection(session, connection_id, user_id, update_data)

                if result:
                    logger.info(f"Updated connection {connection_id} for user {user_id}")
            except ConnectorPermissionError:
                return None
            else:
                return result

    async def store_oauth_token(
        self,
        session: AsyncSession,
        connection_id: UUID,
        user_id: UUID,
        access_token: str,
        refresh_token: str | None = None,
        expires_in: int | None = None,
        scopes: list[str] | None = None,
    ) -> ConnectorOAuthToken:
        """Store OAuth tokens securely with encryption.

        Args:
            session: Database session
            connection_id: Connection ID
            user_id: User ID for validation
            access_token: OAuth access token
            refresh_token: Optional refresh token
            expires_in: Token expiry in seconds
            scopes: OAuth scopes granted

        Returns:
            Created/updated OAuth token

        Raises:
            PermissionError: If user doesn't own connection
        """
        # Validate ownership
        await self._validate_user_ownership(session, connection_id, user_id, "store_token")

        # Encrypt tokens
        encrypted_access = encrypt_sensitive_field(access_token)
        encrypted_refresh = encrypt_sensitive_field(refresh_token) if refresh_token else None

        # Calculate expiry

        token_expiry = None
        if expires_in:
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        token_data = {
            "connection_id": connection_id,
            "encrypted_access_token": encrypted_access,
            "encrypted_refresh_token": encrypted_refresh,
            "token_expiry": token_expiry,
            "scopes": scopes or [],
        }

        # Check if token already exists
        from langflow.services.database.models.connector import get_oauth_token

        existing = await get_oauth_token(session, connection_id)

        if existing:
            # Update existing token
            token = await update_oauth_token(session, connection_id, token_data)
            logger.info(f"Updated OAuth token for connection {connection_id}")
        else:
            # Create new token
            token = await create_oauth_token(session, token_data)
            logger.info(f"Created OAuth token for connection {connection_id}")

        return token

    async def _schedule_webhook_renewal(self, connection_id: UUID):
        """Schedule periodic webhook subscription renewal.

        Args:
            connection_id: Connection ID to renew webhooks for
        """

        async def renewal_task():
            """Task to renew webhook subscription periodically."""
            while True:
                try:
                    # Google Drive webhooks expire after 3 days, renew after 2 days
                    await asyncio.sleep(2 * 24 * 60 * 60)  # 2 days in seconds

                    logger.info(f"Renewing webhook subscription for connection {connection_id}")

                    # TODO: Implement actual renewal logic with connector instance
                    # connector = await self.get_connector_instance(connection)
                    # await connector.renew_subscription()

                except asyncio.CancelledError:
                    logger.info(f"Webhook renewal cancelled for connection {connection_id}")
                    break
                except (OSError, ValueError) as e:
                    logger.error(f"Failed to renew webhook for {connection_id}: {e}")
                    # Continue trying
                    await asyncio.sleep(60 * 60)  # Retry after 1 hour

        # Cancel any existing task
        if connection_id in self._subscription_renewal_tasks:
            self._subscription_renewal_tasks[connection_id].cancel()

        # Create new renewal task
        task = asyncio.create_task(renewal_task())
        self._subscription_renewal_tasks[connection_id] = task

    async def get_oauth_url(self, connection_id: UUID, user_id: UUID, redirect_uri: str) -> str:
        """Generate OAuth authorization URL with ownership validation.

        Args:
            connection_id: Connection requesting OAuth
            user_id: User ID for validation
            redirect_uri: Where to redirect after auth

        Returns:
            OAuth authorization URL

        Raises:
            PermissionError: If user doesn't own connection
        """
        # TODO: Validate ownership and implement with OAuth handlers
        msg = "OAuth URL generation not yet implemented"
        raise NotImplementedError(msg)

    async def complete_oauth(
        self, session: AsyncSession, connection_id: UUID, user_id: UUID, code: str, state: str | None = None
    ) -> ConnectorConnection:
        """Complete OAuth flow with authorization code and ownership validation.

        Args:
            session: Database session
            connection_id: Connection to authenticate
            user_id: User ID for validation
            code: Authorization code from OAuth provider
            state: State token for CSRF protection

        Returns:
            Updated ConnectorConnection

        Raises:
            PermissionError: If user doesn't own connection
        """
        # TODO: Validate ownership and implement with OAuth handlers
        msg = "OAuth completion not yet implemented"
        raise NotImplementedError(msg)

    async def sync_files(
        self,
        session: AsyncSession,
        connection_id: UUID,
        user_id: UUID,
        selected_files: list[str] | None = None,
        max_files: int = 100
    ) -> str:
        """Start file synchronization with rate limiting and error handling.

        Args:
            session: Database session
            connection_id: Connection to sync
            user_id: User ID for validation
            selected_files: Optional list of specific file IDs
            max_files: Maximum files to sync

        Returns:
            Task ID for tracking progress

        Raises:
            PermissionError: If user doesn't own connection
            RateLimitError: If too many concurrent operations
        """
        # Apply rate limiting
        semaphore = self._get_user_semaphore(user_id)

        if semaphore.locked():
            msg = f"Too many concurrent operations for user {user_id}"
            raise RateLimitError(msg)

        async with semaphore:
            try:
                # Validate ownership
                connection = await self._validate_user_ownership(
                    session, connection_id, user_id, "sync_files"
                )

                # Use circuit breaker for provider
                from .retry import get_circuit_breaker_manager
                breaker = get_circuit_breaker_manager().get_or_create(
                    f"connector_{connection.connector_type}"
                )

                # Check if circuit is open
                if breaker.state == breaker.State.OPEN:
                    # Add to DLQ for retry later
                    await self._add_to_dlq(
                        session,
                        connection_id,
                        "sync",
                        {"selected_files": selected_files, "max_files": max_files},
                        ErrorCategory.TRANSIENT,
                        f"Circuit breaker open for {connection.connector_type}",
                    )
                    msg = f"Provider {connection.connector_type} is currently unavailable"
                    raise RuntimeError(msg)

                # TODO: Implement actual sync with provider
                # For now, just create a task ID
                from uuid import uuid4
                task_id = str(uuid4())
                logger.info(f"Started sync task {task_id} for connection {connection_id}")

                return task_id

            except Exception as e:
                # Categorize error and handle appropriately
                await self._handle_sync_error(
                    session,
                    connection_id,
                    {"selected_files": selected_files, "max_files": max_files},
                    e,
                )
                raise

    async def _handle_sync_error(
        self,
        session: AsyncSession,
        connection_id: UUID,
        payload: dict,
        error: Exception,
    ):
        """Handle sync errors by categorizing and potentially adding to DLQ.

        Args:
            session: Database session
            connection_id: Connection that failed
            payload: Operation payload
            error: The exception that occurred
        """
        error_category = categorize_error(error)

        if is_retryable(error_category):
            # Add to DLQ for later retry
            await self._add_to_dlq(
                session,
                connection_id,
                "sync",
                payload,
                error_category,
                str(error),
            )
        else:
            # Log non-retryable errors
            logger.error(
                f"Non-retryable sync error for connection {connection_id}: "
                f"{error_category.value} - {error}"
            )

    async def _add_to_dlq(
        self,
        session: AsyncSession,
        connection_id: UUID,
        operation_type: str,
        payload: dict,
        error_category: ErrorCategory,
        error_message: str,
    ):
        """Add failed operation to dead letter queue.

        Args:
            session: Database session
            connection_id: Connection ID
            operation_type: Type of operation that failed
            payload: Operation details
            error_category: Category of error
            error_message: Error message
        """
        from datetime import datetime, timedelta, timezone

        # Calculate next retry time with exponential backoff
        retry_config = RetryConfig()
        next_retry_delay = retry_config.get_delay(0)  # First retry
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=next_retry_delay)

        dlq_data = {
            "connection_id": connection_id,
            "operation_type": operation_type,
            "payload": payload,
            "error_category": error_category.value,
            "error_message": error_message,
            "next_retry_at": next_retry_at,
            "retry_count": 0,
            "status": "pending",
        }

        await add_to_dlq(session, dlq_data)

    async def process_dlq_retries(self, session: AsyncSession, batch_size: int = 10):
        """Process pending DLQ entries for retry.

        Args:
            session: Database session
            batch_size: Number of entries to process

        Returns:
            Number of entries processed
        """
        from langflow.services.database.models.connector import (
            get_retryable_dlq_entries,
            update_dlq_entry,
        )

        entries = await get_retryable_dlq_entries(session, limit=batch_size)
        processed = 0

        for entry in entries:
            try:
                # Update status to retrying
                await update_dlq_entry(
                    session,
                    entry.id,
                    {"status": "retrying", "last_retry_at": datetime.now(timezone.utc)},
                )

                # Attempt to process based on operation type
                if entry.operation_type == "sync":
                    # Get connection
                    connection = await db_get_connection(session, entry.connection_id)
                    if connection:
                        # Retry sync operation
                        await self.sync_files(
                            session,
                            entry.connection_id,
                            connection.user_id,
                            entry.payload.get("selected_files"),
                            entry.payload.get("max_files", 100),
                        )

                        # Mark as resolved
                        await update_dlq_entry(
                            session,
                            entry.id,
                            {"status": "resolved", "resolved_at": datetime.now(timezone.utc)},
                        )
                    else:
                        # Connection deleted, mark as failed
                        await update_dlq_entry(
                            session, entry.id, {"status": "failed", "error_message": "Connection not found"}
                        )

                processed += 1

            except Exception as e:
                # Update retry count and next retry time
                retry_count = entry.retry_count + 1
                retry_config = RetryConfig()

                if retry_count >= entry.max_retries:
                    # Max retries exceeded
                    await update_dlq_entry(
                        session,
                        entry.id,
                        {
                            "status": "failed",
                            "retry_count": retry_count,
                            "error_message": str(e),
                        },
                    )
                else:
                    # Schedule next retry
                    next_delay = retry_config.get_delay(retry_count)
                    next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=next_delay)

                    await update_dlq_entry(
                        session,
                        entry.id,
                        {
                            "status": "pending",
                            "retry_count": retry_count,
                            "next_retry_at": next_retry_at,
                            "error_message": str(e),
                        },
                    )

        return processed

    async def get_connector_instance(self, connection: ConnectorConnection) -> BaseConnector:
        """Get an initialized connector instance with decrypted config.

        Args:
            connection: Connection to instantiate

        Returns:
            Initialized connector instance
        """
        # Decrypt config before passing to connector
        config = connection.config.copy()
        if config.get("client_secret"):
            config["client_secret"] = decrypt_sensitive_field(config["client_secret"])
        if config.get("api_key"):
            config["api_key"] = decrypt_sensitive_field(config["api_key"])

        # TODO: Implement with provider classes
        msg = "Connector instantiation not yet implemented"
        raise NotImplementedError(msg)
