"""External Integration Service implementation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from langflow.services.base import Service


class ExternalIntegrationService(Service):
    """Implementation of external integration service."""

    name = "external_integration_service"

    def __init__(
        self,
        genesis_api_url: str = "http://localhost:8000",
        notification_api_url: str = "http://localhost:8001",
        activity_log_url: str = "http://localhost:8002",
        api_key: str = "",
        client_id: str = "genesis_studio_backend",
    ):
        super().__init__()
        self.genesis_api_url = genesis_api_url
        self.notification_api_url = notification_api_url
        self.activity_log_url = activity_log_url
        self.api_key = api_key
        self.client_id = client_id
        self._client = None

    async def initialize(self):
        """Initialize the service - called by Langflow service manager."""
        await self.setup()

    async def setup(self):
        """Initialize the service."""
        timeout = aiohttp.ClientTimeout(total=120.0)
        self._client = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Client-ID": self.client_id,
                "Content-Type": "application/json",
            },
        )
        self.set_ready()

    async def teardown(self):
        """Cleanup resources."""
        if self._client:
            await self._client.close()

    async def sync_user_data(self, user_id: str) -> Dict[str, Any]:
        """Sync user data with external systems."""
        if not self.ready:
            await self.setup()

        try:
            # Fetch user data from Genesis API
            async with self._client.get(
                f"{self.genesis_api_url}/auth/api/v1/users/{user_id}/profile"
            ) as response:
                response.raise_for_status()
                user_data = (await response.json())["data"]

            # Log the sync activity
            await self.log_activity(
                user_id, "user_data_sync", {"timestamp": datetime.utcnow().isoformat()}
            )

            return {
                "user_id": user_id,
                "profile": user_data,
                "sync_timestamp": datetime.utcnow().isoformat(),
                "status": "success",
            }

        except aiohttp.ClientResponseError as e:
            return {
                "user_id": user_id,
                "error": f"HTTP {e.status}: {e.message}",
                "status": "error",
            }
        except Exception as e:
            return {"user_id": user_id, "error": str(e), "status": "error"}

    async def send_notification(
        self, user_id: str, message: str, channel: str = "email"
    ) -> bool:
        """Send notification to user via external service."""
        if not self.ready:
            await self.setup()

        try:
            payload = {
                "user_id": user_id,
                "message": message,
                "channel": channel,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "langflow_service",
            }

            response = await self._client.post(
                f"{self.notification_api_url}/notifications/send", json=payload
            )
            response.raise_for_status()

            # Log notification activity
            await self.log_activity(
                user_id,
                "notification_sent",
                {"channel": channel, "message_preview": message[:50]},
            )

            return True

        except Exception as e:
            # Log failed notification
            await self.log_activity(
                user_id, "notification_failed", {"error": str(e), "channel": channel}
            )
            return False

    async def log_activity(
        self, user_id: str, activity: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log user activity to external system."""
        if not self.ready:
            await self.setup()

        try:
            log_entry = {
                "user_id": user_id,
                "activity": activity,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "langflow_service",
                "metadata": metadata or {},
            }

            response = await self._client.post(
                f"{self.activity_log_url}/logs", json=log_entry
            )
            response.raise_for_status()

            result = response.json()
            return result.get("log_id", "unknown")

        except Exception:
            # If external logging fails, return a local identifier
            return f"local_{datetime.utcnow().timestamp()}"

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """Get user permissions from external system."""
        if not self.ready:
            await self.setup()

        try:
            response = await self._client.get(
                f"{self.genesis_api_url}/auth/api/v1/users/{user_id}/permissions"
            )
            response.raise_for_status()

            permissions_data = response.json()["data"]
            permissions = permissions_data.get("permissions", [])

            # Log permission check
            await self.log_activity(
                user_id, "permissions_checked", {"permission_count": len(permissions)}
            )

            return permissions

        except Exception as e:
            # Return default permissions on error
            await self.log_activity(
                user_id, "permissions_check_failed", {"error": str(e)}
            )
            return ["basic_access"]

    async def validate_workflow_access(self, user_id: str, workflow_id: str) -> bool:
        """Validate if user has access to a specific workflow."""
        if not self.ready:
            await self.setup()

        try:
            # Get user permissions
            permissions = await self.get_user_permissions(user_id)

            # Check for admin or workflow-specific permissions
            has_access = (
                "admin" in permissions
                or "workflow_admin" in permissions
                or f"workflow_{workflow_id}" in permissions
                or "all_workflows" in permissions
            )

            # Log access check
            await self.log_activity(
                user_id,
                "workflow_access_check",
                {
                    "workflow_id": workflow_id,
                    "access_granted": has_access,
                    "user_permissions": permissions,
                },
            )

            return has_access

        except Exception as e:
            # Log error and deny access by default
            await self.log_activity(
                user_id,
                "workflow_access_check_failed",
                {"workflow_id": workflow_id, "error": str(e)},
            )
            return False

    async def get_service_status(self) -> Dict[str, Any]:
        """Get status of external integrations."""
        status = {
            "service_ready": self.ready,
            "genesis_api": "unknown",
            "notification_api": "unknown",
            "activity_log_api": "unknown",
            "timestamp": datetime.utcnow().isoformat(),
        }

        if not self.ready:
            return status

        # Check Genesis API
        try:
            response = await self._client.get(
                f"{self.genesis_api_url}/health", timeout=5.0
            )
            status["genesis_api"] = (
                "healthy" if response.status_code == 200 else "unhealthy"
            )
        except Exception:
            status["genesis_api"] = "unreachable"

        # Check Notification API
        try:
            response = await self._client.get(
                f"{self.notification_api_url}/health", timeout=5.0
            )
            status["notification_api"] = (
                "healthy" if response.status_code == 200 else "unhealthy"
            )
        except Exception:
            status["notification_api"] = "unreachable"

        # Check Activity Log API
        try:
            response = await self._client.get(
                f"{self.activity_log_url}/health", timeout=5.0
            )
            status["activity_log_api"] = (
                "healthy" if response.status_code == 200 else "unhealthy"
            )
        except Exception:
            status["activity_log_api"] = "unreachable"

        return status


# Example usage component that uses the service
class ServiceUsingComponent:
    """Example component that demonstrates service usage."""

    def __init__(self, external_service: ExternalIntegrationService):
        self.external_service = external_service

    async def process_user_workflow(
        self, user_id: str, workflow_id: str
    ) -> Dict[str, Any]:
        """Process a workflow with external service integration."""
        # Check user access
        has_access = await self.external_service.validate_workflow_access(
            user_id, workflow_id
        )

        if not has_access:
            await self.external_service.send_notification(
                user_id, f"Access denied for workflow {workflow_id}", "email"
            )
            return {"status": "access_denied", "workflow_id": workflow_id}

        # Sync user data
        user_data = await self.external_service.sync_user_data(user_id)

        # Log workflow execution
        await self.external_service.log_activity(
            user_id,
            "workflow_executed",
            {"workflow_id": workflow_id, "user_data_sync": user_data["status"]},
        )

        # Send completion notification
        await self.external_service.send_notification(
            user_id, f"Workflow {workflow_id} completed successfully", "email"
        )

        return {
            "status": "success",
            "workflow_id": workflow_id,
            "user_data": user_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
