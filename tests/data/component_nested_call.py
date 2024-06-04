from langflow.custom import Component
from langflow.template.field.base import Input, Output
from random import randint


class MultipleOutputsComponent(Component):
    inputs = [
        Input(display_name="Input", name="input", field_type=str),
        Input(display_name="Number", name="number", field_type=int),
    ]
    outputs = [
        Output(name="Certain Output", method="certain_output"),
        Output(name="Other Output", method="other_output"),
    ]

    def certain_output(self) -> int:
        return randint(0, self.number)

    def other_output(self) -> int:
        return self.certain_output()
