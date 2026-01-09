from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from langflow.services.base import Service
from langflow.services.publish.utils import IDType, add_trailing_slash

if TYPE_CHECKING:
    from langflow.services.publish.schema import PublishedFlowMetadata
    from langflow.services.settings.service import SettingsService



class PublishService(Service):
    name = "publish_service"

    def __init__(self, settings_service: SettingsService):

        self.settings_service = settings_service

        self.prefix = settings_service.settings.publish_backend_prefix
        self.prefix = add_trailing_slash(self.prefix)
        self.deploy_prefix = settings_service.settings.publish_backend_prefix_deploy
        self.deploy_prefix = add_trailing_slash(self.deploy_prefix)

        self.set_ready()

    #########################################################
    # Flow
    #########################################################
    @abstractmethod
    async def get_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        key: PublishedFlowMetadata,
        ) -> str:
        """Retrieves a published flow from the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def put_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        flow_blob: dict,
        publish_tag: str | None,
        ) -> PublishedFlowMetadata:
        """Publishes a flow to the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def delete_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        key: PublishedFlowMetadata,
        ) -> str | None:
        """Deletes a published flow from the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def list_flow_versions(
        self,
        user_id: IDType,
        flow_id: IDType,
        ) -> list[PublishedFlowMetadata] | None:
        """List published versions of the given flow."""
        raise NotImplementedError
