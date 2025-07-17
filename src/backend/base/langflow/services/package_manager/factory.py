"""Factory for package manager service."""

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from .service import PackageManagerService


class PackageManagerServiceFactory(ServiceFactory):
    name = "package_manager_service"
    
    def __init__(self):
        super().__init__(PackageManagerService)
    
    @override
    def create(self):
        return PackageManagerService()