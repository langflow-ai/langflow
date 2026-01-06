from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

from langflow.services.base import Service
from langflow.services.database.models.flow_publish.model import PublishProviderEnum

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


IDType = str | UUID | None
IDTypeStrict = str | UUID


class PublishService(Service):
    name = "publish_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

        self.prefix = settings_service.settings.publish_backend_prefix
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        self.set_ready()

    #########################################################
    # Flow
    #########################################################
    @abstractmethod
    async def get_flow(
        self,
        publish_key: str
    ) -> str:
        """Retrieves a published flow from the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def put_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        flow_blob: dict,
        publish_tag: str | None
    ) -> str:
        """Publishes a flow to the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def delete_flow(
        self,
        publish_key: str
    ) -> str:
        """Deletes a published flow from the storage provider."""
        raise NotImplementedError

    #########################################################
    # Project
    #########################################################
    @abstractmethod
    async def get_project(
        self,
        user_id: IDType,
        project_id: IDType,
    ) -> str:
        """Retrieves a published project from the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def put_project(
        self,
        user_id: IDType,
        project_id: IDType,
        manifest: dict,
    ) -> str:
        """Publishes a project manifest to the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def delete_project(
        self,
        user_id: IDType,
        project_id: IDType,
    ) -> str:
        """Deletes a published project from the storage provider."""
        raise NotImplementedError
