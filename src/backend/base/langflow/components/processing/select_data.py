from langflow.custom.custom_component.component import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs.inputs import DataInput, IntInput
from langflow.io import Output
from langflow.schema.data import Data


class SelectDataComponent(Component):
    display_name: str = "Select Data"
    description: str = "Select a single data from a list of data."
    name: str = "SelectData"
    icon = "prototypes"
    legacy = True

    inputs = [
        DataInput(
            name="data_list",
            display_name="Data List",
            info="List of data to select from.",
            is_list=True,  # Specify that this input takes a list of Data objects
        ),
        IntInput(
            name="data_index",
            display_name="Data Index",
            info="Index of the data to select.",
            value=0,  # Will be populated dynamically based on the length of data_list
            range_spec=RangeSpec(min=0, max=15, step=1, step_type="int"),
        ),
    ]

    outputs = [
        Output(display_name="Selected Data", name="selected_data", method="select_data"),
    ]

    async def select_data(self) -> Data:
        # Retrieve the selected index from the dropdown
        selected_index = int(self.data_index)
        # Get the data list

        # Validate that the selected index is within bounds
        if selected_index < 0 or selected_index >= len(self.data_list):
            msg = f"Selected index {selected_index} is out of range."
            raise ValueError(msg)

        # Return the selected Data object
        selected_data = self.data_list[selected_index]
        self.status = selected_data  # Update the component status to reflect the selected data
        return selected_data
