from langflow.services.database.models.flow_publish.model import PublishProviderEnum
from langflow.services.factory import ServiceFactory
from langflow.services.publish.s3 import S3PublishService
from langflow.services.settings.service import SettingsService


class PublishServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(S3PublishService)

    def create(self, settings_service: SettingsService):
        publish_backend = settings_service.settings.publish_backend

        if publish_backend.lower() == PublishProviderEnum.S3.value:
            return S3PublishService(settings_service)

        msg = f"Publish backend {publish_backend} is not supported"
        raise ValueError(msg)
