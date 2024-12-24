from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data


class IteratorComponent(Component):
    display_name = "Loop"
    description = (
        "Iterates over a list of Data objects, outputting one item at a time and aggregating results from loop inputs."
    )
    icon = "infinity"

    inputs = [
        DataInput(name="data", display_name="Data", info="The initial list of Data objects to iterate over."),
        DataInput(name="loop", display_name="Loop Input", info="Data to aggregate during the iteration."),
    ]

    outputs = [
        Output(display_name="Item", name="item", method="item_output"),
        Output(display_name="Done", name="done", method="done_output"),
    ]

    def initialize_data(self):
        """Initialize the data list, context index, and aggregated list."""
        if not self.ctx.get(f"{self._id}_initialized", False):
            # Ensure data is a list of Data objects
            if isinstance(self.data, Data):
                data_list = [self.data]
            elif isinstance(self.data, list):
                data_list = self.data
            else:
                raise ValueError("The 'data' input must be a list of Data objects or a single Data object.")

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
        data_list = self.ctx.get(f"{self._id}_data", [])
        current_index = self.ctx.get(f"{self._id}_index", 0)

        if current_index < len(data_list):
            # Output current item
            current_item = data_list[current_index]
            self.update_ctx({f"{self._id}_index": current_index + 1})
            print("item_output:", current_item)
            return current_item
        # No more items to output
        self.stop("item")
        return None

    def done_output(self) -> Data:
        """Return the aggregated list once all items are processed."""
        self.initialize_data()

        # Get data list and aggregated list
        data_list = self.ctx.get(f"{self._id}_data", [])
        aggregated = self.ctx.get(f"{self._id}_aggregated", [])

        # Check if loop input is provided
        loop_input = self.loop
        if loop_input:
            # Append loop input to aggregated list
            aggregated.append(loop_input)
            self.update_ctx({f"{self._id}_aggregated": aggregated})

        # Check if aggregation is complete
        if len(aggregated) >= len(data_list):
            print("done_output:", aggregated)
            return [data for data in aggregated]
        # Not all items have been processed yet
        self.stop("done")
        return None
