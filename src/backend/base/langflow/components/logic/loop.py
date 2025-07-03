from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import HandleInput, TabInput
from langflow.io import IntInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.template.field.base import Output
from langflow.utils.component_utils import set_current_fields, set_field_advanced

# Define fields for each mode
MODE_FIELDS = {
    "For-Each": ["dataframe_input"],
    "Counted": ["data_input", "iterations"],
}

# Fields that should always be visible
DEFAULT_FIELDS = ["mode"]


class LoopComponent(Component):
    display_name = "Loop"
    description = (
        "Iterates over items with two modes: For-Each (iterate over DataFrame) or Counted (repeat N times)."
    )
    icon = "infinity"

    inputs = [
        TabInput(
            name="mode",
            display_name="Mode",
            options=["For-Each", "Counted"],
            value="For-Each",
            info="Choose iteration mode: For-Each iterates over DataFrame/list, Counted repeats N times.",
            real_time_refresh=True,
        ),
        HandleInput(
            name="dataframe_input",
            display_name="Input",
            info="The DataFrame input to iterate over the rows.",
            input_types=["DataFrame"],
            advanced=False,
        ),
        HandleInput(
            name="data_input",
            display_name="Input",
            info="The Data or Message to repeat N times.",
            input_types=["Data", "Message"],
            advanced=False,
        ),
        IntInput(
            name="iterations",
            display_name="Iterations",
            info="Number of times to repeat the data.",
            value=1,
            advanced=False,
        ),
    ]

    outputs = [
        Output(display_name="Item", name="item", method="item_output", allows_loop=True, group_outputs=True),
        Output(display_name="Done", name="done", method="done_output", group_outputs=True),
    ]

    def initialize_data(self) -> None:
        """Initialize the data list, context index, and aggregated list."""
        if self.ctx.get(f"{self._id}_initialized", False):
            return

        # Get data based on selected mode
        if self.mode == "Counted":
            data_list = self._validate_data_counted(self.data_input, self.iterations)
        else:
            data_list = self._validate_data_foreach(self.dataframe_input)

        # Store the initial data and context variables
        self.update_ctx(
            {
                f"{self._id}_data": data_list,
                f"{self._id}_index": 0,
                f"{self._id}_aggregated": [],
                f"{self._id}_initialized": True,
            }
        )

    def _validate_data_foreach(self, data):
        """Validate and return a list of Data objects for For-Each mode."""
        if isinstance(data, DataFrame):
            return data.to_data_list()
        if isinstance(data, Data):
            return [data]
        if isinstance(data, list) and all(isinstance(item, Data) for item in data):
            return data
        msg = "The 'data' input must be a DataFrame, a list of Data objects, or a single Data object."
        raise TypeError(msg)

    def _validate_data_counted(self, data, iterations):
        """Validate and return a list of Data objects for Counted mode."""
        if isinstance(data, Message):
            data = Data(text=data.text)
        elif not isinstance(data, Data):
            data = Data(text=str(data))
        return [data] * iterations

    def update_build_config(self, build_config, field_value, field_name=None):
        """Update the build config based on the selected mode."""
        if field_name != "mode":
            return build_config

        return set_current_fields(
            build_config=build_config,
            action_fields=MODE_FIELDS,
            selected_action=field_value,
            default_fields=DEFAULT_FIELDS,
            func=set_field_advanced,
            default_value=True,
        )

    def evaluate_stop_loop(self) -> bool:
        """Evaluate whether to stop item or done output."""
        current_index = self.ctx.get(f"{self._id}_index", 0)
        data_length = len(self.ctx.get(f"{self._id}_data", []))
        return current_index > data_length

    def item_output(self) -> Data:
        """Output the next item in the list or stop if done."""
        self.initialize_data()
        current_item = Data(text="")

        if self.evaluate_stop_loop():
            self.stop("item")
        else:
            # Get data list and current index
            data_list, current_index = self.loop_variables()
            if current_index < len(data_list):
                # Output current item and increment index
                try:
                    current_item = data_list[current_index]
                except IndexError:
                    current_item = Data(text="")
            self.aggregated_output()
            self.update_ctx({f"{self._id}_index": current_index + 1})

        # Now we need to update the dependencies for the next run
        self.update_dependency()
        return current_item

    def update_dependency(self):
        item_dependency_id = self.get_incoming_edge_by_target_param("item")

        self.graph.run_manager.run_predecessors[self._id].append(item_dependency_id)

    def done_output(self) -> DataFrame:
        """Trigger the done output when iteration is complete."""
        self.initialize_data()

        if self.evaluate_stop_loop():
            self.stop("item")
            self.start("done")

            aggregated = self.ctx.get(f"{self._id}_aggregated", [])

            return DataFrame(aggregated)
        self.stop("done")
        return DataFrame([])

    def loop_variables(self):
        """Retrieve loop variables from context."""
        return (
            self.ctx.get(f"{self._id}_data", []),
            self.ctx.get(f"{self._id}_index", 0),
        )

    def aggregated_output(self) -> list[Data]:
        """Return the aggregated list once all items are processed."""
        self.initialize_data()

        # Get data list and aggregated list
        data_list = self.ctx.get(f"{self._id}_data", [])
        aggregated = self.ctx.get(f"{self._id}_aggregated", [])
        loop_input = self.item
        if loop_input is not None and not isinstance(loop_input, str) and len(aggregated) <= len(data_list):
            aggregated.append(loop_input)
            self.update_ctx({f"{self._id}_aggregated": aggregated})
        return aggregated
