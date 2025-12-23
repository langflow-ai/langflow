from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class PublishService(Service):
    name = "publish_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

        self.prefix = settings_service.settings.publish_backend_prefix
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        self.set_ready()

    @abstractmethod
    async def publish_flow(
        self,
        user_id: str,
        flow_id: str,
        flow_data: str,
        version_id: str | None = None,
    ) -> str:
        """Publishes a flow to the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def get_flow(
        self,
        user_id: str,
        flow_id: str,
        version_id: str | None = None,
    ) -> str:
        """Retrieves a published flow from the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def publish_project(
        self,
        user_id: str,
        project_id: str,
        manifest: dict,
        version_id: str | None = None,
    ) -> str:
        """Publishes a project manifest to the storage provider."""
        raise NotImplementedError
