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
        DataInput(name="data", display_name="Data", info="The initial list of Data objects to iterate over."),
        DataInput(name="loop_input", display_name="Loop Input", info="Data to aggregate during the iteration."),
    ]

    outputs = [
        Output(display_name="Item", name="item", method="item_output"),
        Output(display_name="Done", name="done", method="done_output"),
    ]

    def initialize_data(self) -> None:
        """Initialize the data list, context index, and aggregated list."""
        if self.ctx.get(f"{self._id}_initialized", False):
            return

        # Ensure data is a list of Data objects
        if isinstance(self.data, Data):
            data_list: list[Data] = [self.data]
        elif isinstance(self.data, list):
            if not all(isinstance(item, Data) for item in self.data):
                msg = "All items in the data list must be Data objects."
                raise TypeError(msg)
            data_list = self.data
        else:
            msg = "The 'data' input must be a list of Data objects or a single Data object."
            raise TypeError(msg)

        # Store the initial data and context variables
        self.update_ctx(
            {
                f"{self._id}_data": data_list,
                f"{self._id}_index": 0,
                f"{self._id}_aggregated": [],
                f"{self._id}_initialized": True,
            }
        )

    def item_output(self) -> Data:
        """Output the next item in the list."""
        self.initialize_data()

        # Get data list and current index
        data_list: list[Data] = self.ctx.get(f"{self._id}_data", [])
        current_index: int = self.ctx.get(f"{self._id}_index", 0)

        if current_index < len(data_list):
            # Output current item and increment index
            current_item: Data = data_list[current_index]
            self.update_ctx({f"{self._id}_index": current_index + 1})
            return current_item

        # No more items to output
        self.stop("item")
        return None  # type: ignore [return-value]

    def done_output(self) -> Data:
        """Return the aggregated list once all items are processed."""
        self.initialize_data()

        # Get data list and aggregated list
        data_list = self.ctx.get(f"{self._id}_data", [])
        aggregated = self.ctx.get(f"{self._id}_aggregated", [])

        # Check if loop input is provided and append to aggregated list
        if self.loop_input is not None:
            aggregated.append(self.loop_input)
            self.update_ctx({f"{self._id}_aggregated": aggregated})

        # Check if aggregation is complete
        if len(aggregated) >= len(data_list):
            return aggregated

        # Not all items have been processed yet
        self.stop("done")
        return None  # type: ignore [return-value]
