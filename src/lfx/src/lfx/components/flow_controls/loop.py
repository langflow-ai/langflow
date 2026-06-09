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
        "Iterates through Data or Message objects, processing items individually "
        "and aggregating results from loop inputs."
    )
    documentation: str = "https://docs.langflow.org/loop"
    icon = "infinity"

    inputs = [
        HandleInput(
            name="data",
            display_name="Inputs",
            info="The initial DataFrame to iterate over.",
            input_types=["DataFrame", "Table"],
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
        """Initialize the data list and context index.

        Seeds the input list and index counter in ctx. The aggregated results
        are owned by `_iterate`, which writes them once the subgraph finishes.
        """
        if self.ctx.get(f"{self._id}_initialized", False):
            return

        # Ensure data is a list of Data objects
        data_list = self._validate_data(self.data)

        # Store the initial data and context variables
        self.update_ctx(
            {
                f"{self._id}_data": data_list,
                f"{self._id}_index": 0,
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

    async def _iterate(self) -> list[Data]:
        """Run the loop body subgraph once and cache the aggregated results.

        Both `item_output` and `done_output` may be called during the same
        vertex build (if both outputs have downstream consumers), so this
        helper is idempotent: it caches the aggregated results in ctx under
        `{self._id}_aggregated` and guards re-entry with `{self._id}_iterated`.
        If a prior call raised, the exception is cached in
        `{self._id}_iteration_error` and re-raised on subsequent calls so
        repeat invocations surface the same failure instead of silently
        returning empty data or re-running the subgraph.

        Production constructs a fresh Graph per request (via
        `Graph.from_payload`), so `ctx` is effectively per-run and the
        cached `_iterated` flag does not leak across executions.
        """
        if self.ctx.get(f"{self._id}_iterated", False):
            cached_error = self.ctx.get(f"{self._id}_iteration_error")
            if cached_error is not None:
                raise cached_error
            return self.ctx.get(f"{self._id}_aggregated", [])

        import time

        started_at = time.perf_counter()
        try:
            self.initialize_data()
            data_list = self.ctx.get(f"{self._id}_data", [])
            self.log(f"Starting loop over {len(data_list)} item(s)", name="Start")

            if not data_list:
                self.update_ctx({f"{self._id}_aggregated": [], f"{self._id}_iterated": True})
                self.log("No items to iterate, skipping loop body", name="Skipped")
                return []

            aggregated_results = await self.execute_loop_body(data_list, event_manager=self._event_manager)
        except Exception as exc:
            from lfx.log.logger import logger

            elapsed = time.perf_counter() - started_at
            self.log(f"Loop failed after {elapsed:.3f}s: {exc}", name="Error")
            await logger.aexception(f"Loop {self._id} failed while executing loop body")
            self.update_ctx({f"{self._id}_iteration_error": exc, f"{self._id}_iterated": True})
            raise

        elapsed = time.perf_counter() - started_at
        self.log(
            f"Completed {len(aggregated_results)} iteration(s) in {elapsed:.3f}s",
            name="Complete",
        )
        self.update_ctx({f"{self._id}_aggregated": aggregated_results, f"{self._id}_iterated": True})
        return aggregated_results

    async def item_output(self) -> Data:
        """Display the inputs dispatched to the loop body.

        Also triggers the iteration (idempotent) when `done` has no
        downstream consumer, so the loop still runs if only the Item
        output is connected. When `done` IS connected we leave iteration
        to `done_output`. The `item` branch is stopped in both cases so
        downstream vertices aren't executed by the outer graph (the loop
        body runs internally via the subgraph in `_iterate`).

        Returns a `Data` envelope so the outer item edge remains
        compatible with Data-typed consumers in the loop body. The
        wrapped payload exposes the iterated rows for inspection.
        """
        self.stop("item")
        if self._vertex is not None and "done" not in self._vertex.edges_source_names:
            await self._iterate()
        data_list = self.ctx.get(f"{self._id}_data", [])
        return Data(data={"count": len(data_list), "items": [d.data for d in data_list]})

    async def done_output(self) -> DataFrame:
        """Return the aggregated results from the loop iteration.

        Triggers the iteration if it hasn't run yet (for example when only
        `done` is connected and `item_output` never executed). In the common
        case where `item` is also connected, `_iterate` has already cached
        the aggregated results in ctx and this call is a cheap read, so the
        order in which the two outputs are evaluated does not matter.
        """
        aggregated_results = await self._iterate()
        return DataFrame(aggregated_results)
