import json
import uuid
import aiofiles
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from utils.logging_config import get_logger

logger = get_logger(__name__)

from .base import BaseConnector
from .google_drive import GoogleDriveConnector
from .sharepoint import SharePointConnector
from .onedrive import OneDriveConnector


@dataclass
class ConnectionConfig:
    """Configuration for a connector connection"""

    connection_id: str
    connector_type: str  # "google_drive", "box", etc.
    name: str  # User-friendly name
    config: Dict[str, Any]  # Connector-specific config
    user_id: Optional[str] = None  # For multi-tenant support
    created_at: datetime = None
    last_sync: Optional[datetime] = None
    is_active: bool = True

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class ConnectionManager:
    """Manages multiple connector connections with persistence"""

    def __init__(self, connections_file: str = "connections.json"):
        self.connections_file = Path(connections_file)
        self.connections: Dict[str, ConnectionConfig] = {}
        self.active_connectors: Dict[str, BaseConnector] = {}

    async def load_connections(self):
        """Load connections from persistent storage"""
        if self.connections_file.exists():
            async with aiofiles.open(self.connections_file, "r") as f:
                data = json.loads(await f.read())

            for conn_data in data.get("connections", []):
                # Convert datetime strings back to datetime objects
                if conn_data.get("created_at"):
                    conn_data["created_at"] = datetime.fromisoformat(
                        conn_data["created_at"]
                    )
                if conn_data.get("last_sync"):
                    conn_data["last_sync"] = datetime.fromisoformat(
                        conn_data["last_sync"]
                    )

                config = ConnectionConfig(**conn_data)
                self.connections[config.connection_id] = config

            # Now that connections are loaded, clean up duplicates
            await self.cleanup_duplicate_connections(remove_duplicates=True)

    async def save_connections(self):
        """Save connections to persistent storage"""
        data = {"connections": []}

        for config in self.connections.values():
            conn_data = asdict(config)
            # Convert datetime objects to strings
            if conn_data.get("created_at"):
                conn_data["created_at"] = conn_data["created_at"].isoformat()
            if conn_data.get("last_sync"):
                conn_data["last_sync"] = conn_data["last_sync"].isoformat()
            data["connections"].append(conn_data)

        async with aiofiles.open(self.connections_file, "w") as f:
            await f.write(json.dumps(data, indent=2))

    async def _get_existing_connection(
        self, connector_type: str, user_id: Optional[str] = None
    ) -> Optional[ConnectionConfig]:
        """Find existing active connection for the same connector type and user"""
        for connection in self.connections.values():
            if (
                connection.connector_type == connector_type
                and connection.user_id == user_id
                and connection.is_active
            ):
                return connection
        return None

    async def cleanup_duplicate_connections(self, remove_duplicates=False):
        """
        Clean up duplicate connections, keeping only the most recent connection 
        per provider per user
        
        Args:
            remove_duplicates: If True, physically removes duplicates from connections.json
                            If False (default), just deactivates them
        """
        logger.info("Starting cleanup of duplicate connections")
        
        # Group connections by (connector_type, user_id)
        grouped_connections = {}
        
        for connection_id, connection in self.connections.items():
            if not connection.is_active:
                continue  # Skip inactive connections
                
            key = (connection.connector_type, connection.user_id)
            
            if key not in grouped_connections:
                grouped_connections[key] = []
            
            grouped_connections[key].append((connection_id, connection))
        
        # For each group, keep only the most recent connection
        connections_to_remove = []
        
        for (connector_type, user_id), connections in grouped_connections.items():
            if len(connections) <= 1:
                continue  # No duplicates
                
            logger.info(f"Found {len(connections)} duplicate connections for {connector_type}, user {user_id}")
            
            # Sort by created_at, keep the most recent
            connections.sort(key=lambda x: x[1].created_at, reverse=True)
            
            # Keep the first (most recent), remove/deactivate the rest
            for connection_id, connection in connections[1:]:
                connections_to_remove.append((connection_id, connection))
                logger.info(f"Marking connection {connection_id} for {'removal' if remove_duplicates else 'deactivation'}")
        
        # Remove or deactivate duplicate connections
        for connection_id, connection in connections_to_remove:
            if remove_duplicates:
                await self.delete_connection(connection_id)  # Handles token cleanup
            else:
                await self.deactivate_connection(connection_id)
        
        action = "Removed" if remove_duplicates else "Deactivated"
        logger.info(f"Cleanup complete. {action} {len(connections_to_remove)} duplicate connections")
        return len(connections_to_remove)
    
    async def update_connection(
        self,
        connection_id: str,
        connector_type: str = None,
        name: str = None,
        config: Dict[str, Any] = None,
        user_id: str = None,
    ) -> bool:
        """Update an existing connection configuration"""
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]

        # Check if this update is adding authentication and webhooks are configured
        should_setup_webhook = (
            config is not None
            and config.get("token_file")
            and config.get("webhook_url")  # Only if webhook URL is configured
            and not connection.config.get("webhook_channel_id")
            and connection.is_active
        )

        # Update fields if provided
        if connector_type is not None:
            connection.connector_type = connector_type
        if name is not None:
            connection.name = name
        if config is not None:
            connection.config = config
        if user_id is not None:
            connection.user_id = user_id

        await self.save_connections()

        # Setup webhook subscription if this connection just got authenticated with webhook URL
        if should_setup_webhook:
            await self._setup_webhook_for_new_connection(connection_id, connection)

        return True

    async def create_connection(
        self,
        connector_type: str,
        name: str,
        config: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> str:
        """Create a new connection configuration, ensuring only one per provider per user"""
        
        # Check if we already have an active connection for this provider and user
        existing_connection = await self._get_existing_connection(connector_type, user_id)
        
        if existing_connection:
            # Check if the existing connection has a valid token
            try:
                connector = self._create_connector(existing_connection)
                if await connector.authenticate():
                    logger.info(
                        f"Using existing valid connection for {connector_type}",
                        connection_id=existing_connection.connection_id
                    )
                    # Update the existing connection with new config if needed
                    if config != existing_connection.config:
                        logger.info("Updating existing connection config")
                        await self.update_connection(
                            existing_connection.connection_id,
                            config=config
                        )
                    return existing_connection.connection_id
            except Exception as e:
                logger.warning(
                    f"Existing connection authentication failed: {e}",
                    connection_id=existing_connection.connection_id
                )
                # If authentication fails, we'll create a new connection and clean up the old one
        
        # Create new connection
        connection_id = str(uuid.uuid4())
        
        connection_config = ConnectionConfig(
            connection_id=connection_id,
            connector_type=connector_type,
            name=name,
            config=config,
            user_id=user_id,
        )

        self.connections[connection_id] = connection_config
        
        # Clean up duplicates (will keep the newest, which is the one we just created)
        await self.cleanup_duplicate_connections(remove_duplicates=True)
        
        await self.save_connections()
        return connection_id

    async def list_connections(
        self, user_id: Optional[str] = None, connector_type: Optional[str] = None
    ) -> List[ConnectionConfig]:
        """List connections, optionally filtered by user or connector type"""
        connections = list(self.connections.values())

        if user_id is not None:
            connections = [c for c in connections if c.user_id == user_id]

        if connector_type is not None:
            connections = [c for c in connections if c.connector_type == connector_type]

        return connections

    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection"""
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]

        # Clean up token file if it exists
        if connection.config.get("token_file"):
            token_file = Path(connection.config["token_file"])
            if token_file.exists():
                try:
                    token_file.unlink()
                    logger.info(f"Deleted token file: {token_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete token file {token_file}: {e}")

        # Clean up active connector if exists
        if connection_id in self.active_connectors:
            connector = self.active_connectors[connection_id]
            # Try to cleanup subscriptions if applicable
            try:
                if (
                    hasattr(connector, "webhook_channel_id")
                    and connector.webhook_channel_id
                ):
                    await connector.cleanup_subscription(connector.webhook_channel_id)
            except:
                pass  # Best effort cleanup

            del self.active_connectors[connection_id]

        del self.connections[connection_id]
        await self.save_connections()
        return True

    async def get_connector(self, connection_id: str) -> Optional[BaseConnector]:
        """Get an active connector instance"""
        # Return cached connector if available
        if connection_id in self.active_connectors:
            connector = self.active_connectors[connection_id]
            if connector.is_authenticated:
                return connector
            else:
                # Remove unauthenticated connector from cache
                del self.active_connectors[connection_id]

        # Try to create and authenticate connector
        connection_config = self.connections.get(connection_id)
        if not connection_config or not connection_config.is_active:
            return None

        connector = self._create_connector(connection_config)
        if await connector.authenticate():
            self.active_connectors[connection_id] = connector

            # Setup webhook subscription if not already set up
            await self._setup_webhook_if_needed(
                connection_id, connection_config, connector
            )

            return connector

        return None

    def get_available_connector_types(self) -> Dict[str, Dict[str, str]]:
        """Get available connector types with their metadata"""
        return {
            "google_drive": {
                "name": GoogleDriveConnector.CONNECTOR_NAME,
                "description": GoogleDriveConnector.CONNECTOR_DESCRIPTION,
                "icon": GoogleDriveConnector.CONNECTOR_ICON,
                "available": self._is_connector_available("google_drive"),
            },
            "sharepoint": {
                "name": SharePointConnector.CONNECTOR_NAME,
                "description": SharePointConnector.CONNECTOR_DESCRIPTION,
                "icon": SharePointConnector.CONNECTOR_ICON,
                "available": self._is_connector_available("sharepoint"),
            },
            "onedrive": {
                "name": OneDriveConnector.CONNECTOR_NAME,
                "description": OneDriveConnector.CONNECTOR_DESCRIPTION,
                "icon": OneDriveConnector.CONNECTOR_ICON,
                "available": self._is_connector_available("onedrive"),
            },
        }

    def _is_connector_available(self, connector_type: str) -> bool:
        """Check if a connector type is available (has required env vars)"""
        try:
            temp_config = ConnectionConfig(
                connection_id="temp",
                connector_type=connector_type,
                name="temp",
                config={},
            )
            connector = self._create_connector(temp_config)
            # Try to get credentials to check if env vars are set
            connector.get_client_id()
            connector.get_client_secret()
            return True
        except (ValueError, NotImplementedError):
            return False

    def _create_connector(self, config: ConnectionConfig) -> BaseConnector:
        """Factory method to create connector instances"""
        if config.connector_type == "google_drive":
            return GoogleDriveConnector(config.config)
        elif config.connector_type == "sharepoint":
            return SharePointConnector(config.config)
        elif config.connector_type == "onedrive":
            return OneDriveConnector(config.config)
        elif config.connector_type == "box":
            # Future: BoxConnector(config.config)
            raise NotImplementedError("Box connector not implemented yet")
        elif config.connector_type == "dropbox":
            # Future: DropboxConnector(config.config)
            raise NotImplementedError("Dropbox connector not implemented yet")
        else:
            raise ValueError(f"Unknown connector type: {config.connector_type}")

    async def update_last_sync(self, connection_id: str):
        """Update the last sync timestamp for a connection"""
        if connection_id in self.connections:
            self.connections[connection_id].last_sync = datetime.now()
            await self.save_connections()

    async def activate_connection(self, connection_id: str) -> bool:
        """Activate a connection"""
        if connection_id in self.connections:
            self.connections[connection_id].is_active = True
            await self.save_connections()
            return True
        return False

    async def deactivate_connection(self, connection_id: str) -> bool:
        """Deactivate a connection"""
        if connection_id in self.connections:
            self.connections[connection_id].is_active = False
            await self.save_connections()

            # Remove from active connectors
            if connection_id in self.active_connectors:
                del self.active_connectors[connection_id]

            return True
        return False
    
    async def get_connection(self, connection_id: str) -> Optional[ConnectionConfig]:
        """Get connection configuration"""
        return self.connections.get(connection_id)

    async def get_connection_by_webhook_id(
        self, webhook_id: str
    ) -> Optional[ConnectionConfig]:
        """Find a connection by its webhook/subscription ID"""
        for connection in self.connections.values():
            # Check if the webhook ID is stored in the connection config
            if connection.config.get("webhook_channel_id") == webhook_id:
                return connection
            # Also check for subscription_id (alternative field name)
            if connection.config.get("subscription_id") == webhook_id:
                return connection
        return None

    async def _setup_webhook_if_needed(
        self,
        connection_id: str,
        connection_config: ConnectionConfig,
        connector: BaseConnector,
    ):
        """Setup webhook subscription if not already configured"""
        # Check if webhook is already set up
        if connection_config.config.get(
            "webhook_channel_id"
        ) or connection_config.config.get("subscription_id"):
            logger.info(
                "Webhook subscription already exists", connection_id=connection_id
            )
            return

        # Check if webhook URL is configured
        webhook_url = connection_config.config.get("webhook_url")
        if not webhook_url:
            logger.info(
                "No webhook URL configured, skipping subscription setup",
                connection_id=connection_id,
            )
            return

        try:
            logger.info("Setting up webhook subscription", connection_id=connection_id)
            subscription_id = await connector.setup_subscription()

            # Store the subscription and resource IDs in connection config
            connection_config.config["webhook_channel_id"] = subscription_id
            connection_config.config["subscription_id"] = (
                subscription_id  # Alternative field
            )
            if getattr(connector, "webhook_resource_id", None):
                connection_config.config["resource_id"] = connector.webhook_resource_id

            # Save updated connection config
            await self.save_connections()

            logger.info(
                "Successfully set up webhook subscription",
                connection_id=connection_id,
                subscription_id=subscription_id,
            )

        except Exception as e:
            logger.error(
                "Failed to setup webhook subscription",
                connection_id=connection_id,
                error=str(e),
            )
            # Don't fail the entire connection setup if webhook fails

    async def _setup_webhook_for_new_connection(
        self, connection_id: str, connection_config: ConnectionConfig
    ):
        """Setup webhook subscription for a newly authenticated connection"""
        try:
            logger.info(
                "Setting up subscription for newly authenticated connection",
                connection_id=connection_id,
            )

            # Create and authenticate connector
            connector = self._create_connector(connection_config)
            if not await connector.authenticate():
                logger.error(
                    "Failed to authenticate connector for webhook setup",
                    connection_id=connection_id,
                )
                return

            # Setup subscription
            subscription_id = await connector.setup_subscription()

            # Store the subscription and resource IDs in connection config
            connection_config.config["webhook_channel_id"] = subscription_id
            connection_config.config["subscription_id"] = subscription_id
            if getattr(connector, "webhook_resource_id", None):
                connection_config.config["resource_id"] = connector.webhook_resource_id

            # Save updated connection config
            await self.save_connections()

            logger.info(
                "Successfully set up webhook subscription",
                connection_id=connection_id,
                subscription_id=subscription_id,
            )

        except Exception as e:
            logger.error(
                "Failed to setup webhook subscription for new connection",
                connection_id=connection_id,
                error=str(e),
            )
            # Don't fail the connection setup if webhook fails
