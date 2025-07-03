from __future__ import annotations

import asyncio
import contextlib
import contextvars
import copy
import json
import queue
import threading
import traceback
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from langflow.exceptions.component import ComponentBuildError
from langflow.graph.edge.base import CycleEdge, Edge
from langflow.graph.graph.constants import Finish, lazy_load_vertex_dict
from langflow.graph.graph.runnable_vertices_manager import RunnableVerticesManager
from langflow.graph.graph.schema import GraphData, GraphDump, StartConfigDict, VertexBuildResult
from langflow.graph.graph.state_model import create_state_model_from_graph
from langflow.graph.graph.utils import (
    find_all_cycle_edges,
    find_cycle_vertices,
    find_start_component_id,
    get_sorted_vertices,
    process_flow,
    should_continue,
)
from langflow.graph.schema import InterfaceComponentTypes, RunOutputs
from langflow.graph.utils import log_vertex_build
from langflow.graph.vertex.base import Vertex, VertexStates
from langflow.graph.vertex.schema import NodeData, NodeTypeEnum
from langflow.graph.vertex.vertex_types import ComponentVertex, InterfaceVertex, StateVertex
from langflow.logging.logger import LogConfig, configure
from langflow.schema.dotdict import dotdict
from langflow.schema.schema import INPUT_FIELD_NAME, InputType, OutputValue
from langflow.services.cache.utils import CacheMiss
from langflow.services.deps import get_chat_service, get_tracing_service
from langflow.utils.async_helpers import run_until_complete

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable

    from langflow.api.v1.schemas import InputValueRequest
    from langflow.custom.custom_component.component import Component
    from langflow.events.event_manager import EventManager
    from langflow.graph.edge.schema import EdgeData
    from langflow.graph.schema import ResultData
    from langflow.services.chat.schema import GetCache, SetCache
    from langflow.services.tracing.service import TracingService


