import json

from langflow.custom import Component
from langflow.inputs import BoolInput, StrInput
from langflow.schema import Data
from langflow.template import Output


class TextToData(Component):
    inputs = [
        StrInput(name="text_data", is_list=True),
        BoolInput(name="is_json", info="Parse text_data as json and fill the data object."),
    ]
    outputs = [
        Output(name="from_text", display_name="From text", method="create_data"),
    ]

    def _to_data(self, text: str) -> Data:
        if self.is_json:
            return Data(data=json.loads(text))
        return Data(text=text)

    def create_data(self) -> list[Data]:
        return [self._to_data(t) for t in self.text_data]
