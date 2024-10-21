from typing import Any


class BasePlugin:
    def initialize(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def get(self) -> Any:
        pass


class CallbackPlugin(BasePlugin):
    def get_callback(self, _id=None):
        pass
