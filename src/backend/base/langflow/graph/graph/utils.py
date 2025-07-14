import copy
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

PRIORITY_LIST_OF_INPUTS = ["webhook", "chat"]
MAX_CYCLE_APPEARANCES = 2


def find_start_component_id(vertices, *, is_webhook: bool = False):
    """Finds the component ID from a list of vertices based on a priority list of input types.

    Args:
        vertices (list): A list of vertex IDs.
        is_webhook (bool, optional): Whether the flow is being run as a webhook. Defaults to False.

    Returns:
        str or None: The component ID that matches the highest priority input type, or None if no match is found.
    """
    # Set priority list based on whether this is a webhook flow
    priority_inputs = ["webhook"] if is_webhook else PRIORITY_LIST_OF_INPUTS

    # Check input types in priority order
    for input_type_str in priority_inputs:
        component_id = next((vertex_id for vertex_id in vertices if input_type_str in vertex_id.lower()), None)
        if component_id:
            return component_id
    return None


def find_last_node(nodes, edges):
    """This function receives a flow and returns the last node."""
    source_ids = {edge["source"] for edge in edges}
    for node in nodes:
        if node["id"] not in source_ids:
            return node
    return None


def add_parent_node_id(nodes, parent_node_id) -> None:
    """This function receives a list of nodes and adds a parent_node_id to each node."""
    for node in nodes:
        node["parent_node_id"] = parent_node_id


def add_frozen(nodes, frozen) -> None:
    """This function receives a list of nodes and adds a frozen to each node."""
    for node in nodes:
        node["data"]["node"]["frozen"] = frozen


def ungroup_node(group_node_data, base_flow):
    template, flow, frozen = (
        group_node_data["node"]["template"],
        group_node_data["node"]["flow"],
        group_node_data["node"].get("frozen", False),
    )
    parent_node_id = group_node_data["id"]

    g_nodes = flow["data"]["nodes"]
    add_parent_node_id(g_nodes, parent_node_id)
    add_frozen(g_nodes, frozen)
    g_edges = flow["data"]["edges"]

    # Redirect edges to the correct proxy node
    updated_edges = get_updated_edges(base_flow, g_nodes, g_edges, group_node_data["id"])

    # Update template values
    update_template(template, g_nodes)

    nodes = [n for n in base_flow["nodes"] if n["id"] != group_node_data["id"]] + g_nodes
    edges = (
        [e for e in base_flow["edges"] if e["target"] != group_node_data["id"] and e["source"] != group_node_data["id"]]
        + g_edges
        + updated_edges
    )

    base_flow["nodes"] = nodes
    base_flow["edges"] = edges

    return nodes


def process_flow(flow_object):
    cloned_flow = copy.deepcopy(flow_object)
    processed_nodes = set()  # To keep track of processed nodes

    def process_node(node) -> None:
        node_id = node.get("id")

        # If node already processed, skip
        if node_id in processed_nodes:
            return

        if node.get("data") and node["data"].get("node") and node["data"]["node"].get("flow"):
            process_flow(node["data"]["node"]["flow"]["data"])
            new_nodes = ungroup_node(node["data"], cloned_flow)
            # Add new nodes to the queue for future processing
            nodes_to_process.extend(new_nodes)

        # Mark node as processed
        processed_nodes.add(node_id)

    nodes_to_process = deque(cloned_flow["nodes"])

    while nodes_to_process:
        node = nodes_to_process.popleft()
        process_node(node)

    return cloned_flow


def update_template(template, g_nodes) -> None:
    """Updates the template of a node in a graph with the given template.

    Args:
        template (dict): The new template to update the node with.
        g_nodes (list): The list of nodes in the graph.
    """
    for value in template.values():
        if not value.get("proxy"):
            continue
        proxy_dict = value["proxy"]
        field, id_ = proxy_dict["field"], proxy_dict["id"]
        node_index = next((i for i, n in enumerate(g_nodes) if n["id"] == id_), -1)
        if node_index != -1:
            display_name = None
            show = g_nodes[node_index]["data"]["node"]["template"][field]["show"]
            advanced = g_nodes[node_index]["data"]["node"]["template"][field]["advanced"]
            if "display_name" in g_nodes[node_index]["data"]["node"]["template"][field]:
                display_name = g_nodes[node_index]["data"]["node"]["template"][field]["display_name"]
            else:
                display_name = g_nodes[node_index]["data"]["node"]["template"][field]["name"]

            g_nodes[node_index]["data"]["node"]["template"][field] = value
            g_nodes[node_index]["data"]["node"]["template"][field]["show"] = show
            g_nodes[node_index]["data"]["node"]["template"][field]["advanced"] = advanced
            g_nodes[node_index]["data"]["node"]["template"][field]["display_name"] = display_name


