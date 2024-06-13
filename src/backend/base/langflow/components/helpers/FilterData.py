from typing import List

from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.schema import Data
from langflow.template import Input, Output


class FilterDataComponent(Component):
    display_name = "Filter Message"
    description = "Filters a Message object based on a list of strings."
    icon = "filter"

    inputs = [
        Input(name="message", display_name="Message", info="Message object to filter.", input_types=["Message"]),
        StrInput(
            name="filter_criteria", display_name="Filter Criteria", info="List of strings to filter by.", is_list=True
        ),
    ]

    outputs = [
        Output(display_name="Filtered Data", name="filtered_data", method="filter_data"),
    ]

    def filter_data(self) -> Data:
        filter_criteria: List[str] = self.filter_criteria

        # Filter the data
        filtered = {key: value for key, value in self.message.data.items() if key == filter_criteria}

        # Create a new Data object with the filtered data
        self.status = filtered
        return filtered
