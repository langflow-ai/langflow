import random

from langflow.custom import CustomComponent
from langflow.field_typing import TemplateField


class TestComponent(CustomComponent):
    def refresh_values(self):
        # This is a function that will be called every time the component is updated
        # and should return a list of random strings
        return [f"Random {random.randint(1, 100)}" for _ in range(5)]

    def build_config(self):
        return {"param": TemplateField(display_name="Param", options=self.refresh_values)}

    def build(self, param: int):
        return param
