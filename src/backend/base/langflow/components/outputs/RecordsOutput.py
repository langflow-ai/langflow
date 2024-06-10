from langflow.custom import Component
from langflow.schema import Record
from langflow.template import Input, Output


class RecordsOutput(Component):
    display_name = "Records Output"
    description = "Display Records as a Table"

    inputs = [
        Input(name="input_value", type=Record, display_name="Record Input"),
    ]
    outputs = [
        Output(display_name="Record", name="record", method="record_response"),
    ]

    def record_response(self) -> Record:
        self.status = self.input_value
        return self.input_value
