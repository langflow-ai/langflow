from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data


class LoopComponent(Component):
    display_name = "Loop"
    description = (
        "Iterates over a list of Data objects, outputting one item at a time and aggregating results from loop inputs."
    )
    icon = "infinity"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The initial list of Data objects to iterate over.",
        ),
    ]

    outputs = [
        Output(display_name="Item", name="item", method="item_output", allows_loop=True),
        Output(display_name="Done", name="done", method="done_output"),
    ]

    def initialize_data(self) -> None:
        """Initialize the data list, context index, and aggregated list."""
        if self.ctx.get(f"{self._id}_initialized", False):
            return

        # Ensure data is a list of Data objects
        data_list = self._validate_data(self.data)

        # Store the initial data and context variables
        self.update_ctx(
            {
                f"{self._id}_data": data_list,
                f"{self._id}_index": 0,
                f"{self._id}_aggregated": [],
                f"{self._id}_initialized": True,
            }
        )

    def _validate_data(self, data):
        """Validate and return a list of Data objects."""
        if isinstance(data, Data):
            return [data]
        if isinstance(data, list) and all(isinstance(item, Data) for item in data):
            return data
        msg = "The 'data' input must be a list of Data objects or a single Data object."
        raise TypeError(msg)

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
            return Data(text="")

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
        return current_item

    def done_output(self) -> Data:
        """Trigger the done output when iteration is complete."""
        self.initialize_data()

        if self.evaluate_stop_loop():
            self.stop("item")
            self.start("done")

            return self.ctx.get(f"{self._id}_aggregated", [])
        self.stop("done")
        return Data(text="")

    def loop_variables(self):
        """Retrieve loop variables from context."""
        return (
            self.ctx.get(f"{self._id}_data", []),
            self.ctx.get(f"{self._id}_index", 0),
        )

    def aggregated_output(self) -> Data:
        """Return the aggregated list once all items are processed."""
        self.initialize_data()

        # Get data list and aggregated list
        data_list = self.ctx.get(f"{self._id}_data", [])
        aggregated = self.ctx.get(f"{self._id}_aggregated", [])

        # Check if loop input is provided and append to aggregated list
        if self.item is not None and not isinstance(self.item, str) and len(aggregated) <= len(data_list):
            aggregated.append(self.item)
            self.update_ctx({f"{self._id}_aggregated": aggregated})
        return aggregated