def update_target_handle(new_edge, g_nodes):
    """Updates the target handle of a given edge if it is a proxy node.

    Args:
        new_edge (dict): The edge to update.
        g_nodes (list): The list of nodes in the graph.

    Returns:
        dict: The updated edge.
    """
    target_handle = new_edge["data"]["targetHandle"]
    if proxy := target_handle.get("proxy"):
        proxy_id = proxy["id"]
        for node in g_nodes:
            if node["id"] == proxy_id:
                set_new_target_handle(proxy_id, new_edge, target_handle, node)
                break

    return new_edge


def set_new_target_handle(proxy_id, new_edge, target_handle, node) -> None:
    """Sets a new target handle for a given edge.

    Args:
        proxy_id (str): The ID of the proxy.
        new_edge (dict): The new edge to be created.
        target_handle (dict): The target handle of the edge.
        node (dict): The node containing the edge.
    """
    new_edge["target"] = proxy_id
    type_ = target_handle.get("type")
    if type_ is None:
        msg = "The 'type' key must be present in target_handle."
        raise KeyError(msg)

    field = target_handle["proxy"]["field"]
    new_target_handle = {
        "fieldName": field,
        "type": type_,
        "id": proxy_id,
    }

    node_data = node["data"]["node"]
    if node_data.get("flow"):
        field_template_proxy = node_data["template"][field]["proxy"]
        new_target_handle["proxy"] = {
            "field": field_template_proxy["field"],
            "id": field_template_proxy["id"],
        }

    if input_types := target_handle.get("inputTypes"):
        new_target_handle["inputTypes"] = input_types

    new_edge["data"]["targetHandle"] = new_target_handle


def update_source_handle(new_edge, g_nodes, g_edges):
    """Updates the source handle of a given edge to the last node in the flow data.

    Args:
        new_edge (dict): The edge to update.
        g_nodes: The graph nodes.
        g_edges: The graph edges.

    Returns:
        dict: The updated edge with the new source handle.
    """
    last_node = copy.deepcopy(find_last_node(g_nodes, g_edges))
    new_edge["source"] = last_node["id"]
    new_source_handle = new_edge["data"]["sourceHandle"]
    new_source_handle["id"] = last_node["id"]
    new_edge["data"]["sourceHandle"] = new_source_handle
    return new_edge


def get_updated_edges(base_flow, g_nodes, g_edges, group_node_id):
    """Get updated edges.

    Given a base flow, a list of graph nodes and a group node id, returns a list of updated edges.
    An updated edge is an edge that has its target or source handle updated based on the group node id.

    Args:
        base_flow (dict): The base flow containing a list of edges.
        g_nodes (list): A list of graph nodes.
        g_edges (list): A list of graph edges.
        group_node_id (str): The id of the group node.

    Returns:
        list: A list of updated edges.
    """
    updated_edges = []
    for edge in base_flow["edges"]:
        new_edge = copy.deepcopy(edge)
        if new_edge["target"] == group_node_id:
            new_edge = update_target_handle(new_edge, g_nodes)

        if new_edge["source"] == group_node_id:
            new_edge = update_source_handle(new_edge, g_nodes, g_edges)

        if group_node_id in {edge["target"], edge["source"]}:
            updated_edges.append(new_edge)
    return updated_edges


def get_successors(graph: dict[str, dict[str, list[str]]], vertex_id: str) -> list[str]:
    successors_result = []
    stack = [vertex_id]
    visited = set()
    while stack:
        current_id = stack.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        if current_id != vertex_id:
            successors_result.append(current_id)
        stack.extend(graph[current_id]["successors"])
    return successors_result


