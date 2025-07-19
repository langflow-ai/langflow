from lfx.custom.custom_component.component import Component

from langflow.io import DataInput, MessageTextInput, Output
from langflow.schema.data import Data


class FilterDataComponent(Component):
    display_name = "Filter Data"
    description = "Filters a Data object based on a list of keys."
    icon = "filter"
    beta = True
    name = "FilterData"
    legacy = True

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="Data object to filter.",
        ),
        MessageTextInput(
            name="filter_criteria",
            display_name="Filter Criteria",
            info="List of keys to filter by.",
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Filtered Data", name="filtered_data", method="filter_data"),
    ]

    def filter_data(self) -> Data:
        filter_criteria: list[str] = self.filter_criteria
        data = self.data.data if isinstance(self.data, Data) else {}

        # Filter the data
        filtered = {key: value for key, value in data.items() if key in filter_criteria}

        # Create a new Data object with the filtered data
        filtered_data = Data(data=filtered)
        self.status = filtered_data
        return filtered_data
