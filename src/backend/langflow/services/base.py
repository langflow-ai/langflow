from abc import ABC


class Service(ABC):
    name: str

    def teardown(self):
        pass
