"""Base service factory classes for lfx package."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.services.base import Service


class ServiceFactory:
    """Base service factory class.

    Concrete factories may add dependency inference and other construction
    logic on top of this contract.
    """

    def __init__(self, service_class: type["Service"] | None = None) -> None:
        self.service_class = service_class
        self.dependencies: list = []

    def create(self, *args, **kwargs) -> "Service":
        """Create a service instance.

        Subclasses typically override this. The default implementation
        instantiates ``service_class`` when one was provided.
        """
        if self.service_class is None:
            msg = "service_class is required"
            raise ValueError(msg)
        return self.service_class(*args, **kwargs)
