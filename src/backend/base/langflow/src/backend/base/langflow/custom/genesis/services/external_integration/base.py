"""Base class for external integration service."""

import abc
from typing import Any, Dict, List, Optional

from langflow.services.base import Service


class ExternalIntegrationServiceBase(Service):
    """Abstract base class for external integration service."""

    name = "external_integration_service"

    @abc.abstractmethod
    async def sync_user_data(self, user_id: str) -> Dict[str, Any]:
        """Sync user data with external systems."""

    @abc.abstractmethod
    async def send_notification(
        self, user_id: str, message: str, channel: str = "email"
    ) -> bool:
        """Send notification to user via external service."""

    @abc.abstractmethod
    async def log_activity(
        self, user_id: str, activity: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log user activity to external system."""

    @abc.abstractmethod
    async def get_user_permissions(self, user_id: str) -> List[str]:
        """Get user permissions from external system."""

    @abc.abstractmethod
    async def validate_workflow_access(self, user_id: str, workflow_id: str) -> bool:
        """Validate if user has access to a specific workflow."""

    @abc.abstractmethod
    async def get_service_status(self) -> Dict[str, Any]:
        """Get status of external integrations."""
