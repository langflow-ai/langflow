from lfx.base.flow_controls.loop_utils import (
    execute_loop_body,
    extract_loop_output,
    get_loop_body_start_edge,
    get_loop_body_start_vertex,
    get_loop_body_vertices,
    validate_data_input,
)
from lfx.components.processing.converter import convert_to_data
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import HandleInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output


class LoopComponent(Component):
    display_name = "Loop"
    description = (
        "Iterates over a list of Data or Message objects, processing one item at a time and "
        "aggregating results from loop inputs. Message objects are automatically converted to "
        "Data objects for consistent processing."
    )
    documentation: str = "https://docs.langflow.org/loop"
    icon = "infinity"

    inputs = [
        HandleInput(
            name="data",
            display_name="Inputs",
            info="The initial DataFrame to iterate over.",
            input_types=["DataFrame"],
        ),
    ]

    outputs = [
        Output(
            display_name="Item",
            name="item",
            method="item_output",
            allows_loop=True,
            loop_types=["Message"],
            group_outputs=True,
        ),
        Output(display_name="Done", name="done", method="done_output", group_outputs=True),
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

    def _convert_message_to_data(self, message: Message) -> Data:
        """Convert a Message object to a Data object using Type Convert logic."""
        return convert_to_data(message, auto_parse=False)

    def _validate_data(self, data):
        """Validate and return a list of Data objects."""
        return validate_data_input(data)

    def get_loop_body_vertices(self) -> set[str]:
        """Identify vertices in this loop's body via graph traversal.

        Traverses from the loop's "item" output to the vertex that feeds back
        to the loop's "item" input, collecting all vertices in between.
        This naturally handles nested loops by stopping at this loop's feedback edge.

        Returns:
            Set of vertex IDs that form this loop's body
        """
        # Check if we have a proper graph context
        if not hasattr(self, "_vertex") or self._vertex is None:
            return set()

        return get_loop_body_vertices(
            vertex=self._vertex,
            graph=self.graph,
            get_incoming_edge_by_target_param_fn=self.get_incoming_edge_by_target_param,
        )

    def _get_loop_body_start_vertex(self) -> str | None:
        """Get the first vertex in the loop body (connected to loop's item output).

        Returns:
            The vertex ID of the first vertex in the loop body, or None if not found
        """
        # Check if we have a proper graph context
        if not hasattr(self, "_vertex") or self._vertex is None:
            return None

        return get_loop_body_start_vertex(vertex=self._vertex)

    def _extract_loop_output(self, results: list) -> Data:
        """Extract the output from subgraph execution results.

        Args:
            results: List of VertexBuildResult objects from subgraph execution

        Returns:
            Data object containing the loop iteration output
        """
        # Get the vertex ID that feeds back to the item input (end of loop body)
        end_vertex_id = self.get_incoming_edge_by_target_param("item")
        return extract_loop_output(results=results, end_vertex_id=end_vertex_id)

    async def execute_loop_body(self, data_list: list[Data], event_manager=None) -> list[Data]:
        """Execute loop body for each data item.

        Creates an isolated subgraph for the loop body and executes it
        for each item in the data list, collecting results.

        Args:
            data_list: List of Data objects to iterate over
            event_manager: Optional event manager to pass to subgraph execution for UI events

        Returns:
            List of Data objects containing results from each iteration
        """
        # Get the loop body configuration once
        loop_body_vertex_ids = self.get_loop_body_vertices()
        start_vertex_id = self._get_loop_body_start_vertex()
        start_edge = get_loop_body_start_edge(self._vertex)
        end_vertex_id = self.get_incoming_edge_by_target_param("item")

        return await execute_loop_body(
            graph=self.graph,
            data_list=data_list,
            loop_body_vertex_ids=loop_body_vertex_ids,
            start_vertex_id=start_vertex_id,
            start_edge=start_edge,
            end_vertex_id=end_vertex_id,
            event_manager=event_manager,
        )

    def item_output(self) -> Data:
        """Output is no longer used - loop executes internally now.

        This method is kept for backward compatibility but does nothing.
        The actual loop execution happens in done_output().
        """
        self.stop("item")
        return Data(text="")

    async def done_output(self) -> DataFrame:
        """Execute the loop body for all items and return aggregated results.

        This is now the main execution point for the loop. It:
        1. Gets the data list to iterate over
        2. Executes the loop body as an isolated subgraph for each item
        3. Returns the aggregated results

        Args:
            event_manager: Optional event manager for UI event emission
        """
        self.initialize_data()

        # Get data list
        data_list = self.ctx.get(f"{self._id}_data", [])

        if not data_list:
            return DataFrame([])

        # Execute loop body for all items
        try:
            aggregated_results = await self.execute_loop_body(data_list, event_manager=self._event_manager)
            return DataFrame(aggregated_results)
        except Exception as e:
            # Log error and return empty DataFrame
            from lfx.log.logger import logger

            await logger.aerror(f"Error executing loop body: {e}")
            raise
