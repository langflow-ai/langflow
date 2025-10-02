from lfx.log.logger import logger
from lfx.services.settings.service import SettingsService
from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.session.service import SessionService
from langflow.services.storage.local import LocalStorageService
from langflow.services.storage.service import StorageService

_S3StorageService = None


class StorageServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(
            StorageService,
        )

    @override
    def create(self, session_service: SessionService, settings_service: SettingsService):
        storage_type = settings_service.settings.storage_type

        storage_type_lc = storage_type.lower()
        if storage_type_lc == "local":
            return LocalStorageService(session_service, settings_service)
        if storage_type_lc == "s3":
            global _S3StorageService
            if _S3StorageService is None:
                from lfx.services.storage.s3 import S3StorageService

                _S3StorageService = S3StorageService
            return _S3StorageService(settings_service=settings_service, session_service=session_service)
        logger.warning(f"Storage type {storage_type} not supported. Using local storage.")
        return LocalStorageService(session_service, settings_service)
