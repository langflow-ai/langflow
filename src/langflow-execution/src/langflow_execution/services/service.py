from abc import ABC, abstractmethod


class Service(ABC):
    """Abstract base class for all services.

    Services are responsible for initializing, managing, and providing access to core execution services.
    """

    name: str
    ready: bool = False

    @abstractmethod
    async def teardown(self) -> None:
        pass

    def set_ready(self) -> None:
        self.ready = True
