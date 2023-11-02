from typing import Any


class BasePlugin:
    def initialize(self):
        pass

    def teardown(self):
        pass

    def get(self) -> Any:
        pass
