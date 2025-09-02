import random

from lfx.custom import CustomComponent


class TestComponent(CustomComponent):
    def refresh_values(self):
        # This is a function that will be called every time the component is updated
        # and should return a list of random strings
        return [f"Random {random.randint(1, 100)}" for _ in range(5)]  # noqa: S311

    def build_config(self):
        return {"param": {"display_name": "Param", "options": self.refresh_values}}

    def build(self, param: int):
        return param
