import random

from langflow.custom import CustomComponent
from langflow.field_typing import Input


# This is a custom component that will be used in the tests
class TestComponent(CustomComponent):
    def refresh_values(self):
        # This is a function that will be called every time the component is updated
        # and should return a list of random strings
        return [f"Random {random.randint(1, 100)}" for _ in range(5)]

    def build_config(self):
        return {"param": Input(display_name="Param", options=self.refresh_values)}

    def build(self, param: int):
        return param
