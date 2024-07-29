import asyncio
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple, Type, Union

from loguru import logger

from langflow.exceptions.component import ComponentBuildException
from langflow.graph.edge.base import ContractEdge
from langflow.graph.graph.constants import lazy_load_vertex_dict
from langflow.graph.graph.runnable_vertices_manager import RunnableVerticesManager
from langflow.graph.graph.state_manager import GraphStateManager
from langflow.graph.graph.utils import find_start_component_id, process_flow, sort_up_to_vertex
from langflow.graph.schema import InterfaceComponentTypes, RunOutputs
from langflow.graph.vertex.base import Vertex, VertexStates
from langflow.graph.vertex.types import InterfaceVertex, StateVertex
from langflow.schema import Data
from langflow.schema.schema import INPUT_FIELD_NAME, InputType
from langflow.services.cache.utils import CacheMiss
from langflow.services.chat.service import ChatService
from langflow.services.deps import get_chat_service, get_tracing_service

if TYPE_CHECKING:
    from langflow.graph.schema import ResultData
    from langflow.services.tracing.service import TracingService


class Graph:
    """A class representing a graph of vertices and edges."""

    def __init__(
        self,
        flow_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Initializes a new instance of the Graph class.

        Args:
            nodes (List[Dict]): A list of dictionaries representing the vertices of the graph.
            edges (List[Dict[str, str]]): A list of dictionaries representing the edges of the graph.
            flow_id (Optional[str], optional): The ID of the flow. Defaults to None.
        """
        self._runs = 0
        self._updates = 0
        self.flow_id = flow_id
        self.flow_name = flow_name
        self.user_id = user_id
        self._is_input_vertices: List[str] = []
        self._is_output_vertices: List[str] = []
        self._is_state_vertices: List[str] = []
        self._has_session_id_vertices: List[str] = []
        self._sorted_vertices_layers: List[List[str]] = []
        self._run_id = ""
        self._start_time = datetime.now(timezone.utc)
        self.inactivated_vertices: set = set()
        self.activated_vertices: List[str] = []
        self.vertices_layers: List[List[str]] = []
        self.vertices_to_run: set[str] = set()
        self.stop_vertex: Optional[str] = None
        self.inactive_vertices: set = set()
        self.edges: List[ContractEdge] = []
        self.vertices: List[Vertex] = []
        self.run_manager = RunnableVerticesManager()
        self.state_manager = GraphStateManager()
        try:
            self.tracing_service: "TracingService" | None = get_tracing_service()
        except Exception as exc:
            logger.error(f"Error getting tracing service: {exc}")
            self.tracing_service = None

    def add_nodes_and_edges(self, nodes: List[Dict], edges: List[Dict[str, str]]):
        self._vertices = nodes
        self._edges = edges
        self.raw_graph_data = {"nodes": nodes, "edges": edges}
        self.top_level_vertices = []
        for vertex in self._vertices:
            if vertex_id := vertex.get("id"):
                self.top_level_vertices.append(vertex_id)
        self._graph_data = process_flow(self.raw_graph_data)

        self._vertices = self._graph_data["nodes"]
        self._edges = self._graph_data["edges"]
        self.initialize()

    # TODO: Create a TypedDict to represente the node
    def add_node(self, node: dict):
        self._vertices.append(node)

    # TODO: Create a TypedDict to represente the edge
    def add_edge(self, edge: dict):
        self._edges.append(edge)

    def initialize(self):
        self._build_graph()
        self.build_graph_maps(self.edges)
        self.define_vertices_lists()

    def get_state(self, name: str) -> Optional[Data]:
        """
        Returns the state of the graph with the given name.

        Args:
            name (str): The name of the state.

        Returns:
            Optional[Data]: The state record, or None if the state does not exist.
        """
        return self.state_manager.get_state(name, run_id=self._run_id)

    def update_state(self, name: str, record: Union[str, Data], caller: Optional[str] = None) -> None:
        """
        Updates the state of the graph with the given name.

        Args:
            name (str): The name of the state.
            record (Union[str, Data]): The new state record.
            caller (Optional[str], optional): The ID of the vertex that is updating the state. Defaults to None.
        """
        if caller:
            # If there is a caller which is a vertex_id, I want to activate
            # all StateVertex in self.vertices that are not the caller
            # essentially notifying all the other vertices that the state has changed
            # This also has to activate their successors
            self.activate_state_vertices(name, caller)

        self.state_manager.update_state(name, record, run_id=self._run_id)

    def activate_state_vertices(self, name: str, caller: str):
        """
        Activates the state vertices in the graph with the given name and caller.

        Args:
            name (str): The name of the state.
            caller (str): The ID of the vertex that is updating the state.
        """
        vertices_ids = set()
        new_predecessor_map = {}
        for vertex_id in self._is_state_vertices:
            caller_vertex = self.get_vertex(caller)
            vertex = self.get_vertex(vertex_id)
            if vertex_id == caller or vertex.display_name == caller_vertex.display_name:
                continue
            if (
                isinstance(vertex._raw_params["name"], str)
                and name in vertex._raw_params["name"]
                and vertex_id != caller
                and isinstance(vertex, StateVertex)
            ):
                vertices_ids.add(vertex_id)
                successors = self.get_all_successors(vertex, flat=True)
                # Update run_manager.run_predecessors because we are activating vertices
                # The run_prdecessors is the predecessor map of the vertices
                # we remove the vertex_id from the predecessor map whenever we run a vertex
                # So we need to get all edges of the vertex and successors
                # and run self.build_adjacency_maps(edges) to get the new predecessor map
                # that is not complete but we can use to update the run_predecessors
                edges_set = set()
                for _vertex in [vertex] + successors:
                    edges_set.update(_vertex.edges)
                    if _vertex.state == VertexStates.INACTIVE:
                        _vertex.set_state("ACTIVE")

                    vertices_ids.add(_vertex.id)
                edges = list(edges_set)
                predecessor_map, _ = self.build_adjacency_maps(edges)
                new_predecessor_map.update(predecessor_map)

        vertices_ids.update(new_predecessor_map.keys())
        vertices_ids.update(v_id for value_list in new_predecessor_map.values() for v_id in value_list)

        self.activated_vertices = list(vertices_ids)
        self.vertices_to_run.update(vertices_ids)
        self.run_manager.update_run_state(
            run_predecessors=new_predecessor_map,
            vertices_to_run=self.vertices_to_run,
        )

    def reset_activated_vertices(self):
        """
        Resets the activated vertices in the graph.
        """
        self.activated_vertices = []

    def append_state(self, name: str, record: Union[str, Data], caller: Optional[str] = None) -> None:
        """
        Appends the state of the graph with the given name.

        Args:
            name (str): The name of the state.
            record (Union[str, Data]): The state record to append.
            caller (Optional[str], optional): The ID of the vertex that is updating the state. Defaults to None.
        """
        if caller:
            self.activate_state_vertices(name, caller)

        self.state_manager.append_state(name, record, run_id=self._run_id)

    def validate_stream(self):
        """
        Validates the stream configuration of the graph.

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
                        raise ValueError(
                            f"Components {vertex.display_name} and {successor.display_name} "
                            "are connected and both have stream or streaming set to True"
                        )

    @property
    def run_id(self):
        """
        The ID of the current run.

        Returns:
            str: The run ID.

        Raises:
            ValueError: If the run ID is not set.
        """
        if not self._run_id:
            raise ValueError("Run ID not set")
        return self._run_id

    def set_run_id(self, run_id: uuid.UUID | None = None):
        """
        Sets the ID of the current run.

        Args:
            run_id (str): The run ID.
        """
        if run_id is None:
            run_id = uuid.uuid4()

        run_id_str = str(run_id)
        for vertex in self.vertices:
            self.state_manager.subscribe(run_id_str, vertex.update_graph_state)
        self._run_id = run_id_str
        if self.tracing_service:
            self.tracing_service.set_run_id(run_id)

    def set_run_name(self):
        # Given a flow name, flow_id
        if not self.tracing_service:
            return
        name = f"{self.flow_name} - {self.flow_id}"

        self.set_run_id()
        self.tracing_service.set_run_name(name)

    async def initialize_run(self):
        await self.tracing_service.initialize_tracers()

    async def end_all_traces(self, outputs: dict[str, Any] | None = None, error: Exception | None = None):
        if not self.tracing_service:
            return
        self._end_time = datetime.now(timezone.utc)
        if outputs is None:
            outputs = {}
        outputs |= self.metadata
        await self.tracing_service.end(outputs, error)

    @property
    def sorted_vertices_layers(self) -> List[List[str]]:
        """
        The sorted layers of vertices in the graph.

        Returns:
            List[List[str]]: The sorted layers of vertices.
        """
        if not self._sorted_vertices_layers:
            self.sort_vertices()
        return self._sorted_vertices_layers

    def define_vertices_lists(self):
        """
        Defines the lists of vertices that are inputs, outputs, and have session_id.
        """
        attributes = ["is_input", "is_output", "has_session_id", "is_state"]
        for vertex in self.vertices:
            for attribute in attributes:
                if getattr(vertex, attribute):
                    getattr(self, f"_{attribute}_vertices").append(vertex.id)

    async def _run(
        self,
        inputs: Dict[str, str],
        input_components: list[str],
        input_type: InputType | None,
        outputs: list[str],
        stream: bool,
        session_id: str,
        fallback_to_env_vars: bool,
    ) -> List[Optional["ResultData"]]:
        """
        Runs the graph with the given inputs.

        Args:
            inputs (Dict[str, str]): The input values for the graph.
            input_components (list[str]): The components to run for the inputs.
            outputs (list[str]): The outputs to retrieve from the graph.
            stream (bool): Whether to stream the results or not.
            session_id (str): The session ID for the graph.

        Returns:
            List[Optional["ResultData"]]: The outputs of the graph.
        """

        if input_components and not isinstance(input_components, list):
            raise ValueError(f"Invalid components value: {input_components}. Expected list")
        elif input_components is None:
            input_components = []

        if not isinstance(inputs.get(INPUT_FIELD_NAME, ""), str):
            raise ValueError(f"Invalid input value: {inputs.get(INPUT_FIELD_NAME)}. Expected string")
        if inputs:
            for vertex_id in self._is_input_vertices:
                vertex = self.get_vertex(vertex_id)
                # If the vertex is not in the input_components list
                if input_components and (
                    vertex_id not in input_components and vertex.display_name not in input_components
                ):
                    continue
                # If the input_type is not any and the input_type is not in the vertex id
                # Example: input_type = "chat" and vertex.id = "OpenAI-19ddn"
                elif input_type is not None and input_type != "any" and input_type not in vertex.id.lower():
                    continue
                if vertex is None:
                    raise ValueError(f"Vertex {vertex_id} not found")
                vertex.update_raw_params(inputs, overwrite=True)
        # Update all the vertices with the session_id
        for vertex_id in self._has_session_id_vertices:
            vertex = self.get_vertex(vertex_id)
            if vertex is None:
                raise ValueError(f"Vertex {vertex_id} not found")
            vertex.update_raw_params({"session_id": session_id})
        # Process the graph
        try:
            cache_service = get_chat_service()
            if self.flow_id:
                await cache_service.set_cache(self.flow_id, self)
        except Exception as exc:
            logger.exception(exc)

        try:
            # Prioritize the webhook component if it exists
            start_component_id = find_start_component_id(self._is_input_vertices)
            await self.process(start_component_id=start_component_id, fallback_to_env_vars=fallback_to_env_vars)
            self.increment_run_count()
        except Exception as exc:
            asyncio.create_task(self.end_all_traces(error=exc))
            raise ValueError(f"Error running graph: {exc}") from exc
        finally:
            asyncio.create_task(self.end_all_traces())
        # Get the outputs
        vertex_outputs = []
        for vertex in self.vertices:
            if not vertex._built:
                continue
            if vertex is None:
                raise ValueError(f"Vertex {vertex_id} not found")

            if not vertex.result and not stream and hasattr(vertex, "consume_async_generator"):
                await vertex.consume_async_generator()
            if (not outputs and vertex.is_output) or (vertex.display_name in outputs or vertex.id in outputs):
                vertex_outputs.append(vertex.result)

        return vertex_outputs

    def run(
        self,
        inputs: list[Dict[str, str]],
        input_components: Optional[list[list[str]]] = None,
        types: Optional[list[InputType | None]] = None,
        outputs: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        stream: bool = False,
        fallback_to_env_vars: bool = False,
    ) -> List[RunOutputs]:
        """
        Run the graph with the given inputs and return the outputs.

        Args:
            inputs (Dict[str, str]): A dictionary of input values.
            input_components (Optional[list[str]]): A list of input components.
            types (Optional[list[str]]): A list of types.
            outputs (Optional[list[str]]): A list of output components.
            session_id (Optional[str]): The session ID.
            stream (bool): Whether to stream the outputs.

        Returns:
            List[RunOutputs]: A list of RunOutputs objects representing the outputs.
        """
        # run the async function in a sync way
        # this could be used in a FastAPI endpoint
        # so we should take care of the event loop
        coro = self.arun(
            inputs=inputs,
            inputs_components=input_components,
            types=types,
            outputs=outputs,
            session_id=session_id,
            stream=stream,
            fallback_to_env_vars=fallback_to_env_vars,
        )

        try:
            # Attempt to get the running event loop; if none, an exception is raised
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                raise RuntimeError("The running event loop is closed.")
        except RuntimeError:
            # If there's no running event loop or it's closed, use asyncio.run
            return asyncio.run(coro)

        # If there's an existing, open event loop, use it to run the async function
        return loop.run_until_complete(coro)

    async def arun(
        self,
        inputs: list[Dict[str, str]],
        inputs_components: Optional[list[list[str]]] = None,
        types: Optional[list[InputType | None]] = None,
        outputs: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        stream: bool = False,
        fallback_to_env_vars: bool = False,
    ) -> List[RunOutputs]:
        """
        Runs the graph with the given inputs.

        Args:
            inputs (list[Dict[str, str]]): The input values for the graph.
            inputs_components (Optional[list[list[str]]], optional): Components to run for the inputs. Defaults to None.
            outputs (Optional[list[str]], optional): The outputs to retrieve from the graph. Defaults to None.
            session_id (Optional[str], optional): The session ID for the graph. Defaults to None.
            stream (bool, optional): Whether to stream the results or not. Defaults to False.

        Returns:
            List[RunOutputs]: The outputs of the graph.
        """
        # inputs is {"message": "Hello, world!"}
        # we need to go through self.inputs and update the self._raw_params
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
        for _ in range(len(inputs) - len(types)):
            types.append("chat")  # default to chat
        for run_inputs, components, input_type in zip(inputs, inputs_components, types):
            run_outputs = await self._run(
                inputs=run_inputs,
                input_components=components,
                input_type=input_type,
                outputs=outputs or [],
                stream=stream,
                session_id=session_id or "",
                fallback_to_env_vars=fallback_to_env_vars,
            )
            run_output_object = RunOutputs(inputs=run_inputs, outputs=run_outputs)
            logger.debug(f"Run outputs: {run_output_object}")
            vertex_outputs.append(run_output_object)
        return vertex_outputs

    def next_vertex_to_build(self):
        """
        Returns the next vertex to be built.

        Yields:
            str: The ID of the next vertex to be built.
        """
        yield from chain.from_iterable(self.vertices_layers)

    @property
    def metadata(self):
        """
        The metadata of the graph.

        Returns:
            dict: The metadata of the graph.
        """
        time_format = "%Y-%m-%d %H:%M:%S"
        return {
            "start_time": self._start_time.strftime(time_format),
            "end_time": self._end_time.strftime(time_format),
            "time_elapsed": f"{(self._end_time - self._start_time).total_seconds()} seconds",
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
        }

    def build_graph_maps(self, edges: Optional[List[ContractEdge]] = None, vertices: Optional[List[Vertex]] = None):
        """
        Builds the adjacency maps for the graph.
        """
        if edges is None:
            edges = self.edges

        if vertices is None:
            vertices = self.vertices

        self.predecessor_map, self.successor_map = self.build_adjacency_maps(edges)

        self.in_degree_map = self.build_in_degree(edges)
        self.parent_child_map = self.build_parent_child_map(vertices)

    def reset_inactivated_vertices(self):
        """
        Resets the inactivated vertices in the graph.
        """
        for vertex_id in self.inactivated_vertices.copy():
            self.mark_vertex(vertex_id, "ACTIVE")
        self.inactivated_vertices = []
        self.inactivated_vertices = set()

    def mark_all_vertices(self, state: str):
        """Marks all vertices in the graph."""
        for vertex in self.vertices:
            vertex.set_state(state)

    def mark_vertex(self, vertex_id: str, state: str):
        """Marks a vertex in the graph."""
        vertex = self.get_vertex(vertex_id)
        vertex.set_state(state)
        if state == VertexStates.INACTIVE:
            self.run_manager.remove_from_predecessors(vertex_id)

    def mark_branch(self, vertex_id: str, state: str, visited: Optional[set] = None, output_name: Optional[str] = None):
        """Marks a branch of the graph."""
        if visited is None:
            visited = set()
        if vertex_id in visited:
            return
        visited.add(vertex_id)

        self.mark_vertex(vertex_id, state)

        for child_id in self.parent_child_map[vertex_id]:
            # Only child_id that have an edge with the vertex_id through the output_name
            # should be marked
            if output_name:
                edge = self.get_edge(vertex_id, child_id)
                if edge and edge.source_handle.name != output_name:
                    continue
            self.mark_branch(child_id, state)

    def get_edge(self, source_id: str, target_id: str) -> Optional[ContractEdge]:
        """Returns the edge between two vertices."""
        for edge in self.edges:
            if edge.source_id == source_id and edge.target_id == target_id:
                return edge
        return None

    def build_parent_child_map(self, vertices: List[Vertex]):
        parent_child_map = defaultdict(list)
        for vertex in vertices:
            parent_child_map[vertex.id] = [child.id for child in self.get_successors(vertex)]
        return parent_child_map

    def increment_run_count(self):
        self._runs += 1

    def increment_update_count(self):
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
            "vertex_map": self.vertex_map,
        }

    def __setstate__(self, state):
        run_manager = state["run_manager"]
        if isinstance(run_manager, RunnableVerticesManager):
            state["run_manager"] = run_manager
        else:
            state["run_manager"] = RunnableVerticesManager.from_dict(run_manager)
        self.__dict__.update(state)
        self.state_manager = GraphStateManager()
        self.tracing_service = get_tracing_service()
        self.set_run_id(self._run_id)
        self.set_run_name()

    @classmethod
    def from_payload(
        cls,
        payload: Dict,
        flow_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> "Graph":
        """
        Creates a graph from a payload.

        Args:
            payload (Dict): The payload to create the graph from.˜`

        Returns:
            Graph: The created graph.
        """
        if "data" in payload:
            payload = payload["data"]
        try:
            vertices = payload["nodes"]
            edges = payload["edges"]
            graph = cls(flow_id, flow_name, user_id)
            graph.add_nodes_and_edges(vertices, edges)
            return graph
        except KeyError as exc:
            logger.exception(exc)
            if "nodes" not in payload and "edges" not in payload:
                logger.exception(exc)
                raise ValueError(
                    f"Invalid payload. Expected keys 'nodes' and 'edges'. Found {list(payload.keys())}"
                ) from exc

            raise ValueError(f"Error while creating graph from payload: {exc}") from exc

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Graph):
            return False
        return self.__repr__() == other.__repr__()

    # update this graph with another graph by comparing the __repr__ of each vertex
    # and if the __repr__ of a vertex is not the same as the other
    # then update the .data of the vertex to the self
    # both graphs have the same vertices and edges
    # but the data of the vertices might be different

    def update_edges_from_vertex(self, vertex: Vertex, other_vertex: Vertex) -> None:
        """Updates the edges of a vertex in the Graph."""
        new_edges = []
        for edge in self.edges:
            if edge.source_id == other_vertex.id or edge.target_id == other_vertex.id:
                continue
            new_edges.append(edge)
        new_edges += other_vertex.edges
        self.edges = new_edges

    def vertex_data_is_identical(self, vertex: Vertex, other_vertex: Vertex) -> bool:
        data_is_equivalent = vertex == other_vertex
        if not data_is_equivalent:
            return False
        return self.vertex_edges_are_identical(vertex, other_vertex)

    def vertex_edges_are_identical(self, vertex: Vertex, other_vertex: Vertex) -> bool:
        same_length = len(vertex.edges) == len(other_vertex.edges)
        if not same_length:
            return False
        for edge in vertex.edges:
            if edge not in other_vertex.edges:
                return False
        return True

    def update(self, other: "Graph") -> "Graph":
        # Existing vertices in self graph
        existing_vertex_ids = set(vertex.id for vertex in self.vertices)
        # Vertex IDs in the other graph
        other_vertex_ids = set(other.vertex_map.keys())

        # Find vertices that are in other but not in self (new vertices)
        new_vertex_ids = other_vertex_ids - existing_vertex_ids

        # Find vertices that are in self but not in other (removed vertices)
        removed_vertex_ids = existing_vertex_ids - other_vertex_ids

        # Remove vertices that are not in the other graph
        for vertex_id in removed_vertex_ids:
            try:
                self.remove_vertex(vertex_id)
            except ValueError:
                pass

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
        """
        Updates a vertex from another vertex.

        Args:
            vertex (Vertex): The vertex to be updated.
            other_vertex (Vertex): The vertex to update from.
        """
        vertex._data = other_vertex._data
        vertex._parse_data()
        # Now we update the edges of the vertex
        self.update_edges_from_vertex(vertex, other_vertex)
        vertex.params = {}
        vertex._build_params()
        vertex.graph = self
        # If the vertex is frozen, we don't want
        # to reset the results nor the _built attribute
        if not vertex.frozen:
            vertex._built = False
            vertex.result = None
            vertex.artifacts = {}
            vertex.set_top_level(self.top_level_vertices)
        self.reset_all_edges_of_vertex(vertex)

    def reset_all_edges_of_vertex(self, vertex: Vertex) -> None:
        """Resets all the edges of a vertex."""
        for edge in vertex.edges:
            for vid in [edge.source_id, edge.target_id]:
                if vid in self.vertex_map:
                    _vertex = self.vertex_map[vid]
                    if not _vertex.frozen:
                        _vertex._build_params()

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

        # Now that we have the vertices and edges
        # We need to map the vertices that are connected to
        # to ChatVertex instances

    def remove_vertex(self, vertex_id: str) -> None:
        """Removes a vertex from the graph."""
        vertex = self.get_vertex(vertex_id)
        if vertex is None:
            return
        self.vertices.remove(vertex)
        self.vertex_map.pop(vertex_id)
        self.edges = [edge for edge in self.edges if edge.source_id != vertex_id and edge.target_id != vertex_id]

    def _build_vertex_params(self) -> None:
        """Identifies and handles the LLM vertex within the graph."""
        for vertex in self.vertices:
            vertex._build_params()

    def _validate_vertex(self, vertex: Vertex) -> bool:
        """Validates a vertex."""
        # All vertices that do not have edges are invalid
        return len(self.get_vertex_edges(vertex.id)) > 0

    def get_vertex(self, vertex_id: str, silent: bool = False) -> Vertex:
        """Returns a vertex by id."""
        try:
            return self.vertex_map[vertex_id]
        except KeyError:
            raise ValueError(f"Vertex {vertex_id} not found")

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
        raise ValueError(f"Vertex {vertex_id} is not a top level vertex or no root vertex found")

    async def build_vertex(
        self,
        chat_service: ChatService,
        vertex_id: str,
        inputs_dict: Optional[Dict[str, str]] = None,
        files: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        fallback_to_env_vars: bool = False,
    ):
        """
        Builds a vertex in the graph.

        Args:
            lock (asyncio.Lock): A lock to synchronize access to the graph.
            set_cache_coro (Coroutine): A coroutine to set the cache.
            vertex_id (str): The ID of the vertex to build.
            inputs (Optional[Dict[str, str]]): Optional dictionary of inputs for the vertex. Defaults to None.
            user_id (Optional[str]): Optional user ID. Defaults to None.

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
            if vertex.frozen:
                # Check the cache for the vertex
                cached_result = await chat_service.get_cache(key=vertex.id)
                if isinstance(cached_result, CacheMiss):
                    await vertex.build(
                        user_id=user_id, inputs=inputs_dict, fallback_to_env_vars=fallback_to_env_vars, files=files
                    )
                    await chat_service.set_cache(key=vertex.id, data=vertex)
                else:
                    cached_vertex = cached_result["result"]
                    # Now set update the vertex with the cached vertex
                    vertex._built = cached_vertex._built
                    vertex.result = cached_vertex.result
                    vertex.results = cached_vertex.results
                    vertex.artifacts = cached_vertex.artifacts
                    vertex._built_object = cached_vertex._built_object
                    vertex._custom_component = cached_vertex._custom_component
                    if vertex.result is not None:
                        vertex.result.used_frozen_result = True

            else:
                await vertex.build(
                    user_id=user_id, inputs=inputs_dict, fallback_to_env_vars=fallback_to_env_vars, files=files
                )
                await chat_service.set_cache(key=vertex.id, data=vertex)

            if vertex.result is not None:
                params = f"{vertex._built_object_repr()}{params}"
                valid = True
                result_dict = vertex.result
                artifacts = vertex.artifacts
            else:
                raise ValueError(f"No result found for vertex {vertex_id}")
            return result_dict, params, valid, artifacts, vertex
        except Exception as exc:
            if not isinstance(exc, ComponentBuildException):
                logger.exception(f"Error building Component: \n\n{exc}")
            raise exc

    def get_vertex_edges(
        self,
        vertex_id: str,
        is_target: Optional[bool] = None,
        is_source: Optional[bool] = None,
    ) -> List[ContractEdge]:
        """Returns a list of edges for a given vertex."""
        # The idea here is to return the edges that have the vertex_id as source or target
        # or both
        return [
            edge
            for edge in self.edges
            if (edge.source_id == vertex_id and is_source is not False)
            or (edge.target_id == vertex_id and is_target is not False)
        ]

    def get_vertices_with_target(self, vertex_id: str) -> List[Vertex]:
        """Returns the vertices connected to a vertex."""
        vertices: List[Vertex] = []
        for edge in self.edges:
            if edge.target_id == vertex_id:
                vertex = self.get_vertex(edge.source_id)
                if vertex is None:
                    continue
                vertices.append(vertex)
        return vertices

    async def process(self, fallback_to_env_vars: bool, start_component_id: Optional[str] = None) -> "Graph":
        """Processes the graph with vertices in each layer run in parallel."""

        first_layer = self.sort_vertices(start_component_id=start_component_id)
        vertex_task_run_count: Dict[str, int] = {}
        to_process = deque(first_layer)
        layer_index = 0
        chat_service = get_chat_service()
        run_id = uuid.uuid4()
        self.set_run_id(run_id)
        self.set_run_name()
        await self.initialize_run()
        lock = chat_service._async_cache_locks[self.run_id]
        while to_process:
            current_batch = list(to_process)  # Copy current deque items to a list
            to_process.clear()  # Clear the deque for new items
            tasks = []
            for vertex_id in current_batch:
                vertex = self.get_vertex(vertex_id)
                task = asyncio.create_task(
                    self.build_vertex(
                        chat_service=chat_service,
                        vertex_id=vertex_id,
                        user_id=self.user_id,
                        inputs_dict={},
                        fallback_to_env_vars=fallback_to_env_vars,
                    ),
                    name=f"{vertex.display_name} Run {vertex_task_run_count.get(vertex_id, 0)}",
                )
                tasks.append(task)
                vertex_task_run_count[vertex_id] = vertex_task_run_count.get(vertex_id, 0) + 1

            logger.debug(f"Running layer {layer_index} with {len(tasks)} tasks")
            try:
                next_runnable_vertices = await self._execute_tasks(tasks, lock=lock)
            except Exception as e:
                logger.error(f"Error executing tasks in layer {layer_index}: {e}")
                raise e
            if not next_runnable_vertices:
                break
            to_process.extend(next_runnable_vertices)
            layer_index += 1

        logger.debug("Graph processing complete")
        return self

    def find_next_runnable_vertices(self, vertex_id: str, vertex_successors_ids: List[str]) -> List[str]:
        next_runnable_vertices = []
        for v_id in vertex_successors_ids:
            if not self.is_vertex_runnable(v_id):
                next_runnable_vertices.extend(self.find_runnable_predecessors_for_successor(v_id))
            else:
                next_runnable_vertices.append(v_id)

        return next_runnable_vertices

    async def get_next_runnable_vertices(self, lock: asyncio.Lock, vertex: "Vertex", cache: bool = True) -> List[str]:
        v_id = vertex.id
        v_successors_ids = vertex.successors_ids
        async with lock:
            self.run_manager.remove_vertex_from_runnables(v_id)
            next_runnable_vertices = self.find_next_runnable_vertices(v_id, v_successors_ids)

            for next_v_id in set(next_runnable_vertices):  # Use set to avoid duplicates
                if next_v_id == v_id:
                    next_runnable_vertices.remove(v_id)
                else:
                    self.run_manager.add_to_vertices_being_run(next_v_id)
            if cache and self.flow_id:
                set_cache_coro = partial(get_chat_service().set_cache, key=self.flow_id)
                await set_cache_coro(self, lock)
        return next_runnable_vertices

    async def _execute_tasks(self, tasks: List[asyncio.Task], lock: asyncio.Lock) -> List[str]:
        """Executes tasks in parallel, handling exceptions for each task."""
        results = []
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        vertices: List[Vertex] = []

        for i, result in enumerate(completed_tasks):
            task_name = tasks[i].get_name()
            if isinstance(result, Exception):
                logger.error(f"Task {task_name} failed with exception: {result}")
                # Cancel all remaining tasks
                for t in tasks[i + 1 :]:
                    t.cancel()
                raise result
            elif isinstance(result, tuple) and len(result) == 5:
                vertices.append(result[4])
            else:
                raise ValueError(f"Invalid result from task {task_name}: {result}")

        for v in vertices:
            # set all executed vertices as non-runnable to not run them again.
            # they could be calculated as predecessor or successors of parallel vertices
            # This could usually happen with input vertices like ChatInput
            self.run_manager.remove_vertex_from_runnables(v.id)

        for v in vertices:
            next_runnable_vertices = await self.get_next_runnable_vertices(lock, vertex=v, cache=False)
            results.extend(next_runnable_vertices)
        return results

    def topological_sort(self) -> List[Vertex]:
        """
        Performs a topological sort of the vertices in the graph.

        Returns:
            List[Vertex]: A list of vertices in topological order.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        # States: 0 = unvisited, 1 = visiting, 2 = visited
        state = {vertex: 0 for vertex in self.vertices}
        sorted_vertices = []

        def dfs(vertex):
            if state[vertex] == 1:
                # We have a cycle
                raise ValueError("Graph contains a cycle, cannot perform topological sort")
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

    def get_all_successors(self, vertex: Vertex, recursive=True, flat=True):
        # Recursively get the successors of the current vertex
        # successors = vertex.successors
        # if not successors:
        #     return []
        # successors_result = []
        # for successor in successors:
        #     # Just return a list of successors
        #     if recursive:
        #         next_successors = self.get_all_successors(successor)
        #         successors_result.extend(next_successors)
        #     successors_result.append(successor)
        # return successors_result
        # The above is the version without the flat parameter
        # The below is the version with the flat parameter
        # the flat parameter will define if each layer of successors
        # becomes one list or if the result is a list of lists
        # if flat is True, the result will be a list of vertices
        # if flat is False, the result will be a list of lists of vertices
        # each list will represent a layer of successors
        successors = vertex.successors
        if not successors:
            return []
        successors_result = []
        for successor in successors:
            if recursive:
                next_successors = self.get_all_successors(successor)
                if flat:
                    successors_result.extend(next_successors)
                else:
                    successors_result.append(next_successors)
            if flat:
                successors_result.append(successor)
            else:
                successors_result.append([successor])
        return successors_result

    def get_successors(self, vertex: Vertex) -> List[Vertex]:
        """Returns the successors of a vertex."""
        return [self.get_vertex(target_id) for target_id in self.successor_map.get(vertex.id, [])]

    def get_vertex_neighbors(self, vertex: Vertex) -> Dict[Vertex, int]:
        """Returns the neighbors of a vertex."""
        neighbors: Dict[Vertex, int] = {}
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

    def _build_edges(self) -> List[ContractEdge]:
        """Builds the edges of the graph."""
        # Edge takes two vertices as arguments, so we need to build the vertices first
        # and then build the edges
        # if we can't find a vertex, we raise an error

        edges: set[ContractEdge] = set()
        for edge in self._edges:
            source = self.get_vertex(edge["source"])
            target = self.get_vertex(edge["target"])

            if source is None:
                raise ValueError(f"Source vertex {edge['source']} not found")
            if target is None:
                raise ValueError(f"Target vertex {edge['target']} not found")
            new_edge = ContractEdge(source, target, edge)

            edges.add(new_edge)

        return list(edges)

    def _get_vertex_class(self, node_type: str, node_base_type: str, node_id: str) -> Type[Vertex]:
        """Returns the node class based on the node type."""
        # First we check for the node_base_type
        node_name = node_id.split("-")[0]
        if node_name in InterfaceComponentTypes:
            return InterfaceVertex
        elif node_name in ["SharedState", "Notify", "Listen"]:
            return StateVertex
        elif node_base_type in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_base_type]
        elif node_name in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_name]

        if node_type in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_type]
        return (
            lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_base_type]
            if node_base_type in lazy_load_vertex_dict.VERTEX_TYPE_MAP
            else Vertex
        )

    def _build_vertices(self) -> List[Vertex]:
        """Builds the vertices of the graph."""
        vertices: List[Vertex] = []
        for vertex in self._vertices:
            vertex_instance = self._create_vertex(vertex)
            vertices.append(vertex_instance)

        return vertices

    def _create_vertex(self, vertex: dict):
        vertex_data = vertex["data"]
        vertex_type: str = vertex_data["type"]  # type: ignore
        vertex_base_type: str = vertex_data["node"]["template"]["_type"]  # type: ignore
        if "id" not in vertex_data:
            raise ValueError(f"Vertex data for {vertex_data['display_name']} does not contain an id")

        VertexClass = self._get_vertex_class(vertex_type, vertex_base_type, vertex_data["id"])

        vertex_instance = VertexClass(vertex, graph=self)
        vertex_instance.set_top_level(self.top_level_vertices)
        return vertex_instance

    def get_children_by_vertex_type(self, vertex: Vertex, vertex_type: str) -> List[Vertex]:
        """Returns the children of a vertex based on the vertex type."""
        children = []
        vertex_types = [vertex.data["type"]]
        if "node" in vertex.data:
            vertex_types += vertex.data["node"]["base_classes"]
        if vertex_type in vertex_types:
            children.append(vertex)
        return children

    def __repr__(self):
        vertex_ids = [vertex.id for vertex in self.vertices]
        edges_repr = "\n".join([f"{edge.source_id} --> {edge.target_id}" for edge in self.edges])
        return f"Graph: \nNodes: {vertex_ids}\nConnections: \n{edges_repr}"

    def layered_topological_sort(
        self,
        vertices: List[Vertex],
        filter_graphs: bool = False,
    ) -> List[List[str]]:
        """Performs a layered topological sort of the vertices in the graph."""
        vertices_ids = {vertex.id for vertex in vertices}
        # Queue for vertices with no incoming edges
        queue = deque(
            vertex.id
            for vertex in vertices
            # if filter_graphs then only vertex.is_input will be considered
            if self.in_degree_map[vertex.id] == 0 and (not filter_graphs or vertex.is_input)
        )
        layers: List[List[str]] = []
        visited = set(queue)

        current_layer = 0
        while queue:
            layers.append([])  # Start a new layer
            layer_size = len(queue)
            for _ in range(layer_size):
                vertex_id = queue.popleft()
                visited.add(vertex_id)

                layers[current_layer].append(vertex_id)
                for neighbor in self.successor_map[vertex_id]:
                    # only vertices in `vertices_ids` should be considered
                    # because vertices by have been filtered out
                    # in a previous step. All dependencies of theirs
                    # will be built automatically if required
                    if neighbor not in vertices_ids:
                        continue

                    self.in_degree_map[neighbor] -= 1  # 'remove' edge
                    if self.in_degree_map[neighbor] == 0 and neighbor not in visited:
                        queue.append(neighbor)

                    # if > 0 it might mean not all predecessors have added to the queue
                    # so we should process the neighbors predecessors
                    elif self.in_degree_map[neighbor] > 0:
                        for predecessor in self.predecessor_map[neighbor]:
                            if predecessor not in queue and predecessor not in visited:
                                queue.append(predecessor)

            current_layer += 1  # Next layer
        new_layers = self.refine_layers(layers)
        return new_layers

    def refine_layers(self, initial_layers):
        # Map each vertex to its current layer
        vertex_to_layer = {}
        for layer_index, layer in enumerate(initial_layers):
            for vertex in layer:
                vertex_to_layer[vertex] = layer_index

        # Build the adjacency list for reverse lookup (dependencies)

        refined_layers = [[] for _ in initial_layers]  # Start with empty layers
        new_layer_index_map = defaultdict(int)

        # Map each vertex to its new layer index
        # by finding the lowest layer index of its dependencies
        # and subtracting 1
        # If a vertex has no dependencies, it will be placed in the first layer
        # If a vertex has dependencies, it will be placed in the lowest layer index of its dependencies
        # minus 1
        for vertex_id, deps in self.successor_map.items():
            indexes = [vertex_to_layer[dep] for dep in deps if dep in vertex_to_layer]
            new_layer_index = max(min(indexes, default=0) - 1, 0)
            new_layer_index_map[vertex_id] = new_layer_index

        for layer_index, layer in enumerate(initial_layers):
            for vertex_id in layer:
                # Place the vertex in the highest possible layer where its dependencies are met
                new_layer_index = new_layer_index_map[vertex_id]
                if new_layer_index > layer_index:
                    refined_layers[new_layer_index].append(vertex_id)
                    vertex_to_layer[vertex_id] = new_layer_index
                else:
                    refined_layers[layer_index].append(vertex_id)

        # Remove empty layers if any
        refined_layers = [layer for layer in refined_layers if layer]

        return refined_layers

    def sort_chat_inputs_first(self, vertices_layers: List[List[str]]) -> List[List[str]]:
        chat_inputs_first = []
        for layer in vertices_layers:
            for vertex_id in layer:
                if "ChatInput" in vertex_id:
                    # Remove the ChatInput from the layer
                    layer.remove(vertex_id)
                    chat_inputs_first.append(vertex_id)
        if not chat_inputs_first:
            return vertices_layers

        vertices_layers = [chat_inputs_first] + vertices_layers

        return vertices_layers

    def sort_layer_by_dependency(self, vertices_layers: List[List[str]]) -> List[List[str]]:
        """Sorts the vertices in each layer by dependency, ensuring no vertex depends on a subsequent vertex."""
        sorted_layers = []

        for layer in vertices_layers:
            sorted_layer = self._sort_single_layer_by_dependency(layer)
            sorted_layers.append(sorted_layer)

        return sorted_layers

    def _sort_single_layer_by_dependency(self, layer: List[str]) -> List[str]:
        """Sorts a single layer by dependency using a stable sorting method."""
        # Build a map of each vertex to its index in the layer for quick lookup.
        index_map = {vertex: index for index, vertex in enumerate(layer)}
        # Create a sorted copy of the layer based on dependency order.
        sorted_layer = sorted(layer, key=lambda vertex: self._max_dependency_index(vertex, index_map), reverse=True)

        return sorted_layer

    def _max_dependency_index(self, vertex_id: str, index_map: Dict[str, int]) -> int:
        """Finds the highest index a given vertex's dependencies occupy in the same layer."""
        vertex = self.get_vertex(vertex_id)
        max_index = -1
        for successor in vertex.successors:  # Assuming vertex.successors is a list of successor vertex identifiers.
            if successor.id in index_map:
                max_index = max(max_index, index_map[successor.id])
        return max_index

    def __to_dict(self) -> Dict[str, Dict[str, List[str]]]:
        """Converts the graph to a dictionary."""
        result: Dict = dict()
        for vertex in self.vertices:
            vertex_id = vertex.id
            sucessors = [i.id for i in self.get_all_successors(vertex)]
            predecessors = [i.id for i in self.get_predecessors(vertex)]
            result |= {vertex_id: {"successors": sucessors, "predecessors": predecessors}}
        return result

    def __filter_vertices(self, vertex_id: str, is_start: bool = False):
        dictionaryized_graph = self.__to_dict()
        vertex_ids = sort_up_to_vertex(dictionaryized_graph, vertex_id, is_start)
        return [self.get_vertex(vertex_id) for vertex_id in vertex_ids]

    def sort_vertices(
        self,
        stop_component_id: Optional[str] = None,
        start_component_id: Optional[str] = None,
    ) -> List[str]:
        """Sorts the vertices in the graph."""
        self.mark_all_vertices("ACTIVE")
        if stop_component_id is not None:
            self.stop_vertex = stop_component_id
            vertices = self.__filter_vertices(stop_component_id)

        elif start_component_id:
            vertices = self.__filter_vertices(start_component_id, is_start=True)

        else:
            vertices = self.vertices
            # without component_id we are probably running in the chat
            # so we want to pick only graphs that start with ChatInput or
            # TextInput

        vertices_layers = self.layered_topological_sort(vertices)
        vertices_layers = self.sort_by_avg_build_time(vertices_layers)
        # vertices_layers = self.sort_chat_inputs_first(vertices_layers)
        # Now we should sort each layer in a way that we make sure
        # vertex V does not depend on vertex V+1
        vertices_layers = self.sort_layer_by_dependency(vertices_layers)
        self.increment_run_count()
        self._sorted_vertices_layers = vertices_layers
        first_layer = vertices_layers[0]
        # save the only the rest
        self.vertices_layers = vertices_layers[1:]
        self.vertices_to_run = {vertex_id for vertex_id in chain.from_iterable(vertices_layers)}
        self.build_run_map()
        # Return just the first layer
        return first_layer

    def sort_interface_components_first(self, vertices_layers: List[List[str]]) -> List[List[str]]:
        """Sorts the vertices in the graph so that vertices containing ChatInput or ChatOutput come first."""

        def contains_interface_component(vertex):
            return any(component.value in vertex for component in InterfaceComponentTypes)

        # Sort each inner list so that vertices containing ChatInput or ChatOutput come first
        sorted_vertices = [
            sorted(
                inner_list,
                key=lambda vertex: not contains_interface_component(vertex),
            )
            for inner_list in vertices_layers
        ]
        return sorted_vertices

    def sort_by_avg_build_time(self, vertices_layers: List[List[str]]) -> List[List[str]]:
        """Sorts the vertices in the graph so that vertices with the lowest average build time come first."""

        def sort_layer_by_avg_build_time(vertices_ids: List[str]) -> List[str]:
            """Sorts the vertices in the graph so that vertices with the lowest average build time come first."""
            if len(vertices_ids) == 1:
                return vertices_ids
            vertices_ids.sort(key=lambda vertex_id: self.get_vertex(vertex_id).avg_build_time)

            return vertices_ids

        sorted_vertices = [sort_layer_by_avg_build_time(layer) for layer in vertices_layers]
        return sorted_vertices

    def is_vertex_runnable(self, vertex_id: str) -> bool:
        """Returns whether a vertex is runnable."""
        is_active = self.get_vertex(vertex_id).is_active()
        return self.run_manager.is_vertex_runnable(vertex_id, is_active)

    def build_run_map(self):
        """
        Builds the run map for the graph.

        This method is responsible for building the run map for the graph,
        which maps each node in the graph to its corresponding run function.

        Returns:
            None
        """
        self.run_manager.build_run_map(predecessor_map=self.predecessor_map, vertices_to_run=self.vertices_to_run)

    def find_runnable_predecessors_for_successors(self, vertex_id: str) -> List[str]:
        """
        For each successor of the current vertex, find runnable predecessors if any.
        This checks the direct predecessors of each successor to identify any that are
        immediately runnable, expanding the search to ensure progress can be made.
        """
        runnable_vertices = []
        for successor_id in self.run_manager.run_map.get(vertex_id, []):
            runnable_vertices.extend(self.find_runnable_predecessors_for_successor(successor_id))

        return runnable_vertices

    def find_runnable_predecessors_for_successor(self, vertex_id: str) -> List[str]:
        runnable_vertices = []
        visited = set()

        def find_runnable_predecessors(predecessor: "Vertex"):
            predecessor_id = predecessor.id
            if predecessor_id in visited:
                return
            visited.add(predecessor_id)
            is_active = self.get_vertex(predecessor_id).is_active()
            if self.run_manager.is_vertex_runnable(predecessor_id, is_active):
                runnable_vertices.append(predecessor_id)
            else:
                for pred_pred_id in self.run_manager.run_predecessors.get(predecessor_id, []):
                    find_runnable_predecessors(self.get_vertex(pred_pred_id))

        for predecessor_id in self.run_manager.run_predecessors.get(vertex_id, []):
            find_runnable_predecessors(self.get_vertex(predecessor_id))
        return runnable_vertices

    def remove_from_predecessors(self, vertex_id: str):
        self.run_manager.remove_from_predecessors(vertex_id)

    def remove_vertex_from_runnables(self, vertex_id: str):
        self.run_manager.remove_vertex_from_runnables(vertex_id)

    def get_top_level_vertices(self, vertices_ids):
        """
        Retrieves the top-level vertices from the given graph based on the provided vertex IDs.

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

    def build_in_degree(self, edges: List[ContractEdge]) -> Dict[str, int]:
        in_degree: Dict[str, int] = defaultdict(int)
        for edge in edges:
            in_degree[edge.target_id] += 1
        return in_degree

    def build_adjacency_maps(self, edges: List[ContractEdge]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """Returns the adjacency maps for the graph."""
        predecessor_map: dict[str, list[str]] = defaultdict(list)
        successor_map: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            predecessor_map[edge.target_id].append(edge.source_id)
            successor_map[edge.source_id].append(edge.target_id)
        return predecessor_map, successor_map
