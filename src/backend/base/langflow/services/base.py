from abc import ABC


class Service(ABC):
    name: str
    ready: bool = False

    def teardown(self):
        pass

    def set_ready(self):
        self.ready = True
