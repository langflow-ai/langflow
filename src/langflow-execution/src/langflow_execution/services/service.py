from abc import ABC, abstractmethod


class Service(ABC):
    name: str
    ready: bool = False

    @abstractmethod
    async def teardown(self) -> None:
        pass

    def set_ready(self) -> None:
        self.ready = True
