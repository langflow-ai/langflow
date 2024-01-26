from abc import abstractmethod
from typing import TYPE_CHECKING

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.session.service import SessionService


class StorageService(Service):
    name = "storage_service"

    def __init__(self, session_service: "SessionService"):
        self.session_service = session_service
        self.set_ready()

    def set_ready(self):
        self.ready = True

    @abstractmethod
    def save_file(self, folder: str, file_name: str, data):
        pass

    @abstractmethod
    def get_file(self, folder: str, file_name: str):
        pass

    @abstractmethod
    def list_files(self, folder: str):
        pass

    @abstractmethod
    def delete_file(self, folder: str, file_name: str):
        pass

    def teardown(self):
        pass
