import asyncio
from collections import defaultdict, deque
from itertools import chain
from typing import TYPE_CHECKING, Dict, Generator, List, Optional, Type, Union

from loguru import logger

from langflow_base.graph.edge.base import Edge
from langflow_base.graph.graph.constants import lazy_load_vertex_dict
from langflow_base.graph.graph.utils import process_flow
from langflow_base.graph.vertex.base import Vertex
from langflow_base.graph.vertex.types import FileToolVertex, LLMVertex, ToolkitVertex
from langflow_base.interface.tools.constants import FILE_TOOLS
from langflow_base.utils import payload


class Graph:
    """A class representing a graph of vertices and edges."""

    def __init__(
        self,
        nodes: List[Dict],
        edges: List[Dict[str, str]],
        flow_id: Optional[str] = None,
    ) -> None:
        self._vertices = nodes
        self._edges = edges
        self.raw_graph_data = {"nodes": nodes, "edges": edges}
        self._runs = 0
        self._updates = 0
        self.flow_id = flow_id
        self._is_input_vertices: List[str] = []
        self._is_output_vertices: List[str] = []
        self._is_state_vertices: List[str] = []
        self._has_session_id_vertices: List[str] = []
        self._sorted_vertices_layers: List[List[str]] = []
        self._run_id = ""

        self.top_level_vertices = []
        for vertex in self._vertices:
            if vertex_id := vertex.get("id"):
                self.top_level_vertices.append(vertex_id)
        self._graph_data = process_flow(self.raw_graph_data)

        self._vertices = self._graph_data["nodes"]
        self._edges = self._graph_data["edges"]
        self.inactivated_vertices: set = set()
        self.activated_vertices: List[str] = []
        self.vertices_layers: List[List[str]] = []
        self.vertices_to_run: set[str] = set()
        self.stop_vertex: Optional[str] = None

        self.inactive_vertices: set = set()
        self.edges: List[ContractEdge] = []
        self.vertices: List[Vertex] = []
        self._build_graph()
        self.build_graph_maps()
        self.define_vertices_lists()
        self.state_manager = GraphStateManager()

    def get_state(self, name: str) -> Optional[Record]:
        """Returns the state of the graph."""
        return self.state_manager.get_state(name, run_id=self._run_id)

    def update_state(self, name: str, record: Union[str, Record], caller: Optional[str] = None) -> None:
        """Updates the state of the graph."""
        if caller:
            # If there is a caller which is a vertex_id, I want to activate
            # all StateVertex in self.vertices that are not the caller
            # essentially notifying all the other vertices that the state has changed
            # This also has to activate their successors
            self.activate_state_vertices(name, caller)

        self.state_manager.update_state(name, record, run_id=self._run_id)

    def activate_state_vertices(self, name: str, caller: str):
        vertices_ids = []
        for vertex_id in self._is_state_vertices:
            if vertex_id == caller:
                continue
            vertex = self.get_vertex(vertex_id)
            if (
                isinstance(vertex._raw_params["name"], str)
                and name in vertex._raw_params["name"]
                and vertex_id != caller
                and isinstance(vertex, StateVertex)
            ):
                vertices_ids.append(vertex_id)
                successors = self.get_all_successors(vertex, flat=True)
                self.vertices_to_run.update(list(map(lambda x: x.id, successors)))
        self.activated_vertices = vertices_ids
        self.vertices_to_run.update(vertices_ids)

    def reset_activated_vertices(self):
        self.activated_vertices = []

    def append_state(self, name: str, record: Union[str, Record], caller: Optional[str] = None) -> None:
        """Appends the state of the graph."""
        if caller:
            self.activate_state_vertices(name, caller)

        self.state_manager.append_state(name, record, run_id=self._run_id)

    @property
    def run_id(self):
        if not self._run_id:
            raise ValueError("Run ID not set")
        return self._run_id

    def set_run_id(self, run_id: str):
        for vertex in self.vertices:
            self.state_manager.subscribe(run_id, vertex.update_graph_state)
        self._run_id = run_id

    @property
    def sorted_vertices_layers(self) -> List[List[str]]:
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
        outputs: list[str],
        stream: bool,
        session_id: str,
    ) -> List[Optional["ResultData"]]:
        """Runs the graph with the given inputs."""
        for vertex_id in self._is_input_vertices:
            vertex = self.get_vertex(vertex_id)
            if input_components and (vertex_id not in input_components or vertex.display_name not in input_components):
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
            await self.process()
            self.increment_run_count()
        except Exception as exc:
            logger.exception(exc)
            raise ValueError(f"Error running graph: {exc}") from exc
        # Get the outputs
        vertex_outputs = []
        for vertex in self.vertices:
            if vertex is None:
                raise ValueError(f"Vertex {vertex_id} not found")

            if not vertex.result and not stream and hasattr(vertex, "consume_async_generator"):
                await vertex.consume_async_generator()
            if not outputs or (vertex.display_name in outputs or vertex.id in outputs):
                vertex_outputs.append(vertex.result)

        return vertex_outputs

    async def run(
        self,
        inputs: list[Dict[str, str]],
        inputs_components: Optional[list[list[str]]] = None,
        outputs: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        stream: bool = False,
    ) -> List[RunOutputs]:
        """Runs the graph with the given inputs."""
        # inputs is {"message": "Hello, world!"}
        # we need to go through self.inputs and update the self._raw_params
        # of the vertices that are inputs
        # if the value is a list, we need to run multiple times
        vertex_outputs = []
        if not isinstance(inputs, list):
            inputs = [inputs]
        for run_inputs, components in zip(inputs, inputs_components or []):
            if components and not isinstance(components, list):
                raise ValueError(f"Invalid components value: {components}. Expected list")
            elif components is None:
                components = []

            if not isinstance(run_inputs.get(INPUT_FIELD_NAME, ""), str):
                raise ValueError(f"Invalid input value: {run_inputs.get(INPUT_FIELD_NAME)}. Expected string")
            run_outputs = await self._run(
                inputs=run_inputs,
                input_components=components,
                outputs=outputs or [],
                stream=stream,
                session_id=session_id or "",
            )
            run_output_object = RunOutputs(inputs=run_inputs, outputs=run_outputs)
            logger.debug(f"Run outputs: {run_output_object}")
            vertex_outputs.append(run_output_object)
        return vertex_outputs

    # vertices_layers is a list of lists ordered by the order the vertices
    # should be built.
    # We need to create a new method that will take the vertices_layers
    # and return the next vertex to be built.
    def next_vertex_to_build(self):
        """Returns the next vertex to be built."""
        yield from chain.from_iterable(self.vertices_layers)

    @property
    def metadata(self):
        return {
            "runs": self._runs,
            "updates": self._updates,
            "inactivated_vertices": self.inactivated_vertices,
        }

    def build_graph_maps(self):
        self.predecessor_map, self.successor_map = self.build_adjacency_maps()

        self.in_degree_map = self.build_in_degree()
        self.parent_child_map = self.build_parent_child_map()

    def reset_inactivated_vertices(self):
        self.inactivated_vertices = set()

    def mark_all_vertices(self, state: str):
        """Marks all vertices in the graph."""
        for vertex in self.vertices:
            vertex.set_state(state)

    def mark_vertex(self, vertex_id: str, state: str):
        """Marks a vertex in the graph."""
        vertex = self.get_vertex(vertex_id)
        vertex.set_state(state)

    def mark_branch(self, vertex_id: str, state: str):
        """Marks a branch of the graph."""
        self.mark_vertex(vertex_id, state)
        for child_id in self.parent_child_map[vertex_id]:
            self.mark_branch(child_id, state)

    def build_parent_child_map(self):
        parent_child_map = defaultdict(list)
        for vertex in self.vertices:
            parent_child_map[vertex.id] = [child.id for child in self.get_successors(vertex)]
        return parent_child_map

    def increment_run_count(self):
        self._runs += 1

    def increment_update_count(self):
        self._updates += 1

    def __getstate__(self):
        return self.raw_graph_data

    def __setstate__(self, state):
        self.__init__(**state)

    def build_in_degree(self):
        in_degree = defaultdict(int)
        for edge in self.edges:
            in_degree[edge.target_id] += 1
        return in_degree

    def build_adjacency_maps(self):
        """Returns the adjacency maps for the graph."""
        predecessor_map = defaultdict(list)
        successor_map = defaultdict(list)
        for edge in self.edges:
            predecessor_map[edge.target_id].append(edge.source_id)
            successor_map[edge.source_id].append(edge.target_id)
        return predecessor_map, successor_map

    def build_run_map(self):
        run_map = defaultdict(list)
        # The run map gets the predecessor_map and maps the info like this:
        # {vertex_id: every id that contains the vertex_id in the predecessor_map}
        for vertex_id, predecessors in self.predecessor_map.items():
            for predecessor in predecessors:
                run_map[predecessor].append(vertex_id)
        return run_map

    @classmethod
    def from_payload(cls, payload: Dict, flow_id: Optional[str] = None) -> "Graph":
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
            return cls(vertices, edges, flow_id)
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
        # remove invalid vertices
        self._validate_vertices()
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
        llm_vertex = None
        for vertex in self.vertices:
            vertex._build_params()
            if isinstance(vertex, LLMVertex):
                llm_vertex = vertex

        if llm_vertex:
            for vertex in self.vertices:
                if isinstance(vertex, ToolkitVertex):
                    vertex.params["llm"] = llm_vertex

    def _validate_vertices(self) -> None:
        """Check that all vertices have edges"""
        if len(self.vertices) == 1:
            return
        for vertex in self.vertices:
            if not self._validate_vertex(vertex):
                raise ValueError(f"{vertex.display_name} is not connected to any other components")

    def _validate_vertex(self, vertex: Vertex) -> bool:
        """Validates a vertex."""
        # All vertices that do not have edges are invalid
        return len(self.get_vertex_edges(vertex.id)) > 0

    def get_vertex(self, vertex_id: str) -> Vertex:
        """Returns a vertex by id."""
        try:
            return self.vertex_map[vertex_id]
        except KeyError:
            raise ValueError(f"Vertex {vertex_id} not found")

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

    async def process(self) -> "Graph":
        """Processes the graph with vertices in each layer run in parallel."""
        vertices_layers = self.sorted_vertices_layers
        vertex_task_run_count: Dict[str, int] = {}
        for layer_index, layer in enumerate(vertices_layers):
            tasks = []
            for vertex_id in layer:
                vertex = self.get_vertex(vertex_id)
                task = asyncio.create_task(
                    vertex.build(),
                    name=f"{vertex.display_name} Run {vertex_task_run_count.get(vertex_id, 0)}",
                )
                tasks.append(task)
                vertex_task_run_count[vertex_id] = vertex_task_run_count.get(vertex_id, 0) + 1
            logger.debug(f"Running layer {layer_index} with {len(tasks)} tasks")
            await self._execute_tasks(tasks)
        logger.debug("Graph processing complete")
        return self

    async def _execute_tasks(self, tasks):
        """Executes tasks in parallel, handling exceptions for each task."""
        results = []
        for i, task in enumerate(asyncio.as_completed(tasks)):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                # Log the exception along with the task name for easier debugging
                # task_name = task.get_name()
                # coroutine has not attribute get_name
                task_name = tasks[i].get_name()
                logger.error(f"Task {task_name} failed with exception: {e}")
                # Cancel all remaining tasks
                for t in tasks[i:]:
                    t.cancel()
                raise e
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

    def get_all_successors(self, vertex, recursive=True, flat=True):
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

    def get_successors(self, vertex):
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

        edges: List[ContractEdge] = []
        edges_added = set()
        for edge in self._edges:
            source = self.get_vertex(edge["source"])
            target = self.get_vertex(edge["target"])

            if source is None:
                raise ValueError(f"Source vertex {edge['source']} not found")
            if target is None:
                raise ValueError(f"Target vertex {edge['target']} not found")

            if (source.id, target.id) in edges_added:
                continue

            edges.append(ContractEdge(source, target, edge))
            edges_added.add((source.id, target.id))
        return edges

    def _get_vertex_class(self, node_type: str, node_base_type: str, node_id: str) -> Type[Vertex]:
        """Returns the node class based on the node type."""
        # First we check for the node_base_type
        node_name = node_id.split("-")[0]
        if node_name in ["ChatOutput", "ChatInput"]:
            return ChatVertex
        elif node_name in ["ShouldRunNext"]:
            return RoutingVertex
        elif node_name in ["SharedState", "Notify", "GetNotified"]:
            return StateVertex
        elif node_base_type in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_base_type]
        elif node_name in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_name]

        if node_type in FILE_TOOLS:
            return FileToolVertex
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
            vertex_data = vertex["data"]
            vertex_type: str = vertex_data["type"]  # type: ignore
            vertex_base_type: str = vertex_data["node"]["template"]["_type"]  # type: ignore

            VertexClass = self._get_vertex_class(vertex_type, vertex_base_type, vertex_data["id"])
            vertex_instance = VertexClass(vertex, graph=self)
            vertex_instance.set_top_level(self.top_level_vertices)
            vertices.append(vertex_instance)

        return vertices

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
        return f"Graph:\nNodes: {vertex_ids}\nConnections:\n{edges_repr}"

    def sort_up_to_vertex(self, vertex_id: str, is_start: bool = False) -> List[Vertex]:
        """Cuts the graph up to a given vertex and sorts the resulting subgraph."""
        # Initial setup
        visited = set()  # To keep track of visited vertices
        excluded = set()  # To keep track of vertices that should be excluded
        stack = [vertex_id]  # Use a list as a stack for DFS

        def get_successors(vertex, recursive=True):
            # Recursively get the successors of the current vertex
            successors = vertex.successors
            if not successors:
                return []
            successors_result = []
            for successor in successors:
                # Just return a list of successors
                if recursive:
                    next_successors = get_successors(successor)
                    successors_result.extend(next_successors)
                successors_result.append(successor)
            return successors_result

        # DFS to collect all vertices that can reach the specified vertex
        while stack:
            current_id = stack.pop()
            if current_id not in visited and current_id not in excluded:
                visited.add(current_id)
                current_vertex = self.get_vertex(current_id)
                # Assuming get_predecessors is a method that returns all vertices with edges to current_vertex
                for predecessor in current_vertex.predecessors:
                    stack.append(predecessor.id)

                if current_id == vertex_id:
                    # We should add to visited all the vertices that are successors of the current vertex
                    # and their successors and so on
                    # if the vertex is a start, it means we are starting from the beginning
                    # and getting successors
                    for successor in current_vertex.successors:
                        if is_start:
                            stack.append(successor.id)
                        else:
                            excluded.add(successor.id)
                        all_successors = get_successors(successor)
                        for successor in all_successors:
                            if is_start:
                                stack.append(successor.id)
                            else:
                                excluded.add(successor.id)

        # Filter the original graph's vertices and edges to keep only those in `visited`
        vertices_to_keep = [self.get_vertex(vid) for vid in visited]

        return vertices_to_keep

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

    def sort_vertices(
        self,
        stop_component_id: Optional[str] = None,
        start_component_id: Optional[str] = None,
    ) -> List[str]:
        """Sorts the vertices in the graph."""
        self.mark_all_vertices("ACTIVE")
        if stop_component_id is not None:
            self.stop_vertex = stop_component_id
            vertices = self.sort_up_to_vertex(stop_component_id)
        elif start_component_id:
            vertices = self.sort_up_to_vertex(start_component_id, is_start=True)
        else:
            vertices = self.vertices
            # without component_id we are probably running in the chat
            # so we want to pick only graphs that start with ChatInput or
            # TextInput

        vertices_layers = self.layered_topological_sort(vertices)
        vertices_layers = self.sort_by_avg_build_time(vertices_layers)
        # vertices_layers = self.sort_chat_inputs_first(vertices_layers)
        self.increment_run_count()
        self._sorted_vertices_layers = vertices_layers
        first_layer = vertices_layers[0]
        # save the only the rest
        self.vertices_layers = vertices_layers[1:]
        self.vertices_to_run = {vertex_id for vertex_id in chain.from_iterable(vertices_layers)}
        self.run_map, self.run_predecessors = (
            self.build_run_map(),
            self.predecessor_map.copy(),
        )

        # Return just the first layer
        return first_layer

    def vertex_has_no_more_predecessors(self, vertex_id: str) -> bool:
        """Returns whether a vertex has no more predecessors."""
        return not self.run_predecessors.get(vertex_id)

    def should_run_vertex(self, vertex_id: str) -> bool:
        """Returns whether a component should be run."""
        # the self.run_map is a map of vertex_id to a list of predecessors
        # each time a vertex is run, we remove it from the list of predecessors
        # if a vertex has no more predecessors, it should be run
        should_run = vertex_id in self.vertices_to_run and self.vertex_has_no_more_predecessors(vertex_id)

        if should_run:
            self.vertices_to_run.remove(vertex_id)
            # remove the vertex from the run_map
            self.remove_from_predecessors(vertex_id)
        return should_run

    def remove_from_predecessors(self, vertex_id: str):
        predecessors = self.run_map.get(vertex_id, [])
        for predecessor in predecessors:
            if vertex_id in self.run_predecessors[predecessor]:
                self.run_predecessors[predecessor].remove(vertex_id)

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
