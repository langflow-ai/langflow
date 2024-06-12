from langflow.custom import Component
from langflow.schema import Data
from langflow.template import Input, Output


class RecordsOutput(Component):
    display_name = "Records Output"
    description = "Display Records as a Table"

    inputs = [
        Input(name="input_value", type=Data, display_name="Data Input"),
    ]
    outputs = [
        Output(display_name="Data", name="record", method="record_response"),
    ]

    def record_response(self) -> Data:
        self.status = self.input_value
        return self.input_value
