from json import JSONDecodeError
import json
import jq
from json_repair import repair_json
from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.inputs import HandleInput, MessageTextInput
from langflow.io import DataInput, MultilineInput, Output, StrInput
from langflow.schema import Data
from langflow.schema.message import Message


class ParseJSONDataComponent(Component):
    display_name = "Parse JSON"
    description = "Convert and extract JSON fields."
    icon = "braces"
    name = "ParseJSONData"


    inputs = [
        HandleInput(
            name="input_value",
            display_name="Input",
            info="Data object to filter.",
            required=True,
            input_types=["Message", "Data"]
        ),
        MessageTextInput(
            name="query",
            display_name="JQ Query",
            info="JQ Query to filter the data. The input is always a JSON list.",
            required=True
        ),
    ]

    outputs = [
        Output(display_name="Filtered Data", name="filtered_data", method="filter_data"),
    ]


    def _parse_data(self, input_value):
        if isinstance(input_value, Message):
            return input_value.text
        if isinstance(input_value, Data):
            return input_value.data
        return input_value

    def filter_data(self) -> list[Data]:

        to_filter = self.input_value
        if isinstance(to_filter, list):
            to_filter = [self._parse_data(f) for f in to_filter]
        else:
            to_filter = [self._parse_data(to_filter)]

        if len(to_filter):
            try:
                to_filter = [json.loads(str(f)) for f in to_filter]
            except json.JSONDecodeError:
                to_filter = [repair_json(str(f)) for f in to_filter]
            except Exception:
                pass
        to_filter = json.dumps(to_filter)
        to_filter = str(to_filter)

        results = jq.compile(self.query).input_text(to_filter).all()
        docs = [Data(data=value) for value in results]
        return docs