def get_root_of_group_node(
    graph: dict[str, dict[str, list[str]]], vertex_id: str, parent_node_map: dict[str, str | None]
) -> str:
    """Returns the root of a group node."""
    if vertex_id in parent_node_map.values():
        # Get all vertices with vertex_id as their parent node
        child_vertices = [v_id for v_id, parent_id in parent_node_map.items() if parent_id == vertex_id]

        # Now go through successors of the child vertices
        # and get the one that none of its successors is in child_vertices
        for child_id in child_vertices:
            successors = get_successors(graph, child_id)
            if not any(successor in child_vertices for successor in successors):
                return child_id

    msg = f"Vertex {vertex_id} is not a top level vertex or no root vertex found"
    raise ValueError(msg)


def sort_up_to_vertex(
    graph: dict[str, dict[str, list[str]]],
    vertex_id: str,
    *,
    parent_node_map: dict[str, str | None] | None = None,
    is_start: bool = False,
) -> list[str]:
    """Cuts the graph up to a given vertex and sorts the resulting subgraph."""
    try:
        stop_or_start_vertex = graph[vertex_id]
    except KeyError as e:
        if parent_node_map is None:
            msg = "Parent node map is required to find the root of a group node"
            raise ValueError(msg) from e
        vertex_id = get_root_of_group_node(graph=graph, vertex_id=vertex_id, parent_node_map=parent_node_map)
        if vertex_id not in graph:
            msg = f"Vertex {vertex_id} not found into graph"
            raise ValueError(msg) from e
        stop_or_start_vertex = graph[vertex_id]

    visited, excluded = set(), set()
    stack = [vertex_id]
    stop_predecessors = set(stop_or_start_vertex["predecessors"])

    while stack:
        current_id = stack.pop()
        if current_id in visited or current_id in excluded:
            continue

        visited.add(current_id)
        current_vertex = graph[current_id]

        stack.extend(current_vertex["predecessors"])

        if current_id == vertex_id or (current_id not in stop_predecessors and is_start):
            for successor_id in current_vertex["successors"]:
                if is_start:
                    stack.append(successor_id)
                else:
                    excluded.add(successor_id)
                for succ_id in get_successors(graph, successor_id):
                    if is_start:
                        stack.append(succ_id)
                    else:
                        excluded.add(succ_id)

    return list(visited)


def has_cycle(vertex_ids: list[str], edges: list[tuple[str, str]]) -> bool:
    """Determines whether a directed graph represented by a list of vertices and edges contains a cycle.

    Args:
        vertex_ids (list[str]): A list of vertex IDs.
        edges (list[tuple[str, str]]): A list of tuples representing directed edges between vertices.

    Returns:
        bool: True if the graph contains a cycle, False otherwise.
    """
    # Build the graph as an adjacency list
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)

    # Utility function to perform DFS
    def dfs(v, visited, rec_stack) -> bool:
        visited.add(v)
        rec_stack.add(v)

        for neighbor in graph[v]:
            if neighbor not in visited:
                if dfs(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(v)
        return False

    visited: set[str] = set()
    rec_stack: set[str] = set()

    return any(vertex not in visited and dfs(vertex, visited, rec_stack) for vertex in vertex_ids)


def find_cycle_edge(entry_point: str, edges: list[tuple[str, str]]) -> tuple[str, str]:
    """Find the edge that causes a cycle in a directed graph starting from a given entry point.

    Args:
        entry_point (str): The vertex ID from which to start the search.
        edges (list[tuple[str, str]]): A list of tuples representing directed edges between vertices.

    Returns:
        tuple[str, str]: A tuple representing the edge that causes a cycle, or None if no cycle is found.
    """
    # Build the graph as an adjacency list
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)

    # Utility function to perform DFS
    def dfs(v, visited, rec_stack):
        visited.add(v)
        rec_stack.add(v)

        for neighbor in graph[v]:
            if neighbor not in visited:
                result = dfs(neighbor, visited, rec_stack)
                if result:
                    return result
            elif neighbor in rec_stack:
                return (v, neighbor)  # This edge causes the cycle

        rec_stack.remove(v)
        return None

    visited: set[str] = set()
    rec_stack: set[str] = set()

    return dfs(entry_point, visited, rec_stack)


