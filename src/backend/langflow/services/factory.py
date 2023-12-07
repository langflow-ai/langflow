from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.base import Service


class ServiceFactory:
    def __init__(self, service_class):
        self.service_class = service_class

    def create(self, *args, **kwargs) -> "Service":
        raise NotImplementedError
