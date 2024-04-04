from typing import Any


class BasePlugin:
    def initialize(self):
        pass

    def teardown(self):
        pass

    def get(self) -> Any:
        pass


class CallbackPlugin(BasePlugin):
    def get_callback(self, _id=None):
        pass