def find_all_cycle_edges(entry_point: str, edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Find all edges that cause cycles in a directed graph starting from a given entry point.

    Args:
        entry_point (str): The vertex ID from which to start the search.
        edges (list[tuple[str, str]]): A list of tuples representing directed edges between vertices.

    Returns:
        list[tuple[str, str]]: A list of tuples representing edges that cause cycles.
    """
    # Build the graph as an adjacency list
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)

    # Utility function to perform DFS
    def dfs(v, visited, rec_stack, cycle_edges):
        visited.add(v)
        rec_stack.add(v)

        for neighbor in graph[v]:
            if neighbor not in visited:
                dfs(neighbor, visited, rec_stack, cycle_edges)
            elif neighbor in rec_stack:
                cycle_edges.append((v, neighbor))  # This edge causes a cycle

        rec_stack.remove(v)

    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycle_edges: list[tuple[str, str]] = []

    dfs(entry_point, visited, rec_stack, cycle_edges)

    return cycle_edges


def should_continue(yielded_counts: dict[str, int], max_iterations: int | None) -> bool:
    if max_iterations is None:
        return True
    return max(yielded_counts.values(), default=0) <= max_iterations


def find_sccs_tarjan(edges: list[tuple[str, str]]):
    """Finds all strongly connected components in a directed graph using Tarjan's algorithm.

    Args:
        edges: A list of tuples representing the directed edges of the graph.

    Returns:
        A list of lists, where each inner list contains the vertices of a strongly connected component.
    """
    graph = defaultdict(list)
    nodes = set()
    self_loops = set()
    append_graph = graph.setdefault  # Minor speedup, local lookup
    add_node = nodes.add  # Minor speedup, local lookup
    add_self = self_loops.add
    for u, v in edges:
        graph[u].append(v)
        add_node(u)
        add_node(v)
        if u == v:
            add_self(u)

    ids = {}
    low = {}
    on_stack = set()
    stack = []
    at = 0
    sccs = []

    def dfs(node):
        nonlocal at
        stack.append(node)
        on_stack.add(node)
        ids[node] = low[node] = at
        at += 1

        for to in graph[node]:
            if to not in ids:
                dfs(to)
                low[node] = min(low[node], low[to])
            elif to in on_stack:
                low[node] = min(low[node], ids[to])

        if ids[node] == low[node]:
            scc = []
            while True:
                n = stack.pop()
                on_stack.remove(n)
                scc.append(n)
                if n == node:
                    break
            sccs.append(scc)

    for node in nodes:
        if node not in ids:
            dfs(node)
    return sccs, self_loops


def find_cycle_vertices(edges: list[tuple[str, str]]) -> list[str]:
    """Finds all vertices that are part of a cycle in a directed graph.

    This implementation uses Tarjan's algorithm to find strongly connected components.
    Any SCC with more than one vertex or a single vertex with a self-loop is a cycle.

    Args:
        edges: A list of tuples representing the directed edges of the graph.

    Returns:
        A sorted list of vertices that are part of a cycle.
    """
    sccs, self_loops = find_sccs_tarjan(edges)
    cycle_vertices = set()
    for scc in sccs:
        if len(scc) > 1:
            cycle_vertices.update(scc)
        elif scc[0] in self_loops:
            cycle_vertices.add(scc[0])
    return sorted(cycle_vertices)


def layered_topological_sort(
    vertices_ids: set[str],
    in_degree_map: dict[str, int],
    successor_map: dict[str, list[str]],
    predecessor_map: dict[str, list[str]],
    start_id: str | None = None,
    cycle_vertices: set[str] | None = None,
    is_input_vertex: Callable[[str], bool] | None = None,  # noqa: ARG001
    *,
    is_cyclic: bool = False,
) -> list[list[str]]:
    """Performs a layered topological sort of the vertices in the graph.

    Args:
        vertices_ids: Set of vertex IDs to sort
        in_degree_map: Map of vertex IDs to their in-degree
        successor_map: Map of vertex IDs to their successors
        predecessor_map: Map of vertex IDs to their predecessors
        is_cyclic: Whether the graph is cyclic
        start_id: ID of the start vertex (if any)
        cycle_vertices: Set of vertices that form a cycle
        is_input_vertex: Function to check if a vertex is an input vertex

    Returns:
        List of layers, where each layer is a list of vertex IDs
    """
    # Queue for vertices with no incoming edges
    cycle_vertices = cycle_vertices or set()
    in_degree_map = in_degree_map.copy()

    if is_cyclic and all(in_degree_map.values()):
        # This means we have a cycle because all vertex have in_degree_map > 0
        # because of this we set the queue to start on the start_id if it exists
        if start_id is not None:
            queue = deque([start_id])
            # Reset in_degree for start_id to allow cycle traversal
            in_degree_map[start_id] = 0
        else:
            # Find the chat input component
            chat_input = find_start_component_id(vertices_ids)
            if chat_input is None:
                # If no input component is found, start with any vertex
                queue = deque([next(iter(vertices_ids))])
                in_degree_map[next(iter(vertices_ids))] = 0
            else:
                queue = deque([chat_input])
                # Reset in_degree for chat_input to allow cycle traversal
                in_degree_map[chat_input] = 0
    else:
        # Start with vertices that have no incoming edges or are input vertices
        queue = deque(
            vertex_id
            for vertex_id in vertices_ids
            if in_degree_map[vertex_id] == 0
            # We checked if it is input but that caused the TextInput to be at the start
            # or (is_input_vertex and is_input_vertex(vertex_id))
        )

    layers: list[list[str]] = []
    visited = set()
    cycle_counts = dict.fromkeys(vertices_ids, 0)
    current_layer = 0

    # Process the first layer separately to avoid duplicates
    if queue:
        layers.append([])  # Start the first layer
        first_layer_vertices = set()
        layer_size = len(queue)
        for _ in range(layer_size):
            vertex_id = queue.popleft()
            if vertex_id not in first_layer_vertices:
                first_layer_vertices.add(vertex_id)
                visited.add(vertex_id)
                cycle_counts[vertex_id] += 1
                layers[current_layer].append(vertex_id)

            for neighbor in successor_map[vertex_id]:
                # only vertices in `vertices_ids` should be considered
                # because vertices by have been filtered out
                # in a previous step. All dependencies of theirs
                # will be built automatically if required
                if neighbor not in vertices_ids:
                    continue

                in_degree_map[neighbor] -= 1  # 'remove' edge
                if in_degree_map[neighbor] == 0:
                    queue.append(neighbor)

                # if > 0 it might mean not all predecessors have added to the queue
                # so we should process the neighbors predecessors
                elif in_degree_map[neighbor] > 0:
                    for predecessor in predecessor_map[neighbor]:
                        if (
                            predecessor not in queue
                            and predecessor not in first_layer_vertices
                            and (in_degree_map[predecessor] == 0 or predecessor in cycle_vertices)
                        ):
                            queue.append(predecessor)

        current_layer += 1  # Next layer

    # Process remaining layers normally, allowing cycle vertices to appear multiple times
    while queue:
        layers.append([])  # Start a new layer
        layer_size = len(queue)
        for _ in range(layer_size):
            vertex_id = queue.popleft()
            if vertex_id not in visited or (is_cyclic and cycle_counts[vertex_id] < MAX_CYCLE_APPEARANCES):
                if vertex_id not in visited:
                    visited.add(vertex_id)
                cycle_counts[vertex_id] += 1
                layers[current_layer].append(vertex_id)

            for neighbor in successor_map[vertex_id]:
                # only vertices in `vertices_ids` should be considered
                # because vertices by have been filtered out
                # in a previous step. All dependencies of theirs
                # will be built automatically if required
                if neighbor not in vertices_ids:
                    continue

                in_degree_map[neighbor] -= 1  # 'remove' edge
                if in_degree_map[neighbor] == 0 and neighbor not in visited:
                    queue.append(neighbor)
                    # # If this is a cycle vertex, reset its in_degree to allow it to appear again
                    # if neighbor in cycle_vertices and neighbor in visited:
                    #     in_degree_map[neighbor] = len(predecessor_map[neighbor])

                # if > 0 it might mean not all predecessors have added to the queue
                # so we should process the neighbors predecessors
                elif in_degree_map[neighbor] > 0:
                    for predecessor in predecessor_map[neighbor]:
                        if predecessor not in queue and (
                            predecessor not in visited
                            or (is_cyclic and cycle_counts[predecessor] < MAX_CYCLE_APPEARANCES)
                        ):
                            queue.append(predecessor)

        current_layer += 1  # Next layer

    # Remove empty layers
    return [layer for layer in layers if layer]


def refine_layers(
    initial_layers: list[list[str]],
    successor_map: dict[str, list[str]],
) -> list[list[str]]:
    """Refines the layers of vertices to ensure proper dependency ordering.

    Args:
        initial_layers: Initial layers of vertices
        successor_map: Map of vertex IDs to their successors

    Returns:
        Refined layers with proper dependency ordering
    """
    # Map each vertex to its current layer
    vertex_to_layer: dict[str, int] = {}
    for layer_index, layer in enumerate(initial_layers):
        for vertex in layer:
            vertex_to_layer[vertex] = layer_index

    refined_layers: list[list[str]] = [[] for _ in initial_layers]  # Start with empty layers
    new_layer_index_map = defaultdict(int)

    # Map each vertex to its new layer index
    # by finding the lowest layer index of its dependencies
    # and subtracting 1
    # If a vertex has no dependencies, it will be placed in the first layer
    # If a vertex has dependencies, it will be placed in the lowest layer index of its dependencies
    # minus 1
    for vertex_id, deps in successor_map.items():
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
    return [layer for layer in refined_layers if layer]


def _max_dependency_index(
    vertex_id: str,
    index_map: dict[str, int],
    get_vertex_successors: Callable[[str], list[str]],
) -> int:
    """Finds the highest index a given vertex's dependencies occupy in the same layer.

    Args:
        vertex_id: ID of the vertex to check
        index_map: Map of vertex IDs to their indices in the layer
        get_vertex_successors: Function to get the successor IDs of a vertex

    Returns:
        The highest index of the vertex's dependencies
    """
    max_index = -1
    for successor_id in get_vertex_successors(vertex_id):
        successor_index = index_map.get(successor_id, -1)
        max_index = max(successor_index, max_index)
    return max_index


def _sort_single_layer_by_dependency(
    layer: list[str],
    get_vertex_successors: Callable[[str], list[str]],
) -> list[str]:
    """Sorts a single layer by dependency using a stable sorting method.

    Args:
        layer: List of vertex IDs in the layer
        get_vertex_successors: Function to get the successor IDs of a vertex

    Returns:
        Sorted list of vertex IDs
    """
    # Build a map of each vertex to its index in the layer for quick lookup.
    index_map = {vertex: index for index, vertex in enumerate(layer)}
    dependency_cache: dict[str, int] = {}

    def max_dependency_index(vertex: str) -> int:
        if vertex in dependency_cache:
            return dependency_cache[vertex]
        max_index = index_map[vertex]
        for successor in get_vertex_successors(vertex):
            if successor in index_map:
                max_index = max(max_index, max_dependency_index(successor))

        dependency_cache[vertex] = max_index
        return max_index

    return sorted(layer, key=max_dependency_index, reverse=True)


def sort_layer_by_dependency(
    vertices_layers: list[list[str]],
    get_vertex_successors: Callable[[str], list[str]],
) -> list[list[str]]:
    """Sorts the vertices in each layer by dependency, ensuring no vertex depends on a subsequent vertex.

    Args:
        vertices_layers: List of layers, where each layer is a list of vertex IDs
        get_vertex_successors: Function to get the successor IDs of a vertex

    Returns:
        Sorted layers
    """
    return [_sort_single_layer_by_dependency(layer, get_vertex_successors) for layer in vertices_layers]


def sort_chat_inputs_first(
    vertices_layers: list[list[str]],
    get_vertex_predecessors: Callable[[str], list[str]],
) -> list[list[str]]:
    """Sorts the vertices so that chat inputs come first in the layers.

    Only one chat input is allowed in the entire graph.

    Args:
        vertices_layers: List of layers, where each layer is a list of vertex IDs
        get_vertex_predecessors: Function to get the predecessor IDs of a vertex

    Returns:
        Sorted layers with single chat input first

    Raises:
        ValueError: If there are multiple chat inputs in the graph
    """
    chat_input = None
    chat_input_layer_idx = None

    # Find chat input and validate only one exists
    for layer_idx, layer in enumerate(vertices_layers):
        for vertex_id in layer:
            if "ChatInput" in vertex_id and get_vertex_predecessors(vertex_id):
                return vertices_layers
            if "ChatInput" in vertex_id:
                if chat_input is not None:
                    msg = "Only one chat input is allowed in the graph"
                    raise ValueError(msg)
                chat_input = vertex_id
                chat_input_layer_idx = layer_idx

    if not chat_input:
        return vertices_layers
    # If chat input already in first layer, just move it to index 0
    if chat_input_layer_idx == 0:
        # If chat input is alone in first layer, keep as-is
        if len(vertices_layers[0]) == 1:
            return vertices_layers

        # Otherwise move chat input to its own layer at the start
        vertices_layers[0].remove(chat_input)
        return [[chat_input], *vertices_layers]

    # Otherwise create new layers with chat input first
    result_layers = []
    for layer in vertices_layers:
        layer_vertices = [v for v in layer if v != chat_input]
        if layer_vertices:
            result_layers.append(layer_vertices)

    return [[chat_input], *result_layers]


def get_sorted_vertices(
    vertices_ids: list[str],
    cycle_vertices: set[str],
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    graph_dict: dict[str, Any] | None = None,
    in_degree_map: dict[str, int] | None = None,
    successor_map: dict[str, list[str]] | None = None,
    predecessor_map: dict[str, list[str]] | None = None,
    is_input_vertex: Callable[[str], bool] | None = None,
    get_vertex_predecessors: Callable[[str], list[str]] | None = None,
    get_vertex_successors: Callable[[str], list[str]] | None = None,
    *,
    is_cyclic: bool = False,
) -> tuple[list[str], list[list[str]]]:
    """Get sorted vertices in a graph.

    Args:
        vertices_ids: List of vertex IDs to sort
        cycle_vertices: Set of vertices that form a cycle
        stop_component_id: ID of the stop component (if any)
        start_component_id: ID of the start component (if any)
        graph_dict: Dictionary containing graph information
        in_degree_map: Map of vertex IDs to their in-degree
        successor_map: Map of vertex IDs to their successors
        predecessor_map: Map of vertex IDs to their predecessors
        is_input_vertex: Function to check if a vertex is an input vertex
        get_vertex_predecessors: Function to get predecessors of a vertex
        get_vertex_successors: Function to get successors of a vertex
        is_cyclic: Whether the graph is cyclic

    Returns:
        Tuple of (first layer vertices, remaining layer vertices)
    """
    # Handle cycles by converting stop to start
    if stop_component_id in cycle_vertices:
        start_component_id = stop_component_id
        stop_component_id = None

    # Build in_degree_map if not provided
    if in_degree_map is None:
        in_degree_map = {}
        for vertex_id in vertices_ids:
            if get_vertex_predecessors is not None:
                in_degree_map[vertex_id] = len(get_vertex_predecessors(vertex_id))
            else:
                in_degree_map[vertex_id] = 0

    # Build successor_map if not provided
    if successor_map is None:
        successor_map = {}
        for vertex_id in vertices_ids:
            if get_vertex_successors is not None:
                successor_map[vertex_id] = get_vertex_successors(vertex_id)
            else:
                successor_map[vertex_id] = []

    # Build predecessor_map if not provided
    if predecessor_map is None:
        predecessor_map = {}
        for vertex_id in vertices_ids:
            if get_vertex_predecessors is not None:
                predecessor_map[vertex_id] = get_vertex_predecessors(vertex_id)
            else:
                predecessor_map[vertex_id] = []

    # If we have a stop component, we need to filter out all vertices
    # that are not predecessors of the stop component
    if stop_component_id is not None:
        filtered_vertices = filter_vertices_up_to_vertex(
            vertices_ids,
            stop_component_id,
            get_vertex_predecessors=get_vertex_predecessors,
            get_vertex_successors=get_vertex_successors,
            graph_dict=graph_dict,
        )
        vertices_ids = list(filtered_vertices)

    # If we have a start component, we need to filter out unconnected vertices
    # but keep vertices that are connected to the graph even if not reachable from start
    if start_component_id is not None:
        # First get all vertices reachable from start
        reachable_vertices = filter_vertices_from_vertex(
            vertices_ids,
            start_component_id,
            get_vertex_predecessors=get_vertex_predecessors,
            get_vertex_successors=get_vertex_successors,
            graph_dict=graph_dict,
        )
        # Then get all vertices that can reach any reachable vertex
        connected_vertices = set()
        for vertex in reachable_vertices:
            connected_vertices.update(
                filter_vertices_up_to_vertex(
                    vertices_ids,
                    vertex,
                    get_vertex_predecessors=get_vertex_predecessors,
                    get_vertex_successors=get_vertex_successors,
                    graph_dict=graph_dict,
                )
            )
        vertices_ids = list(connected_vertices)

    # Get the layers
    layers = layered_topological_sort(
        vertices_ids=set(vertices_ids),
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        start_id=start_component_id,
        is_input_vertex=is_input_vertex,
        cycle_vertices=cycle_vertices,
        is_cyclic=is_cyclic,
    )

    # Split into first layer and remaining layers
    if not layers:
        return [], []

    first_layer = layers[0]
    remaining_layers = layers[1:]

    # If we have a stop component, we need to filter out all vertices
    # that are not predecessors of the stop component
    if stop_component_id is not None and remaining_layers and stop_component_id not in remaining_layers[-1]:
        remaining_layers[-1].append(stop_component_id)

    # Sort chat inputs first and sort each layer by dependencies
    all_layers = [first_layer, *remaining_layers]
    if get_vertex_predecessors is not None and start_component_id is None:
        all_layers = sort_chat_inputs_first(all_layers, get_vertex_predecessors)
    if get_vertex_successors is not None:
        all_layers = sort_layer_by_dependency(all_layers, get_vertex_successors)

    if not all_layers:
        return [], []

    return all_layers[0], all_layers[1:]


def filter_vertices_up_to_vertex(
    vertices_ids: list[str],
    vertex_id: str,
    get_vertex_predecessors: Callable[[str], list[str]] | None = None,
    get_vertex_successors: Callable[[str], list[str]] | None = None,
    graph_dict: dict[str, Any] | None = None,
) -> set[str]:
    """Filter vertices up to a given vertex.

    Args:
        vertices_ids: List of vertex IDs to filter
        vertex_id: ID of the vertex to filter up to
        get_vertex_predecessors: Function to get predecessors of a vertex
        get_vertex_successors: Function to get successors of a vertex
        graph_dict: Dictionary containing graph information
        parent_node_map: Map of vertex IDs to their parent node IDs

    Returns:
        Set of vertex IDs that are predecessors of the given vertex
    """
    vertices_set = set(vertices_ids)
    if vertex_id not in vertices_set:
        return set()

    # Build predecessor map if not provided
    if get_vertex_predecessors is None:
        if graph_dict is None:
            msg = "Either get_vertex_predecessors or graph_dict must be provided"
            raise ValueError(msg)

        def get_vertex_predecessors(v):
            return graph_dict[v]["predecessors"]

    # Build successor map if not provided
    if get_vertex_successors is None:
        if graph_dict is None:
            return set()

        def get_vertex_successors(v):
            return graph_dict[v]["successors"]

    # Start with the target vertex
    filtered_vertices = {vertex_id}
    queue = deque([vertex_id])

    # Process vertices in breadth-first order
    while queue:
        current_vertex = queue.popleft()
        for predecessor in get_vertex_predecessors(current_vertex):
            if predecessor in vertices_set and predecessor not in filtered_vertices:
                filtered_vertices.add(predecessor)
                queue.append(predecessor)

    return filtered_vertices


def filter_vertices_from_vertex(
    vertices_ids: list[str],
    vertex_id: str,
    get_vertex_predecessors: Callable[[str], list[str]] | None = None,
    get_vertex_successors: Callable[[str], list[str]] | None = None,
    graph_dict: dict[str, Any] | None = None,
) -> set[str]:
    """Filter vertices starting from a given vertex.

    Args:
        vertices_ids: List of vertex IDs to filter
        vertex_id: ID of the vertex to start filtering from
        get_vertex_predecessors: Function to get predecessors of a vertex
        get_vertex_successors: Function to get successors of a vertex
        graph_dict: Dictionary containing graph information

    Returns:
        Set of vertex IDs that are successors of the given vertex
    """
    vertices_set = set(vertices_ids)
    if vertex_id not in vertices_set:
        return set()

    # Build predecessor map if not provided
    if get_vertex_predecessors is None:
        if graph_dict is None:
            msg = "Either get_vertex_predecessors or graph_dict must be provided"
            raise ValueError(msg)

        def get_vertex_predecessors(v):
            return graph_dict[v]["predecessors"]

    # Build successor map if not provided
    if get_vertex_successors is None:
        if graph_dict is None:
            return set()

        def get_vertex_successors(v):
            return graph_dict[v]["successors"]

    # Start with the target vertex
    filtered_vertices = {vertex_id}
    queue = deque([vertex_id])

    # Process vertices in breadth-first order
    while queue:
        current_vertex = queue.popleft()
        for successor in get_vertex_successors(current_vertex):
            if successor in vertices_set and successor not in filtered_vertices:
                filtered_vertices.add(successor)
                queue.append(successor)

    return filtered_vertices
