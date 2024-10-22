from loguru import logger

from langflow.services.factory import ServiceFactory
from langflow.services.session.service import SessionService
from langflow.services.settings.service import SettingsService
from langflow.services.storage.service import StorageService


class StorageServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(
            StorageService,
        )

    def create(self, session_service: SessionService, settings_service: SettingsService):
        storage_type = settings_service.settings.storage_type
        if storage_type.lower() == "local":
            from .local import LocalStorageService

            return LocalStorageService(session_service, settings_service)
        if storage_type.lower() == "s3":
            from .s3 import S3StorageService

            return S3StorageService(session_service, settings_service)
        logger.warning(f"Storage type {storage_type} not supported. Using local storage.")
        from .local import LocalStorageService

        return LocalStorageService(session_service, settings_service)
