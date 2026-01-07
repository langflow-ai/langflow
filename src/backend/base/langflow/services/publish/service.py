from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


IDType = str | UUID | None
IDTypeStrict = str | UUID


class PublishService(Service):
    name = "publish_service"

    def __init__(self, settings_service: SettingsService):
        from langflow.services.publish.utils import add_trailing_slash

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
        publish_key: str,
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
        ) -> str:
        """Publishes a flow to the storage provider."""
        raise NotImplementedError

    @abstractmethod
    async def delete_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        publish_key: str,
        ) -> str:
        """Deletes a published flow from the storage provider."""
        raise NotImplementedError
