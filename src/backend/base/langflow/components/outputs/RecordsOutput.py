from langflow.custom import Component
from langflow.schema import Data
from langflow.template import Input, Output


class DataOutput(Component):
    display_name = "Data Output"
    description = "Display Data as a Table"

    inputs = [
        Input(name="input_value", type=Data, display_name="Data Input"),
    ]
    outputs = [
        Output(display_name="Data", name="data", method="data_response"),
    ]

    def data_response(self) -> Data:
        self.status = self.input_value
        return self.input_value
