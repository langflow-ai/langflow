"""Factory for creating PALookupService instances."""

from typing import override
from langflow.services.factory import ServiceFactory
from .service import PALookupService


class PALookupServiceFactory(ServiceFactory):
    """Factory for creating PALookupService instances."""

    name = "pa_lookup_service"

    def __init__(self):
        """Initialize the PALookupServiceFactory."""
        super().__init__(PALookupService)

    @override
    def create(self, **kwargs):
        """Create a new PALookupService instance."""
        return PALookupService()
