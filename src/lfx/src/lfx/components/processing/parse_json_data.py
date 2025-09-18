import json
from json import JSONDecodeError

import jq
from json_repair import repair_json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import HandleInput, MessageTextInput
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.message import Message


class ParseJSONDataComponent(Component):
    display_name = "Parse JSON"
    description = "Convert and extract JSON fields."
    icon = "braces"
    name = "ParseJSONData"
    legacy: bool = True
    replacement = ["processing.ParserComponent"]

    inputs = [
        HandleInput(
            name="input_value",
            display_name="Input",
            info="Data object to filter.",
            required=True,
            input_types=["Message", "Data"],
        ),
        MessageTextInput(
            name="query",
            display_name="JQ Query",
            info="JQ Query to filter the data. The input is always a JSON list.",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Filtered Data", name="filtered_data", method="filter_data"),
    ]

    def _parse_data(self, input_value) -> str:
        if isinstance(input_value, Message) and isinstance(input_value.text, str):
            return input_value.text
        if isinstance(input_value, Data):
            return json.dumps(input_value.data)
        return str(input_value)

    def filter_data(self) -> list[Data]:
        to_filter = self.input_value
        if not to_filter:
            return []
        # Check if input is a list
        if isinstance(to_filter, list):
            to_filter = [self._parse_data(f) for f in to_filter]
        else:
            to_filter = self._parse_data(to_filter)

        # If input is not a list, don't wrap it in a list
        if not isinstance(to_filter, list):
            to_filter = repair_json(to_filter)
            try:
                to_filter_as_dict = json.loads(to_filter)
            except JSONDecodeError:
                try:
                    to_filter_as_dict = json.loads(repair_json(to_filter))
                except JSONDecodeError as e:
                    msg = f"Invalid JSON: {e}"
                    raise ValueError(msg) from e
        else:
            to_filter = [repair_json(f) for f in to_filter]
            to_filter_as_dict = []
            for f in to_filter:
                try:
                    to_filter_as_dict.append(json.loads(f))
                except JSONDecodeError:
                    try:
                        to_filter_as_dict.append(json.loads(repair_json(f)))
                    except JSONDecodeError as e:
                        msg = f"Invalid JSON: {e}"
                        raise ValueError(msg) from e
            to_filter = to_filter_as_dict

        full_filter_str = json.dumps(to_filter_as_dict)

        logger.info("to_filter: ", to_filter)

        results = jq.compile(self.query).input_text(full_filter_str).all()
        logger.info("results: ", results)
        return [Data(data=value) if isinstance(value, dict) else Data(text=str(value)) for value in results]