class Graph:
    """A class representing a graph of vertices and edges."""

    def __init__(
        self,
        start: Component | None = None,
        end: Component | None = None,
        flow_id: str | None = None,
        flow_name: str | None = None,
        description: str | None = None,
        user_id: str | None = None,
        log_config: LogConfig | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initializes a new Graph instance.

        If both start and end components are provided, the graph is initialized and prepared for execution.
        If only one is provided, a ValueError is raised. The context must be a dictionary if specified,
        otherwise a TypeError is raised. Internal data structures for vertices, edges, state management,
        run management, and tracing are set up during initialization.
        """
        if log_config:
            configure(**log_config)

        self._start = start
        self._state_model = None
        self._end = end
        self._prepared = False
        self._runs = 0
        self._updates = 0
        self.flow_id = flow_id
        self.flow_name = flow_name
        self.description = description
        self.user_id = user_id
        self._is_input_vertices: list[str] = []
        self._is_output_vertices: list[str] = []
        self._is_state_vertices: list[str] | None = None
        self.has_session_id_vertices: list[str] = []
        self._sorted_vertices_layers: list[list[str]] = []
        self._run_id = ""
        self._session_id = ""
        self._start_time = datetime.now(timezone.utc)
        self.inactivated_vertices: set = set()
        self.activated_vertices: list[str] = []
        self.vertices_layers: list[list[str]] = []
        self.vertices_to_run: set[str] = set()
        self.stop_vertex: str | None = None
        self.inactive_vertices: set = set()
        self.edges: list[CycleEdge] = []
        self.vertices: list[Vertex] = []
        self.run_manager = RunnableVerticesManager()
        self._vertices: list[NodeData] = []
        self._edges: list[EdgeData] = []

        self.top_level_vertices: list[str] = []
        self.vertex_map: dict[str, Vertex] = {}
        self.predecessor_map: dict[str, list[str]] = defaultdict(list)
        self.successor_map: dict[str, list[str]] = defaultdict(list)
        self.in_degree_map: dict[str, int] = defaultdict(int)
        self.parent_child_map: dict[str, list[str]] = defaultdict(list)
        self._run_queue: deque[str] = deque()
        self._first_layer: list[str] = []
        self._lock = asyncio.Lock()
        self.raw_graph_data: GraphData = {"nodes": [], "edges": []}
        self._is_cyclic: bool | None = None
        self._cycles: list[tuple[str, str]] | None = None
        self._cycle_vertices: set[str] | None = None
        self._call_order: list[str] = []
        self._snapshots: list[dict[str, Any]] = []
        self._end_trace_tasks: set[asyncio.Task] = set()

        if context and not isinstance(context, dict):
            msg = "Context must be a dictionary"
            raise TypeError(msg)
        self._context = dotdict(context or {})
        try:
            self.tracing_service: TracingService | None = get_tracing_service()
        except Exception:  # noqa: BLE001
            logger.exception("Error getting tracing service")
            self.tracing_service = None
        if start is not None and end is not None:
            self._set_start_and_end(start, end)
            self.prepare(start_component_id=start._id)
        if (start is not None and end is None) or (start is None and end is not None):
            msg = "You must provide both input and output components"
            raise ValueError(msg)

    @property
    def context(self) -> dotdict:
        if isinstance(self._context, dotdict):
            return self._context
        return dotdict(self._context)

    @context.setter
    def context(self, value: dict[str, Any]):
        if not isinstance(value, dict):
            msg = "Context must be a dictionary"
            raise TypeError(msg)
        if isinstance(value, dict):
            value = dotdict(value)
        self._context = value

    @property
    def session_id(self):
        return self._session_id

    @session_id.setter
    def session_id(self, value: str):
        self._session_id = value

    @property
    def state_model(self):
        if not self._state_model:
            self._state_model = create_state_model_from_graph(self)
        return self._state_model

    def __add__(self, other):
        if not isinstance(other, Graph):
            msg = "Can only add Graph objects"
            raise TypeError(msg)
        # Add the vertices and edges from the other graph to this graph
        new_instance = copy.deepcopy(self)
        for vertex in other.vertices:
            # This updates the edges as well
            new_instance.add_vertex(vertex)
        new_instance.build_graph_maps(new_instance.edges)
        new_instance.define_vertices_lists()
        return new_instance

    def __iadd__(self, other):
        if not isinstance(other, Graph):
            msg = "Can only add Graph objects"
            raise TypeError(msg)
        # Add the vertices and edges from the other graph to this graph
        for vertex in other.vertices:
            # This updates the edges as well
            self.add_vertex(vertex)
        self.build_graph_maps(self.edges)
        self.define_vertices_lists()
        return self

    def dumps(
        self,
        name: str | None = None,
        description: str | None = None,
        endpoint_name: str | None = None,
    ) -> str:
        graph_dict = self.dump(name, description, endpoint_name)
        return json.dumps(graph_dict, indent=4, sort_keys=True)

    def dump(
        self, name: str | None = None, description: str | None = None, endpoint_name: str | None = None
    ) -> GraphDump:
        if self.raw_graph_data != {"nodes": [], "edges": []}:
            data_dict = self.raw_graph_data
        else:
            # we need to convert the vertices and edges to json
            nodes = [node.to_data() for node in self.vertices]
            edges = [edge.to_data() for edge in self.edges]
            self.raw_graph_data = {"nodes": nodes, "edges": edges}
            data_dict = self.raw_graph_data
        graph_dict: GraphDump = {
            "data": data_dict,
            "is_component": len(data_dict.get("nodes", [])) == 1 and data_dict["edges"] == [],
        }
        if name:
            graph_dict["name"] = name
        elif name is None and self.flow_name:
            graph_dict["name"] = self.flow_name
        if description:
            graph_dict["description"] = description
        elif description is None and self.description:
            graph_dict["description"] = self.description
        graph_dict["endpoint_name"] = str(endpoint_name)
        return graph_dict

    def add_nodes_and_edges(self, nodes: list[NodeData], edges: list[EdgeData]) -> None:
        self._vertices = nodes
        self._edges = edges
        self.raw_graph_data = {"nodes": nodes, "edges": edges}
        self.top_level_vertices = []
        for vertex in self._vertices:
            if vertex_id := vertex.get("id"):
                self.top_level_vertices.append(vertex_id)
            if vertex_id in self.cycle_vertices:
                self.run_manager.add_to_cycle_vertices(vertex_id)
        self._graph_data = process_flow(self.raw_graph_data)

        self._vertices = self._graph_data["nodes"]
        self._edges = self._graph_data["edges"]
        self.initialize()

    def add_component(self, component: Component, component_id: str | None = None) -> str:
        component_id = component_id or component._id
        if component_id in self.vertex_map:
            return component_id
        component._id = component_id
        if component_id in self.vertex_map:
            msg = f"Component ID {component_id} already exists"
            raise ValueError(msg)
        frontend_node = component.to_frontend_node()
        self._vertices.append(frontend_node)
        vertex = self._create_vertex(frontend_node)
        vertex.add_component_instance(component)
        self._add_vertex(vertex)
        if component._edges:
            for edge in component._edges:
                self._add_edge(edge)

        if component._components:
            for _component in component._components:
                self.add_component(_component)

        return component_id

    def _set_start_and_end(self, start: Component, end: Component) -> None:
        if not hasattr(start, "to_frontend_node"):
            msg = f"start must be a Component. Got {type(start)}"
            raise TypeError(msg)
        if not hasattr(end, "to_frontend_node"):
            msg = f"end must be a Component. Got {type(end)}"
            raise TypeError(msg)
        self.add_component(start, start._id)
        self.add_component(end, end._id)

    def add_component_edge(self, source_id: str, output_input_tuple: tuple[str, str], target_id: str) -> None:
        source_vertex = self.get_vertex(source_id)
        if not isinstance(source_vertex, ComponentVertex):
            msg = f"Source vertex {source_id} is not a component vertex."
            raise TypeError(msg)
        target_vertex = self.get_vertex(target_id)
        if not isinstance(target_vertex, ComponentVertex):
            msg = f"Target vertex {target_id} is not a component vertex."
            raise TypeError(msg)
        output_name, input_name = output_input_tuple
        if source_vertex.custom_component is None:
            msg = f"Source vertex {source_id} does not have a custom component."
            raise ValueError(msg)
        if target_vertex.custom_component is None:
            msg = f"Target vertex {target_id} does not have a custom component."
            raise ValueError(msg)

        try:
            input_field = target_vertex.get_input(input_name)
            input_types = input_field.input_types
            input_field_type = str(input_field.field_type)
        except ValueError as e:
            input_field = target_vertex.data.get("node", {}).get("template", {}).get(input_name)
            if not input_field:
                msg = f"Input field {input_name} not found in target vertex {target_id}"
                raise ValueError(msg) from e
            input_types = input_field.get("input_types", [])
            input_field_type = input_field.get("type", "")

        edge_data: EdgeData = {
            "source": source_id,
            "target": target_id,
            "data": {
                "sourceHandle": {
                    "dataType": source_vertex.custom_component.name
                    or source_vertex.custom_component.__class__.__name__,
                    "id": source_vertex.id,
                    "name": output_name,
                    "output_types": source_vertex.get_output(output_name).types,
                },
                "targetHandle": {
                    "fieldName": input_name,
                    "id": target_vertex.id,
                    "inputTypes": input_types,
                    "type": input_field_type,
                },
            },
        }
        self._add_edge(edge_data)

    async def async_start(
        self,
        inputs: InputValueRequest | list[dict] | None = None,
        max_iterations: int | None = None,
        config: StartConfigDict | None = None,
        event_manager: EventManager | None = None,
    ):
        if not self._prepared:
            msg = "Graph not prepared. Call prepare() first."
            raise ValueError(msg)
        # The idea is for this to return a generator that yields the result of
        # each step call and raise StopIteration when the graph is done
        if config is not None:
            self.__apply_config(config)
        # I want to keep a counter of how many tyimes result.vertex.id
        # has been yielded
        yielded_counts: dict[str, int] = defaultdict(int)

        while should_continue(yielded_counts, max_iterations):
            result = await self.astep(inputs=inputs, event_manager=event_manager)
            yield result
            if hasattr(result, "vertex"):
                yielded_counts[result.vertex.id] += 1
            if isinstance(result, Finish):
                return

        msg = "Max iterations reached"
        raise ValueError(msg)

    def _snapshot(self):
        return {
            "_run_queue": self._run_queue.copy(),
            "_first_layer": self._first_layer.copy(),
            "vertices_layers": copy.deepcopy(self.vertices_layers),
            "vertices_to_run": copy.deepcopy(self.vertices_to_run),
            "run_manager": copy.deepcopy(self.run_manager.to_dict()),
        }

    def __apply_config(self, config: StartConfigDict) -> None:
        for vertex in self.vertices:
            if vertex.custom_component is None:
                continue
            for output in vertex.custom_component._outputs_map.values():
                for key, value in config["output"].items():
                    setattr(output, key, value)

    def start(
        self,
        inputs: list[dict] | None = None,
        max_iterations: int | None = None,
        config: StartConfigDict | None = None,
        event_manager: EventManager | None = None,
    ) -> Generator:
        """Starts the graph execution synchronously by creating a new event loop in a separate thread.

        Args:
            inputs: Optional list of input dictionaries
            max_iterations: Optional maximum number of iterations
            config: Optional configuration dictionary
            event_manager: Optional event manager

        Returns:
            Generator yielding results from graph execution
        """
        if self.is_cyclic and max_iterations is None:
            msg = "You must specify a max_iterations if the graph is cyclic"
            raise ValueError(msg)

        if config is not None:
            self.__apply_config(config)

        # Create a queue for passing results and errors between threads
        result_queue: queue.Queue[VertexBuildResult | Exception | None] = queue.Queue()

        # Function to run async code in separate thread
        def run_async_code():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the async generator
                async_gen = self.async_start(inputs, max_iterations, event_manager)

                while True:
                    try:
                        # Get next result from async generator
                        result = loop.run_until_complete(anext(async_gen))
                        result_queue.put(result)

                        if isinstance(result, Finish):
                            break

                    except StopAsyncIteration:
                        break
                    except ValueError as e:
                        # Put the exception in the queue
                        result_queue.put(e)
                        break

            finally:
                # Ensure all pending tasks are completed
                pending = asyncio.all_tasks(loop)
                if pending:
                    # Create a future to gather all pending tasks
                    cleanup_future = asyncio.gather(*pending, return_exceptions=True)
                    loop.run_until_complete(cleanup_future)

                # Close the loop
                loop.close()
                # Signal completion
                result_queue.put(None)

        # Start thread for async execution
        thread = threading.Thread(target=run_async_code)
        thread.start()

        # Yield results from queue
        while True:
            result = result_queue.get()
            if result is None:
                break
            if isinstance(result, Exception):
                raise result
            yield result

        # Wait for thread to complete
        thread.join()

    def _add_edge(self, edge: EdgeData) -> None:
        self.add_edge(edge)
        source_id = edge["data"]["sourceHandle"]["id"]
        target_id = edge["data"]["targetHandle"]["id"]
        self.predecessor_map[target_id].append(source_id)
        self.successor_map[source_id].append(target_id)
        self.in_degree_map[target_id] += 1
        self.parent_child_map[source_id].append(target_id)

    def add_node(self, node: NodeData) -> None:
        self._vertices.append(node)

    def add_edge(self, edge: EdgeData) -> None:
        # Check if the edge already exists
        if edge in self._edges:
            return
        self._edges.append(edge)

    def initialize(self) -> None:
        self._build_graph()
        self.build_graph_maps(self.edges)
        self.define_vertices_lists()

    @property
    def is_state_vertices(self) -> list[str]:
        """Returns a cached list of vertex IDs for vertices marked as state vertices.

        The list is computed on first access by filtering vertices with `is_state` set to True and is
        cached for future calls.
        """
        if self._is_state_vertices is None:
            self._is_state_vertices = [vertex.id for vertex in self.vertices if vertex.is_state]
        return self._is_state_vertices

    def activate_state_vertices(self, name: str, caller: str) -> None:
        """Activates vertices associated with a given state name.

        Marks vertices with the specified state name, as well as their successors and related
        predecessors. The state manager is then updated with the new state record.
        """
        vertices_ids = set()
        new_predecessor_map = {}
        activated_vertices = []
        for vertex_id in self.is_state_vertices:
            caller_vertex = self.get_vertex(caller)
            vertex = self.get_vertex(vertex_id)
            if vertex_id == caller or vertex.display_name == caller_vertex.display_name:
                continue
            ctx_key = vertex.raw_params.get("context_key")
            if isinstance(ctx_key, str) and name in ctx_key and vertex_id != caller and isinstance(vertex, StateVertex):
                activated_vertices.append(vertex_id)
                vertices_ids.add(vertex_id)
                successors = self.get_all_successors(vertex, flat=True)
                # Update run_manager.run_predecessors because we are activating vertices
                # The run_prdecessors is the predecessor map of the vertices
                # we remove the vertex_id from the predecessor map whenever we run a vertex
                # So we need to get all edges of the vertex and successors
                # and run self.build_adjacency_maps(edges) to get the new predecessor map
                # that is not complete but we can use to update the run_predecessors
                successors_predecessors = set()
                for sucessor in successors:
                    successors_predecessors.update(self.get_all_predecessors(sucessor))

                edges_set = set()
                for _vertex in [vertex, *successors, *successors_predecessors]:
                    edges_set.update(_vertex.edges)
                    if _vertex.state == VertexStates.INACTIVE:
                        _vertex.set_state("ACTIVE")

                    vertices_ids.add(_vertex.id)
                edges = list(edges_set)
                predecessor_map, _ = self.build_adjacency_maps(edges)
                new_predecessor_map.update(predecessor_map)

        vertices_ids.update(new_predecessor_map.keys())
        vertices_ids.update(v_id for value_list in new_predecessor_map.values() for v_id in value_list)

        self.activated_vertices = activated_vertices
        self.vertices_to_run.update(vertices_ids)
        self.run_manager.update_run_state(
            run_predecessors=new_predecessor_map,
            vertices_to_run=self.vertices_to_run,
        )

    def reset_activated_vertices(self) -> None:
        """Resets the activated vertices in the graph."""
        self.activated_vertices = []

    def validate_stream(self) -> None:
        """Validates the stream configuration of the graph.

        If there are two vertices in the same graph (connected by edges)
        that have `stream=True` or `streaming=True`, raises a `ValueError`.

        Raises:
            ValueError: If two connected vertices have `stream=True` or `streaming=True`.
        """
        for vertex in self.vertices:
            if vertex.params.get("stream") or vertex.params.get("streaming"):
                successors = self.get_all_successors(vertex)
                for successor in successors:
                    if successor.params.get("stream") or successor.params.get("streaming"):
                        msg = (
                            f"Components {vertex.display_name} and {successor.display_name} "
                            "are connected and both have stream or streaming set to True"
                        )
                        raise ValueError(msg)

    @property
    def first_layer(self):
        if self._first_layer is None:
            msg = "Graph not prepared. Call prepare() first."
            raise ValueError(msg)
        return self._first_layer

    @property
    def is_cyclic(self):
        """Check if the graph has any cycles.

        Returns:
            bool: True if the graph has any cycles, False otherwise.
        """
        if self._is_cyclic is None:
            self._is_cyclic = bool(self.cycle_vertices)
        return self._is_cyclic

    @property
    def run_id(self):
        """The ID of the current run.

        Returns:
            str: The run ID.

        Raises:
            ValueError: If the run ID is not set.
        """
        if not self._run_id:
            msg = "Run ID not set"
            raise ValueError(msg)
        return self._run_id

    def set_run_id(self, run_id: uuid.UUID | str | None = None) -> None:
        """Sets the ID of the current run.

        Args:
            run_id (str): The run ID.
        """
        if run_id is None:
            run_id = uuid.uuid4()

        self._run_id = str(run_id)

    async def initialize_run(self) -> None:
        if not self._run_id:
            self.set_run_id()
        if self.tracing_service:
            run_name = f"{self.flow_name} - {self.flow_id}"
            await self.tracing_service.start_tracers(
                run_id=uuid.UUID(self._run_id),
                run_name=run_name,
                user_id=self.user_id,
                session_id=self.session_id,
            )

    def _end_all_traces_async(self, outputs: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        task = asyncio.create_task(self.end_all_traces(outputs, error))
        self._end_trace_tasks.add(task)
        task.add_done_callback(self._end_trace_tasks.discard)

    def end_all_traces_in_context(
        self,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> Callable:
        # BackgroundTasks run in different context, so we need to copy the context
        context = contextvars.copy_context()

        async def async_end_traces_func():
            await asyncio.create_task(self.end_all_traces(outputs, error), context=context)

        return async_end_traces_func

    async def end_all_traces(self, outputs: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        if not self.tracing_service:
            return
        self._end_time = datetime.now(timezone.utc)
        if outputs is None:
            outputs = {}
        outputs |= self.metadata
        await self.tracing_service.end_tracers(outputs, error)

    @property
    def sorted_vertices_layers(self) -> list[list[str]]:
        """Returns the sorted layers of vertex IDs by type.

        Each layer in the returned list contains vertex IDs grouped by their classification,
        such as input, output, session, or state vertices. Sorting is performed if not already done.
        """
        if not self._sorted_vertices_layers:
            self.sort_vertices()
        return self._sorted_vertices_layers

    def define_vertices_lists(self) -> None:
        """Populates internal lists of input, output, session ID, and state vertex IDs.

        Iterates over all vertices and appends their IDs to the corresponding internal lists
        based on their classification.
        """
        for vertex in self.vertices:
            if vertex.is_input:
                self._is_input_vertices.append(vertex.id)
            if vertex.is_output:
                self._is_output_vertices.append(vertex.id)
            if vertex.has_session_id:
                self.has_session_id_vertices.append(vertex.id)
            if vertex.is_state:
                if self._is_state_vertices is None:
                    self._is_state_vertices = []
                self._is_state_vertices.append(vertex.id)

    def _set_inputs(self, input_components: list[str], inputs: dict[str, str], input_type: InputType | None) -> None:
        """Updates input vertices' parameters with the provided inputs, filtering by component list and input type.

        Only vertices whose IDs or display names match the specified input components and whose IDs contain
        the input type (unless input type is 'any' or None) are updated. Raises a ValueError if a specified
        vertex is not found.
        """
        for vertex_id in self._is_input_vertices:
            vertex = self.get_vertex(vertex_id)
            # If the vertex is not in the input_components list
            if input_components and (vertex_id not in input_components and vertex.display_name not in input_components):
                continue
            # If the input_type is not any and the input_type is not in the vertex id
            # Example: input_type = "chat" and vertex.id = "OpenAI-19ddn"
            if input_type is not None and input_type != "any" and input_type not in vertex.id.lower():
                continue
            if vertex is None:
                msg = f"Vertex {vertex_id} not found"
                raise ValueError(msg)
            vertex.update_raw_params(inputs, overwrite=True)

    async def _run(
        self,
        *,
        inputs: dict[str, str],
        input_components: list[str],
        input_type: InputType | None,
        outputs: list[str],
        stream: bool,
        session_id: str,
        fallback_to_env_vars: bool,
        event_manager: EventManager | None = None,
    ) -> list[ResultData | None]:
        """Runs the graph with the given inputs.

        Args:
            inputs (Dict[str, str]): The input values for the graph.
            input_components (list[str]): The components to run for the inputs.
            input_type: (Optional[InputType]): The input type.
            outputs (list[str]): The outputs to retrieve from the graph.
            stream (bool): Whether to stream the results or not.
            session_id (str): The session ID for the graph.
            fallback_to_env_vars (bool): Whether to fallback to environment variables.
            event_manager (EventManager | None): The event manager for the graph.

        Returns:
            List[Optional["ResultData"]]: The outputs of the graph.
        """
        if input_components and not isinstance(input_components, list):
            msg = f"Invalid components value: {input_components}. Expected list"
            raise ValueError(msg)
        if input_components is None:
            input_components = []

        if not isinstance(inputs.get(INPUT_FIELD_NAME, ""), str):
            msg = f"Invalid input value: {inputs.get(INPUT_FIELD_NAME)}. Expected string"
            raise TypeError(msg)
        if inputs:
            self._set_inputs(input_components, inputs, input_type)
        # Update all the vertices with the session_id
        for vertex_id in self.has_session_id_vertices:
            vertex = self.get_vertex(vertex_id)
            if vertex is None:
                msg = f"Vertex {vertex_id} not found"
                raise ValueError(msg)
            vertex.update_raw_params({"session_id": session_id})
        # Process the graph
        try:
            cache_service = get_chat_service()
            if self.flow_id:
                await cache_service.set_cache(self.flow_id, self)
        except Exception:  # noqa: BLE001
            logger.exception("Error setting cache")

        try:
            # Prioritize the webhook component if it exists
            start_component_id = find_start_component_id(self._is_input_vertices)
            await self.process(
                start_component_id=start_component_id,
                fallback_to_env_vars=fallback_to_env_vars,
                event_manager=event_manager,
            )
            self.increment_run_count()
        except Exception as exc:
            self._end_all_traces_async(error=exc)
            msg = f"Error running graph: {exc}"
            raise ValueError(msg) from exc

        self._end_all_traces_async()
        # Get the outputs
        vertex_outputs = []
        for vertex in self.vertices:
            if not vertex.built:
                continue
            if vertex is None:
                msg = f"Vertex {vertex_id} not found"
                raise ValueError(msg)

            if not vertex.result and not stream and hasattr(vertex, "consume_async_generator"):
                await vertex.consume_async_generator()
            if (not outputs and vertex.is_output) or (vertex.display_name in outputs or vertex.id in outputs):
                vertex_outputs.append(vertex.result)

        return vertex_outputs

    async def arun(
        self,
        inputs: list[dict[str, str]],
        *,
        inputs_components: list[list[str]] | None = None,
        types: list[InputType | None] | None = None,
        outputs: list[str] | None = None,
        session_id: str | None = None,
        stream: bool = False,
        fallback_to_env_vars: bool = False,
        event_manager: EventManager | None = None,
    ) -> list[RunOutputs]:
        """Runs the graph with the given inputs.

        Args:
            inputs (list[Dict[str, str]]): The input values for the graph.
            inputs_components (Optional[list[list[str]]], optional): Components to run for the inputs. Defaults to None.
            types (Optional[list[Optional[InputType]]], optional): The types of the inputs. Defaults to None.
            outputs (Optional[list[str]], optional): The outputs to retrieve from the graph. Defaults to None.
            session_id (Optional[str], optional): The session ID for the graph. Defaults to None.
            stream (bool, optional): Whether to stream the results or not. Defaults to False.
            fallback_to_env_vars (bool, optional): Whether to fallback to environment variables. Defaults to False.
            event_manager (EventManager | None): The event manager for the graph.

        Returns:
            List[RunOutputs]: The outputs of the graph.
        """
        # inputs is {"message": "Hello, world!"}
        # we need to go through self.inputs and update the self.raw_params
        # of the vertices that are inputs
        # if the value is a list, we need to run multiple times
        vertex_outputs = []
        if not isinstance(inputs, list):
            inputs = [inputs]
        elif not inputs:
            inputs = [{}]
        # Length of all should be the as inputs length
        # just add empty lists to complete the length
        if inputs_components is None:
            inputs_components = []
        for _ in range(len(inputs) - len(inputs_components)):
            inputs_components.append([])
        if types is None:
            types = []
        if session_id:
            self.session_id = session_id
        for _ in range(len(inputs) - len(types)):
            types.append("chat")  # default to chat
        for run_inputs, components, input_type in zip(inputs, inputs_components, types, strict=True):
            run_outputs = await self._run(
                inputs=run_inputs,
                input_components=components,
                input_type=input_type,
                outputs=outputs or [],
                stream=stream,
                session_id=session_id or "",
                fallback_to_env_vars=fallback_to_env_vars,
                event_manager=event_manager,
            )
            run_output_object = RunOutputs(inputs=run_inputs, outputs=run_outputs)
            logger.debug(f"Run outputs: {run_output_object}")
            vertex_outputs.append(run_output_object)
        return vertex_outputs

    def next_vertex_to_build(self):
        """Returns the next vertex to be built.

        Yields:
            str: The ID of the next vertex to be built.
        """
        yield from chain.from_iterable(self.vertices_layers)

    @property
    def metadata(self):
        """The metadata of the graph.

        Returns:
            dict: The metadata of the graph.
        """
        time_format = "%Y-%m-%d %H:%M:%S %Z"
        return {
            "start_time": self._start_time.strftime(time_format),
            "end_time": self._end_time.strftime(time_format),
            "time_elapsed": f"{(self._end_time - self._start_time).total_seconds()} seconds",
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
        }

    def build_graph_maps(self, edges: list[CycleEdge] | None = None, vertices: list[Vertex] | None = None) -> None:
        """Builds the adjacency maps for the graph."""
        if edges is None:
            edges = self.edges

        if vertices is None:
            vertices = self.vertices

        self.predecessor_map, self.successor_map = self.build_adjacency_maps(edges)

        self.in_degree_map = self.build_in_degree(edges)
        self.parent_child_map = self.build_parent_child_map(vertices)

    def reset_inactivated_vertices(self) -> None:
        """Resets the inactivated vertices in the graph."""
        for vertex_id in self.inactivated_vertices.copy():
            self.mark_vertex(vertex_id, "ACTIVE")
        self.inactivated_vertices = set()
        self.inactivated_vertices = set()

    def mark_all_vertices(self, state: str) -> None:
        """Marks all vertices in the graph."""
        for vertex in self.vertices:
            vertex.set_state(state)

    def mark_vertex(self, vertex_id: str, state: str) -> None:
        """Marks a vertex in the graph."""
        vertex = self.get_vertex(vertex_id)
        vertex.set_state(state)
        if state == VertexStates.INACTIVE:
            self.run_manager.remove_from_predecessors(vertex_id)

    def _mark_branch(
        self, vertex_id: str, state: str, visited: set | None = None, output_name: str | None = None
    ) -> None:
        """Marks a branch of the graph."""
        if visited is None:
            visited = set()
        else:
            self.mark_vertex(vertex_id, state)
        if vertex_id in visited:
            return
        visited.add(vertex_id)

        for child_id in self.parent_child_map[vertex_id]:
            # Only child_id that have an edge with the vertex_id through the output_name
            # should be marked
            if output_name:
                edge = self.get_edge(vertex_id, child_id)
                if edge and edge.source_handle.name != output_name:
                    continue
            self._mark_branch(child_id, state, visited)

    def mark_branch(self, vertex_id: str, state: str, output_name: str | None = None) -> None:
        self._mark_branch(vertex_id=vertex_id, state=state, output_name=output_name)
        new_predecessor_map, _ = self.build_adjacency_maps(self.edges)
        self.run_manager.update_run_state(
            run_predecessors=new_predecessor_map,
            vertices_to_run=self.vertices_to_run,
        )

    def get_edge(self, source_id: str, target_id: str) -> CycleEdge | None:
        """Returns the edge between two vertices."""
        for edge in self.edges:
            if edge.source_id == source_id and edge.target_id == target_id:
                return edge
        return None

    def build_parent_child_map(self, vertices: list[Vertex]):
        parent_child_map = defaultdict(list)
        for vertex in vertices:
            parent_child_map[vertex.id] = [child.id for child in self.get_successors(vertex)]
        return parent_child_map

    def increment_run_count(self) -> None:
        self._runs += 1

    def increment_update_count(self) -> None:
        self._updates += 1

    def __getstate__(self):
        # Get all attributes that are useful in runs.
        # We don't need to save the state_manager because it is
        # a singleton and it is not necessary to save it
        return {
            "vertices": self.vertices,
            "edges": self.edges,
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
            "description": self.description,
            "user_id": self.user_id,
            "raw_graph_data": self.raw_graph_data,
            "top_level_vertices": self.top_level_vertices,
            "inactivated_vertices": self.inactivated_vertices,
            "run_manager": self.run_manager.to_dict(),
            "_run_id": self._run_id,
            "in_degree_map": self.in_degree_map,
            "parent_child_map": self.parent_child_map,
            "predecessor_map": self.predecessor_map,
            "successor_map": self.successor_map,
            "activated_vertices": self.activated_vertices,
            "vertices_layers": self.vertices_layers,
            "vertices_to_run": self.vertices_to_run,
            "stop_vertex": self.stop_vertex,
            "_run_queue": self._run_queue,
            "_first_layer": self._first_layer,
            "_vertices": self._vertices,
            "_edges": self._edges,
            "_is_input_vertices": self._is_input_vertices,
            "_is_output_vertices": self._is_output_vertices,
            "has_session_id_vertices": self.has_session_id_vertices,
            "_sorted_vertices_layers": self._sorted_vertices_layers,
        }

    def __deepcopy__(self, memo):
        # Check if we've already copied this instance
        if id(self) in memo:
            return memo[id(self)]

        if self._start is not None and self._end is not None:
            # Deep copy start and end components
            start_copy = copy.deepcopy(self._start, memo)
            end_copy = copy.deepcopy(self._end, memo)
            new_graph = type(self)(
                start_copy,
                end_copy,
                copy.deepcopy(self.flow_id, memo),
                copy.deepcopy(self.flow_name, memo),
                copy.deepcopy(self.user_id, memo),
            )
        else:
            # Create a new graph without start and end, but copy flow_id, flow_name, and user_id
            new_graph = type(self)(
                None,
                None,
                copy.deepcopy(self.flow_id, memo),
                copy.deepcopy(self.flow_name, memo),
                copy.deepcopy(self.user_id, memo),
            )
            # Deep copy vertices and edges
            new_graph.add_nodes_and_edges(copy.deepcopy(self._vertices, memo), copy.deepcopy(self._edges, memo))

        # Store the newly created object in memo
        memo[id(self)] = new_graph

        return new_graph

    def __setstate__(self, state):
        run_manager = state["run_manager"]
        if isinstance(run_manager, RunnableVerticesManager):
            state["run_manager"] = run_manager
        else:
            state["run_manager"] = RunnableVerticesManager.from_dict(run_manager)
        self.__dict__.update(state)
        self.vertex_map = {vertex.id: vertex for vertex in self.vertices}
        self.tracing_service = get_tracing_service()
        self.set_run_id(self._run_id)

    @classmethod
    def from_payload(
        cls,
        payload: dict,
        flow_id: str | None = None,
        flow_name: str | None = None,
        user_id: str | None = None,
    ) -> Graph:
        """Creates a graph from a payload.

        Args:
            payload: The payload to create the graph from.
            flow_id: The ID of the flow.
            flow_name: The flow name.
            user_id: The user ID.

        Returns:
            Graph: The created graph.
        """
        if "data" in payload:
            payload = payload["data"]
        try:
            vertices = payload["nodes"]
            edges = payload["edges"]
            graph = cls(flow_id=flow_id, flow_name=flow_name, user_id=user_id)
            graph.add_nodes_and_edges(vertices, edges)
        except KeyError as exc:
            logger.exception(exc)
            if "nodes" not in payload and "edges" not in payload:
                msg = f"Invalid payload. Expected keys 'nodes' and 'edges'. Found {list(payload.keys())}"
                raise ValueError(msg) from exc

            msg = f"Error while creating graph from payload: {exc}"
            raise ValueError(msg) from exc
        else:
            return graph

    def __eq__(self, /, other: object) -> bool:
        if not isinstance(other, Graph):
            return False
        return self.__repr__() == other.__repr__()

    # update this graph with another graph by comparing the __repr__ of each vertex
    # and if the __repr__ of a vertex is not the same as the other
    # then update the .data of the vertex to the self
    # both graphs have the same vertices and edges
    # but the data of the vertices might be different

    def update_edges_from_vertex(self, other_vertex: Vertex) -> None:
        """Updates the edges of a vertex in the Graph."""
        new_edges = []
        for edge in self.edges:
            if other_vertex.id in {edge.source_id, edge.target_id}:
                continue
            new_edges.append(edge)
        new_edges += other_vertex.edges
        self.edges = new_edges

    def vertex_data_is_identical(self, vertex: Vertex, other_vertex: Vertex) -> bool:
        data_is_equivalent = vertex == other_vertex
        if not data_is_equivalent:
            return False
        return self.vertex_edges_are_identical(vertex, other_vertex)

    @staticmethod
    def vertex_edges_are_identical(vertex: Vertex, other_vertex: Vertex) -> bool:
        same_length = len(vertex.edges) == len(other_vertex.edges)
        if not same_length:
            return False
        return all(edge in other_vertex.edges for edge in vertex.edges)

    def update(self, other: Graph) -> Graph:
        # Existing vertices in self graph
        existing_vertex_ids = {vertex.id for vertex in self.vertices}
        # Vertex IDs in the other graph
        other_vertex_ids = set(other.vertex_map.keys())

        # Find vertices that are in other but not in self (new vertices)
        new_vertex_ids = other_vertex_ids - existing_vertex_ids

        # Find vertices that are in self but not in other (removed vertices)
        removed_vertex_ids = existing_vertex_ids - other_vertex_ids

        # Remove vertices that are not in the other graph
        for vertex_id in removed_vertex_ids:
            with contextlib.suppress(ValueError):
                self.remove_vertex(vertex_id)

        # The order here matters because adding the vertex is required
        # if any of them have edges that point to any of the new vertices
        # By adding them first, them adding the edges we ensure that the
        # edges have valid vertices to point to

        # Add new vertices
        for vertex_id in new_vertex_ids:
            new_vertex = other.get_vertex(vertex_id)
            self._add_vertex(new_vertex)

        # Now update the edges
        for vertex_id in new_vertex_ids:
            new_vertex = other.get_vertex(vertex_id)
            self._update_edges(new_vertex)
            # Graph is set at the end because the edges come from the graph
            # and the other graph is where the new edges and vertices come from
            new_vertex.graph = self

        # Update existing vertices that have changed
        for vertex_id in existing_vertex_ids.intersection(other_vertex_ids):
            self_vertex = self.get_vertex(vertex_id)
            other_vertex = other.get_vertex(vertex_id)
            # If the vertices are not identical, update the vertex
            if not self.vertex_data_is_identical(self_vertex, other_vertex):
                self.update_vertex_from_another(self_vertex, other_vertex)

        self.build_graph_maps()
        self.define_vertices_lists()
        self.increment_update_count()
        return self

    def update_vertex_from_another(self, vertex: Vertex, other_vertex: Vertex) -> None:
        """Updates a vertex from another vertex.

        Args:
            vertex (Vertex): The vertex to be updated.
            other_vertex (Vertex): The vertex to update from.
        """
        vertex.full_data = other_vertex.full_data
        vertex.parse_data()
        # Now we update the edges of the vertex
        self.update_edges_from_vertex(other_vertex)
        vertex.params = {}
        vertex.build_params()
        vertex.graph = self
        # If the vertex is frozen, we don't want
        # to reset the results nor the built attribute
        if not vertex.frozen:
            vertex.built = False
            vertex.result = None
            vertex.artifacts = {}
            vertex.set_top_level(self.top_level_vertices)
        self.reset_all_edges_of_vertex(vertex)

    def reset_all_edges_of_vertex(self, vertex: Vertex) -> None:
        """Resets all the edges of a vertex."""
        for edge in vertex.edges:
            for vid in [edge.source_id, edge.target_id]:
                if vid in self.vertex_map:
                    vertex_ = self.vertex_map[vid]
                    if not vertex_.frozen:
                        vertex_.build_params()

    def _add_vertex(self, vertex: Vertex) -> None:
        """Adds a vertex to the graph."""
        self.vertices.append(vertex)
        self.vertex_map[vertex.id] = vertex

    def add_vertex(self, vertex: Vertex) -> None:
        """Adds a new vertex to the graph."""
        self._add_vertex(vertex)
        self._update_edges(vertex)

    def _update_edges(self, vertex: Vertex) -> None:
        """Updates the edges of a vertex."""
        # Vertex has edges, so we need to update the edges
        for edge in vertex.edges:
            if edge not in self.edges and edge.source_id in self.vertex_map and edge.target_id in self.vertex_map:
                self.edges.append(edge)

    def _build_graph(self) -> None:
        """Builds the graph from the vertices and edges."""
        self.vertices = self._build_vertices()
        self.vertex_map = {vertex.id: vertex for vertex in self.vertices}
        self.edges = self._build_edges()

        # This is a hack to make sure that the LLM vertex is sent to
        # the toolkit vertex
        self._build_vertex_params()
        self._instantiate_components_in_vertices()
        self._set_cache_to_vertices_in_cycle()
        self._set_cache_if_listen_notify_components()
        for vertex in self.vertices:
            if vertex.id in self.cycle_vertices:
                self.run_manager.add_to_cycle_vertices(vertex.id)

    def _get_edges_as_list_of_tuples(self) -> list[tuple[str, str]]:
        """Returns the edges of the graph as a list of tuples.

        Each tuple contains the source and target handle IDs from the edge data.

        Returns:
            list[tuple[str, str]]: List of (source_id, target_id) tuples representing graph edges.
        """
        return [(e["data"]["sourceHandle"]["id"], e["data"]["targetHandle"]["id"]) for e in self._edges]

    def _set_cache_if_listen_notify_components(self) -> None:
        """Disables caching for all vertices if Listen/Notify components are present.

        If the graph contains any Listen or Notify components, caching is disabled for all vertices
        by setting cache=False on their outputs. This ensures proper handling of real-time
        communication between components.
        """
        has_listen_or_notify_component = any(
            vertex.id.split("-")[0] in {"Listen", "Notify"} for vertex in self.vertices
        )
        if has_listen_or_notify_component:
            for vertex in self.vertices:
                vertex.apply_on_outputs(lambda output_object: setattr(output_object, "cache", False))

    def _set_cache_to_vertices_in_cycle(self) -> None:
        """Sets the cache to the vertices in cycle."""
        edges = self._get_edges_as_list_of_tuples()
        cycle_vertices = set(find_cycle_vertices(edges))
        for vertex in self.vertices:
            if vertex.id in cycle_vertices:
                vertex.apply_on_outputs(lambda output_object: setattr(output_object, "cache", False))

    def _instantiate_components_in_vertices(self) -> None:
        """Instantiates the components in the vertices."""
        for vertex in self.vertices:
            vertex.instantiate_component(self.user_id)

    def remove_vertex(self, vertex_id: str) -> None:
        """Removes a vertex from the graph."""
        vertex = self.get_vertex(vertex_id)
        if vertex is None:
            return
        self.vertices.remove(vertex)
        self.vertex_map.pop(vertex_id)
        self.edges = [edge for edge in self.edges if vertex_id not in {edge.source_id, edge.target_id}]

    def _build_vertex_params(self) -> None:
        """Identifies and handles the LLM vertex within the graph."""
        for vertex in self.vertices:
            vertex.build_params()

    def _validate_vertex(self, vertex: Vertex) -> bool:
        """Validates a vertex."""
        # All vertices that do not have edges are invalid
        return len(self.get_vertex_edges(vertex.id)) > 0

    def get_vertex(self, vertex_id: str) -> Vertex:
        """Returns a vertex by id."""
        try:
            return self.vertex_map[vertex_id]
        except KeyError as e:
            msg = f"Vertex {vertex_id} not found"
            raise ValueError(msg) from e

    def get_root_of_group_node(self, vertex_id: str) -> Vertex:
        """Returns the root of a group node."""
        if vertex_id in self.top_level_vertices:
            # Get all vertices with vertex_id as .parent_node_id
            # then get the one at the top
            vertices = [vertex for vertex in self.vertices if vertex.parent_node_id == vertex_id]
            # Now go through successors of the vertices
            # and get the one that none of its successors is in vertices
            for vertex in vertices:
                successors = self.get_all_successors(vertex, recursive=False)
                if not any(successor in vertices for successor in successors):
                    return vertex
        msg = f"Vertex {vertex_id} is not a top level vertex or no root vertex found"
        raise ValueError(msg)

    def get_next_in_queue(self):
        if not self._run_queue:
            return None
        return self._run_queue.popleft()

    def extend_run_queue(self, vertices: list[str]) -> None:
        self._run_queue.extend(vertices)

    async def astep(
        self,
        inputs: InputValueRequest | list[dict] | None = None,
        files: list[str] | None = None,
        user_id: str | None = None,
        event_manager: EventManager | None = None,
    ):
        if not self._prepared:
            msg = "Graph not prepared. Call prepare() first."
            raise ValueError(msg)
        if not self._run_queue:
            self._end_all_traces_async()
            return Finish()
        vertex_id = self.get_next_in_queue()
        chat_service = get_chat_service()
        vertex_build_result = await self.build_vertex(
            vertex_id=vertex_id,
            user_id=user_id,
            inputs_dict=inputs.model_dump() if inputs and hasattr(inputs, "model_dump") else None,
            files=files,
            get_cache=chat_service.get_cache,
            set_cache=chat_service.set_cache,
            event_manager=event_manager,
        )

        next_runnable_vertices = await self.get_next_runnable_vertices(
            self._lock, vertex=vertex_build_result.vertex, cache=False
        )
        if self.stop_vertex and self.stop_vertex in next_runnable_vertices:
            next_runnable_vertices = [self.stop_vertex]
        self.extend_run_queue(next_runnable_vertices)
        self.reset_inactivated_vertices()
        self.reset_activated_vertices()

        await chat_service.set_cache(str(self.flow_id or self._run_id), self)
        self._record_snapshot(vertex_id)
        return vertex_build_result

    def get_snapshot(self):
        return copy.deepcopy(
            {
                "run_manager": self.run_manager.to_dict(),
                "run_queue": self._run_queue,
                "vertices_layers": self.vertices_layers,
                "first_layer": self.first_layer,
                "inactive_vertices": self.inactive_vertices,
                "activated_vertices": self.activated_vertices,
            }
        )

    def _record_snapshot(self, vertex_id: str | None = None) -> None:
        self._snapshots.append(self.get_snapshot())
        if vertex_id:
            self._call_order.append(vertex_id)

    def step(
        self,
        inputs: InputValueRequest | None = None,
        files: list[str] | None = None,
        user_id: str | None = None,
    ):
        """Runs the next vertex in the graph.

        Note:
            This function is a synchronous wrapper around `astep`.
            It creates an event loop if one does not exist.

        Args:
            inputs: The inputs for the vertex. Defaults to None.
            files: The files for the vertex. Defaults to None.
            user_id: The user ID. Defaults to None.
        """
        return run_until_complete(self.astep(inputs, files, user_id))

    async def build_vertex(
        self,
        vertex_id: str,
        *,
        get_cache: GetCache | None = None,
        set_cache: SetCache | None = None,
        inputs_dict: dict[str, str] | None = None,
        files: list[str] | None = None,
        user_id: str | None = None,
        fallback_to_env_vars: bool = False,
        event_manager: EventManager | None = None,
    ) -> VertexBuildResult:
        """Builds a vertex in the graph.

        Args:
            vertex_id (str): The ID of the vertex to build.
            get_cache (GetCache): A coroutine to get the cache.
            set_cache (SetCache): A coroutine to set the cache.
            inputs_dict (Optional[Dict[str, str]]): Optional dictionary of inputs for the vertex. Defaults to None.
            files: (Optional[List[str]]): Optional list of files. Defaults to None.
            user_id (Optional[str]): Optional user ID. Defaults to None.
            fallback_to_env_vars (bool): Whether to fallback to environment variables. Defaults to False.
            event_manager (Optional[EventManager]): Optional event manager. Defaults to None.

        Returns:
            Tuple: A tuple containing the next runnable vertices, top level vertices, result dictionary,
            parameters, validity flag, artifacts, and the built vertex.

        Raises:
            ValueError: If no result is found for the vertex.
        """
        vertex = self.get_vertex(vertex_id)
        self.run_manager.add_to_vertices_being_run(vertex_id)
        try:
            params = ""
            should_build = False
            if not vertex.frozen:
                should_build = True
            else:
                # Check the cache for the vertex
                if get_cache is not None:
                    cached_result = await get_cache(key=vertex.id)
                else:
                    cached_result = CacheMiss()
                if isinstance(cached_result, CacheMiss):
                    should_build = True
                else:
                    try:
                        cached_vertex_dict = cached_result["result"]
                        # Now set update the vertex with the cached vertex
                        vertex.built = cached_vertex_dict["built"]
                        vertex.artifacts = cached_vertex_dict["artifacts"]
                        vertex.built_object = cached_vertex_dict["built_object"]
                        vertex.built_result = cached_vertex_dict["built_result"]
                        vertex.full_data = cached_vertex_dict["full_data"]
                        vertex.results = cached_vertex_dict["results"]
                        try:
                            vertex.finalize_build()

                            if vertex.result is not None:
                                vertex.result.used_frozen_result = True
                        except Exception:  # noqa: BLE001
                            logger.opt(exception=True).debug("Error finalizing build")
                            should_build = True
                    except KeyError:
                        should_build = True

            if should_build:
                await vertex.build(
                    user_id=user_id,
                    inputs=inputs_dict,
                    fallback_to_env_vars=fallback_to_env_vars,
                    files=files,
                    event_manager=event_manager,
                )
                if set_cache is not None:
                    vertex_dict = {
                        "built": vertex.built,
                        "results": vertex.results,
                        "artifacts": vertex.artifacts,
                        "built_object": vertex.built_object,
                        "built_result": vertex.built_result,
                        "full_data": vertex.full_data,
                    }

                    await set_cache(key=vertex.id, data=vertex_dict)

        except Exception as exc:
            if not isinstance(exc, ComponentBuildError):
                logger.exception("Error building Component")
            raise

        if vertex.result is not None:
            params = f"{vertex.built_object_repr()}{params}"
            valid = True
            result_dict = vertex.result
            artifacts = vertex.artifacts
        else:
            msg = f"Error building Component: no result found for vertex {vertex_id}"
            raise ValueError(msg)

        return VertexBuildResult(
            result_dict=result_dict, params=params, valid=valid, artifacts=artifacts, vertex=vertex
        )

    def get_vertex_edges(
        self,
        vertex_id: str,
        *,
        is_target: bool | None = None,
        is_source: bool | None = None,
    ) -> list[CycleEdge]:
        """Returns a list of edges for a given vertex."""
        # The idea here is to return the edges that have the vertex_id as source or target
        # or both
        return [
            edge
            for edge in self.edges
            if (edge.source_id == vertex_id and is_source is not False)
            or (edge.target_id == vertex_id and is_target is not False)
        ]

    def get_vertices_with_target(self, vertex_id: str) -> list[Vertex]:
        """Returns the vertices connected to a vertex."""
        vertices: list[Vertex] = []
        for edge in self.edges:
            if edge.target_id == vertex_id:
                vertex = self.get_vertex(edge.source_id)
                if vertex is None:
                    continue
                vertices.append(vertex)
        return vertices

    async def process(
        self,
        *,
        fallback_to_env_vars: bool,
        start_component_id: str | None = None,
        event_manager: EventManager | None = None,
    ) -> Graph:
        """Processes the graph with vertices in each layer run in parallel."""
        has_webhook_component = "webhook" in start_component_id.lower() if start_component_id else False
        first_layer = self.sort_vertices(start_component_id=start_component_id)
        vertex_task_run_count: dict[str, int] = {}
        to_process = deque(first_layer)
        layer_index = 0
        chat_service = get_chat_service()
        await self.initialize_run()
        lock = asyncio.Lock()
        while to_process:
            current_batch = list(to_process)  # Copy current deque items to a list
            to_process.clear()  # Clear the deque for new items
            tasks = []
            for vertex_id in current_batch:
                vertex = self.get_vertex(vertex_id)
                task = asyncio.create_task(
                    self.build_vertex(
                        vertex_id=vertex_id,
                        user_id=self.user_id,
                        inputs_dict={},
                        fallback_to_env_vars=fallback_to_env_vars,
                        get_cache=chat_service.get_cache,
                        set_cache=chat_service.set_cache,
                        event_manager=event_manager,
                    ),
                    name=f"{vertex.id} Run {vertex_task_run_count.get(vertex_id, 0)}",
                )
                tasks.append(task)
                vertex_task_run_count[vertex_id] = vertex_task_run_count.get(vertex_id, 0) + 1

            logger.debug(f"Running layer {layer_index} with {len(tasks)} tasks, {current_batch}")
            try:
                next_runnable_vertices = await self._execute_tasks(
                    tasks, lock=lock, has_webhook_component=has_webhook_component
                )
            except Exception:
                logger.exception(f"Error executing tasks in layer {layer_index}")
                raise
            if not next_runnable_vertices:
                break
            to_process.extend(next_runnable_vertices)
            layer_index += 1

        logger.debug("Graph processing complete")
        return self

    def find_next_runnable_vertices(self, vertex_successors_ids: list[str]) -> list[str]:
        """Determines the next set of runnable vertices from a list of successor vertex IDs.

        For each successor, if it is not runnable, recursively finds its runnable
        predecessors; otherwise, includes the successor itself. Returns a sorted list of all such vertex IDs.
        """
        next_runnable_vertices = set()
        for v_id in sorted(vertex_successors_ids):
            if not self.is_vertex_runnable(v_id):
                next_runnable_vertices.update(self.find_runnable_predecessors_for_successor(v_id))
            else:
                next_runnable_vertices.add(v_id)

        return sorted(next_runnable_vertices)

    async def get_next_runnable_vertices(self, lock: asyncio.Lock, vertex: Vertex, *, cache: bool = True) -> list[str]:
        """Determines the next set of runnable vertex IDs after a vertex completes execution.

        If the completed vertex is a state vertex, any recently activated state vertices are also included.
        Updates the run manager to reflect the new runnable state and optionally caches the updated graph state.

        Args:
            lock: An asyncio lock for thread-safe updates.
            vertex: The vertex that has just finished execution.
            cache: If True, caches the updated graph state.

        Returns:
            A list of vertex IDs that are ready to be executed next.
        """
        v_id = vertex.id
        v_successors_ids = vertex.successors_ids
        self.run_manager.ran_at_least_once.add(v_id)
        async with lock:
            self.run_manager.remove_vertex_from_runnables(v_id)
            next_runnable_vertices = self.find_next_runnable_vertices(v_successors_ids)

            for next_v_id in set(next_runnable_vertices):  # Use set to avoid duplicates
                if next_v_id == v_id:
                    next_runnable_vertices.remove(v_id)
                else:
                    self.run_manager.add_to_vertices_being_run(next_v_id)
            if cache and self.flow_id is not None:
                set_cache_coro = partial(get_chat_service().set_cache, key=self.flow_id)
                await set_cache_coro(data=self, lock=lock)
        if vertex.is_state:
            next_runnable_vertices.extend(self.activated_vertices)
        return next_runnable_vertices

    async def _log_vertex_build_from_exception(self, vertex_id: str, result: Exception) -> None:
        """Logs detailed information about a vertex build exception.

        Formats the exception message and stack trace, constructs an error output,
        and records the failure using the vertex build logging system.
        """
        if isinstance(result, ComponentBuildError):
            params = result.message
            tb = result.formatted_traceback
        else:
            from langflow.api.utils import format_exception_message

            tb = traceback.format_exc()
            logger.exception("Error building Component")

            params = format_exception_message(result)
        message = {"errorMessage": params, "stackTrace": tb}
        vertex = self.get_vertex(vertex_id)
        output_label = vertex.outputs[0]["name"] if vertex.outputs else "output"
        outputs = {output_label: OutputValue(message=message, type="error")}
        result_data_response = {
            "results": {},
            "outputs": outputs,
            "logs": {},
            "message": {},
            "artifacts": {},
            "timedelta": None,
            "duration": None,
            "used_frozen_result": False,
        }

        await log_vertex_build(
            flow_id=self.flow_id or "",
            vertex_id=vertex_id or "errors",
            valid=False,
            params=params,
            data=result_data_response,
            artifacts={},
        )

    async def _execute_tasks(
        self, tasks: list[asyncio.Task], lock: asyncio.Lock, *, has_webhook_component: bool = False
    ) -> list[str]:
        """Executes tasks in parallel, handling exceptions for each task.

        Args:
            tasks: List of tasks to execute
            lock: Async lock for synchronization
            has_webhook_component: Whether the graph has a webhook component
        """
        results = []
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        vertices: list[Vertex] = []

        for i, result in enumerate(completed_tasks):
            task_name = tasks[i].get_name()
            vertex_id = tasks[i].get_name().split(" ")[0]

            if isinstance(result, Exception):
                logger.error(f"Task {task_name} failed with exception: {result}")
                if has_webhook_component:
                    await self._log_vertex_build_from_exception(vertex_id, result)

                # Cancel all remaining tasks
                for t in tasks[i + 1 :]:
                    t.cancel()
                raise result
            if isinstance(result, VertexBuildResult):
                await log_vertex_build(
                    flow_id=self.flow_id or "",
                    vertex_id=result.vertex.id,
                    valid=result.valid,
                    params=result.params,
                    data=result.result_dict,
                    artifacts=result.artifacts,
                )

                vertices.append(result.vertex)
            else:
                msg = f"Invalid result from task {task_name}: {result}"
                raise TypeError(msg)

        for v in vertices:
            # set all executed vertices as non-runnable to not run them again.
            # they could be calculated as predecessor or successors of parallel vertices
            # This could usually happen with input vertices like ChatInput
            self.run_manager.remove_vertex_from_runnables(v.id)

            logger.debug(f"Vertex {v.id}, result: {v.built_result}, object: {v.built_object}")

        for v in vertices:
            next_runnable_vertices = await self.get_next_runnable_vertices(lock, vertex=v, cache=False)
            results.extend(next_runnable_vertices)
        return list(set(results))

    def topological_sort(self) -> list[Vertex]:
        """Performs a topological sort of the vertices in the graph.

        Returns:
            List[Vertex]: A list of vertices in topological order.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        # States: 0 = unvisited, 1 = visiting, 2 = visited
        state = dict.fromkeys(self.vertices, 0)
        sorted_vertices = []

        def dfs(vertex) -> None:
            if state[vertex] == 1:
                # We have a cycle
                msg = "Graph contains a cycle, cannot perform topological sort"
                raise ValueError(msg)
            if state[vertex] == 0:
                state[vertex] = 1
                for edge in vertex.edges:
                    if edge.source_id == vertex.id:
                        dfs(self.get_vertex(edge.target_id))
                state[vertex] = 2
                sorted_vertices.append(vertex)

        # Visit each vertex
        for vertex in self.vertices:
            if state[vertex] == 0:
                dfs(vertex)

        return list(reversed(sorted_vertices))

    def generator_build(self) -> Generator[Vertex, None, None]:
        """Builds each vertex in the graph and yields it."""
        sorted_vertices = self.topological_sort()
        logger.debug("There are %s vertices in the graph", len(sorted_vertices))
        yield from sorted_vertices

    def get_predecessors(self, vertex):
        """Returns the predecessors of a vertex."""
        return [self.get_vertex(source_id) for source_id in self.predecessor_map.get(vertex.id, [])]

    def get_all_successors(self, vertex: Vertex, *, recursive=True, flat=True, visited=None):
        """Returns all successors of a given vertex, optionally recursively and as a flat or nested list.

        Args:
            vertex: The vertex whose successors are to be retrieved.
            recursive: If True, retrieves successors recursively; otherwise, only immediate successors.
            flat: If True, returns a flat list of successors; if False, returns a nested list structure.
            visited: Internal set used to track visited vertices and prevent cycles.

        Returns:
            A list of successor vertices, either flat or nested depending on the `flat` parameter.
        """
        if visited is None:
            visited = set()

        # Prevent revisiting vertices to avoid infinite loops in cyclic graphs
        if vertex in visited:
            return []

        visited.add(vertex)

        successors = vertex.successors
        if not successors:
            return []

        successors_result = []

        for successor in successors:
            if recursive:
                next_successors = self.get_all_successors(successor, recursive=recursive, flat=flat, visited=visited)
                if flat:
                    successors_result.extend(next_successors)
                else:
                    successors_result.append(next_successors)
            if flat:
                successors_result.append(successor)
            else:
                successors_result.append([successor])

        if not flat and successors_result:
            return [successors, *successors_result]

        return successors_result

    def get_successors(self, vertex: Vertex) -> list[Vertex]:
        """Returns the immediate successor vertices of the given vertex.

        Args:
            vertex: The vertex whose successors are to be retrieved.

        Returns:
            A list of vertices that are direct successors of the specified vertex.
        """
        return [self.get_vertex(target_id) for target_id in self.successor_map.get(vertex.id, set())]

    def get_all_predecessors(self, vertex: Vertex, *, recursive: bool = True) -> list[Vertex]:
        """Retrieves all predecessor vertices of a given vertex.

        If `recursive` is True, returns both direct and indirect predecessors by
        traversing the graph recursively. If False, returns only the immediate predecessors.
        """
        _predecessors = self.predecessor_map.get(vertex.id, [])
        predecessors = [self.get_vertex(v_id) for v_id in _predecessors]
        if recursive:
            for predecessor in _predecessors:
                predecessors.extend(self.get_all_predecessors(self.get_vertex(predecessor), recursive=recursive))
        else:
            predecessors.extend([self.get_vertex(predecessor) for predecessor in _predecessors])
        return predecessors

    def get_vertex_neighbors(self, vertex: Vertex) -> dict[Vertex, int]:
        """Returns a dictionary mapping each direct neighbor of a vertex to the count of connecting edges.

        A neighbor is any vertex directly connected to the input vertex, either as a source or target.
        The count reflects the number of edges between the input vertex and each neighbor.
        """
        neighbors: dict[Vertex, int] = {}
        for edge in self.edges:
            if edge.source_id == vertex.id:
                neighbor = self.get_vertex(edge.target_id)
                if neighbor is None:
                    continue
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
            elif edge.target_id == vertex.id:
                neighbor = self.get_vertex(edge.source_id)
                if neighbor is None:
                    continue
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
        return neighbors

    @property
    def cycles(self):
        if self._cycles is None:
            if self._start is None:
                self._cycles = []
            else:
                entry_vertex = self._start._id
                edges = [(e["data"]["sourceHandle"]["id"], e["data"]["targetHandle"]["id"]) for e in self._edges]
                self._cycles = find_all_cycle_edges(entry_vertex, edges)
        return self._cycles

    @property
    def cycle_vertices(self):
        if self._cycle_vertices is None:
            edges = self._get_edges_as_list_of_tuples()
            self._cycle_vertices = set(find_cycle_vertices(edges))
        return self._cycle_vertices

    def _build_edges(self) -> list[CycleEdge]:
        """Builds the edges of the graph."""
        # Edge takes two vertices as arguments, so we need to build the vertices first
        # and then build the edges
        # if we can't find a vertex, we raise an error
        edges: set[CycleEdge | Edge] = set()
        for edge in self._edges:
            new_edge = self.build_edge(edge)
            edges.add(new_edge)
        if self.vertices and not edges:
            logger.warning("Graph has vertices but no edges")
        return list(cast("Iterable[CycleEdge]", edges))

    def build_edge(self, edge: EdgeData) -> CycleEdge | Edge:
        source = self.get_vertex(edge["source"])
        target = self.get_vertex(edge["target"])

        if source is None:
            msg = f"Source vertex {edge['source']} not found"
            raise ValueError(msg)
        if target is None:
            msg = f"Target vertex {edge['target']} not found"
            raise ValueError(msg)
        if any(v in self.cycle_vertices for v in [source.id, target.id]):
            new_edge: CycleEdge | Edge = CycleEdge(source, target, edge)
        else:
            new_edge = Edge(source, target, edge)
        return new_edge

    @staticmethod
    def _get_vertex_class(node_type: str, node_base_type: str, node_id: str) -> type[Vertex]:
        """Returns the node class based on the node type."""
        # First we check for the node_base_type
        node_name = node_id.split("-")[0]
        if node_name in InterfaceComponentTypes or node_type in InterfaceComponentTypes:
            return InterfaceVertex
        if node_name in {"SharedState", "Notify", "Listen"}:
            return StateVertex
        if node_base_type in lazy_load_vertex_dict.vertex_type_map:
            return lazy_load_vertex_dict.vertex_type_map[node_base_type]
        if node_name in lazy_load_vertex_dict.vertex_type_map:
            return lazy_load_vertex_dict.vertex_type_map[node_name]

        if node_type in lazy_load_vertex_dict.vertex_type_map:
            return lazy_load_vertex_dict.vertex_type_map[node_type]
        return Vertex

    def _build_vertices(self) -> list[Vertex]:
        """Builds the vertices of the graph."""
        vertices: list[Vertex] = []
        for frontend_data in self._vertices:
            if frontend_data.get("type") == NodeTypeEnum.NoteNode:
                continue
            try:
                vertex_instance = self.get_vertex(frontend_data["id"])
            except ValueError:
                vertex_instance = self._create_vertex(frontend_data)
            vertices.append(vertex_instance)

        return vertices

    def _create_vertex(self, frontend_data: NodeData):
        vertex_data = frontend_data["data"]
        vertex_type: str = vertex_data["type"]
        vertex_base_type: str = vertex_data["node"]["template"]["_type"]
        if "id" not in vertex_data:
            msg = f"Vertex data for {vertex_data['display_name']} does not contain an id"
            raise ValueError(msg)

        vertex_class = self._get_vertex_class(vertex_type, vertex_base_type, vertex_data["id"])

        vertex_instance = vertex_class(frontend_data, graph=self)
        vertex_instance.set_top_level(self.top_level_vertices)
        return vertex_instance

    def prepare(self, stop_component_id: str | None = None, start_component_id: str | None = None):
        self.initialize()
        if stop_component_id and start_component_id:
            msg = "You can only provide one of stop_component_id or start_component_id"
            raise ValueError(msg)

        if stop_component_id or start_component_id:
            try:
                first_layer = self.sort_vertices(stop_component_id, start_component_id)
            except Exception:  # noqa: BLE001
                logger.exception("Error sorting vertices")
                first_layer = self.sort_vertices()
        else:
            first_layer = self.sort_vertices()

        for vertex_id in first_layer:
            self.run_manager.add_to_vertices_being_run(vertex_id)
            if vertex_id in self.cycle_vertices:
                self.run_manager.add_to_cycle_vertices(vertex_id)
        self._first_layer = sorted(first_layer)
        self._run_queue = deque(self._first_layer)
        self._prepared = True
        self._record_snapshot()
        return self

    @staticmethod
    def get_children_by_vertex_type(vertex: Vertex, vertex_type: str) -> list[Vertex]:
        """Returns the children of a vertex based on the vertex type."""
        children = []
        vertex_types = [vertex.data["type"]]
        if "node" in vertex.data:
            vertex_types += vertex.data["node"]["base_classes"]
        if vertex_type in vertex_types:
            children.append(vertex)
        return children

    def __repr__(self) -> str:
        vertex_ids = [vertex.id for vertex in self.vertices]
        edges_repr = "\n".join([f"  {edge.source_id} --> {edge.target_id}" for edge in self.edges])

        return (
            f"Graph Representation:\n"
            f"----------------------\n"
            f"Vertices ({len(vertex_ids)}):\n"
            f"  {', '.join(map(str, vertex_ids))}\n\n"
            f"Edges ({len(self.edges)}):\n"
            f"{edges_repr}"
        )

    def get_vertex_predecessors_ids(self, vertex_id: str) -> list[str]:
        """Get the predecessor IDs of a vertex."""
        return [v.id for v in self.get_predecessors(self.get_vertex(vertex_id))]

    def get_vertex_successors_ids(self, vertex_id: str) -> list[str]:
        """Get the successor IDs of a vertex."""
        return [v.id for v in self.get_vertex(vertex_id).successors]

    def get_vertex_input_status(self, vertex_id: str) -> bool:
        """Check if a vertex is an input vertex."""
        return self.get_vertex(vertex_id).is_input

    def get_parent_map(self) -> dict[str, str | None]:
        """Get the parent node map for all vertices."""
        return {vertex.id: vertex.parent_node_id for vertex in self.vertices}

    def get_vertex_ids(self) -> list[str]:
        """Get all vertex IDs in the graph."""
        return [vertex.id for vertex in self.vertices]

    def sort_vertices(
        self,
        stop_component_id: str | None = None,
        start_component_id: str | None = None,
    ) -> list[str]:
        """Sorts the vertices in the graph."""
        self.mark_all_vertices("ACTIVE")

        first_layer, remaining_layers = get_sorted_vertices(
            vertices_ids=self.get_vertex_ids(),
            cycle_vertices=self.cycle_vertices,
            stop_component_id=stop_component_id,
            start_component_id=start_component_id,
            graph_dict=self.__to_dict(),
            in_degree_map=self.in_degree_map,
            successor_map=self.successor_map,
            predecessor_map=self.predecessor_map,
            is_input_vertex=self.get_vertex_input_status,
            get_vertex_predecessors=self.get_vertex_predecessors_ids,
            get_vertex_successors=self.get_vertex_successors_ids,
            is_cyclic=self.is_cyclic,
        )

        self.increment_run_count()
        self._sorted_vertices_layers = [first_layer, *remaining_layers]
        self.vertices_layers = remaining_layers
        self.vertices_to_run = set(chain.from_iterable([first_layer, *remaining_layers]))
        self.build_run_map()
        self._first_layer = first_layer
        return first_layer

    @staticmethod
    def sort_interface_components_first(vertices_layers: list[list[str]]) -> list[list[str]]:
        """Sorts the vertices in the graph so that vertices containing ChatInput or ChatOutput come first."""

        def contains_interface_component(vertex):
            return any(component.value in vertex for component in InterfaceComponentTypes)

        # Sort each inner list so that vertices containing ChatInput or ChatOutput come first
        return [
            sorted(
                inner_list,
                key=lambda vertex: not contains_interface_component(vertex),
            )
            for inner_list in vertices_layers
        ]

    def sort_by_avg_build_time(self, vertices_layers: list[list[str]]) -> list[list[str]]:
        """Sorts the vertices in the graph so that vertices with the lowest average build time come first."""

        def sort_layer_by_avg_build_time(vertices_ids: list[str]) -> list[str]:
            """Sorts the vertices in the graph so that vertices with the lowest average build time come first."""
            if len(vertices_ids) == 1:
                return vertices_ids
            vertices_ids.sort(key=lambda vertex_id: self.get_vertex(vertex_id).avg_build_time)

            return vertices_ids

        return [sort_layer_by_avg_build_time(layer) for layer in vertices_layers]

    def is_vertex_runnable(self, vertex_id: str) -> bool:
        """Returns whether a vertex is runnable."""
        is_active = self.get_vertex(vertex_id).is_active()
        is_loop = self.get_vertex(vertex_id).is_loop
        return self.run_manager.is_vertex_runnable(vertex_id, is_active=is_active, is_loop=is_loop)

    def build_run_map(self) -> None:
        """Builds the run map for the graph.

        This method is responsible for building the run map for the graph,
        which maps each node in the graph to its corresponding run function.
        """
        self.run_manager.build_run_map(predecessor_map=self.predecessor_map, vertices_to_run=self.vertices_to_run)

    def find_runnable_predecessors_for_successors(self, vertex_id: str) -> list[str]:
        """For each successor of the current vertex, find runnable predecessors if any.

        This checks the direct predecessors of each successor to identify any that are
        immediately runnable, expanding the search to ensure progress can be made.
        """
        runnable_vertices = []
        for successor_id in self.run_manager.run_map.get(vertex_id, []):
            runnable_vertices.extend(self.find_runnable_predecessors_for_successor(successor_id))

        return sorted(runnable_vertices)

    def find_runnable_predecessors_for_successor(self, vertex_id: str) -> list[str]:
        runnable_vertices = []
        visited = set()

        def find_runnable_predecessors(predecessor_id: str) -> None:
            if predecessor_id in visited:
                return
            visited.add(predecessor_id)
            predecessor_vertex = self.get_vertex(predecessor_id)
            is_active = predecessor_vertex.is_active()
            is_loop = predecessor_vertex.is_loop
            if self.run_manager.is_vertex_runnable(predecessor_id, is_active=is_active, is_loop=is_loop):
                runnable_vertices.append(predecessor_id)
            else:
                for pred_pred_id in self.run_manager.run_predecessors.get(predecessor_id, []):
                    find_runnable_predecessors(pred_pred_id)

        for predecessor_id in self.run_manager.run_predecessors.get(vertex_id, []):
            find_runnable_predecessors(predecessor_id)
        return runnable_vertices

    def remove_from_predecessors(self, vertex_id: str) -> None:
        self.run_manager.remove_from_predecessors(vertex_id)

    def remove_vertex_from_runnables(self, vertex_id: str) -> None:
        self.run_manager.remove_vertex_from_runnables(vertex_id)

    def get_top_level_vertices(self, vertices_ids):
        """Retrieves the top-level vertices from the given graph based on the provided vertex IDs.

        Args:
            vertices_ids (list): A list of vertex IDs.

        Returns:
            list: A list of top-level vertex IDs.

        """
        top_level_vertices = []
        for vertex_id in vertices_ids:
            vertex = self.get_vertex(vertex_id)
            if vertex.parent_is_top_level:
                top_level_vertices.append(vertex.parent_node_id)
            else:
                top_level_vertices.append(vertex_id)
        return top_level_vertices

    def build_in_degree(self, edges: list[CycleEdge]) -> dict[str, int]:
        in_degree: dict[str, int] = defaultdict(int)

        for edge in edges:
            # We don't need to count if a Component connects more than one
            # time to the same vertex.
            in_degree[edge.target_id] += 1
        for vertex in self.vertices:
            if vertex.id not in in_degree:
                in_degree[vertex.id] = 0
        return in_degree

    @staticmethod
    def build_adjacency_maps(edges: list[CycleEdge]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Returns the adjacency maps for the graph."""
        predecessor_map: dict[str, list[str]] = defaultdict(list)
        successor_map: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            predecessor_map[edge.target_id].append(edge.source_id)
            successor_map[edge.source_id].append(edge.target_id)
        return predecessor_map, successor_map

    def __to_dict(self) -> dict[str, dict[str, list[str]]]:
        """Converts the graph to a dictionary."""
        result: dict = {}
        for vertex in self.vertices:
            vertex_id = vertex.id
            sucessors = [i.id for i in self.get_all_successors(vertex)]
            predecessors = [i.id for i in self.get_predecessors(vertex)]
            result |= {vertex_id: {"successors": sucessors, "predecessors": predecessors}}
        return result
