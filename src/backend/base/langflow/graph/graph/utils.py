import copy
from collections import defaultdict, deque

import networkx as nx

PRIORITY_LIST_OF_INPUTS = ["webhook", "chat"]


def find_start_component_id(vertices):
    """Finds the component ID from a list of vertices based on a priority list of input types.

    Args:
        vertices (list): A list of vertex IDs.

    Returns:
        str or None: The component ID that matches the highest priority input type, or None if no match is found.
    """
    for input_type_str in PRIORITY_LIST_OF_INPUTS:
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
    if target_handle.get("proxy"):
        proxy_id = target_handle["proxy"]["id"]
        if node := next((n for n in g_nodes if n["id"] == proxy_id), None):
            set_new_target_handle(proxy_id, new_edge, target_handle, node)
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
    if node["data"]["node"].get("flow"):
        new_target_handle["proxy"] = {
            "field": node["data"]["node"]["template"][field]["proxy"]["field"],
            "id": node["data"]["node"]["template"][field]["proxy"]["id"],
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
    def dfs(v, visited, rec_stack):
        visited.add(v)
        rec_stack.add(v)

        cycle_edges = []

        for neighbor in graph[v]:
            if neighbor not in visited:
                cycle_edges += dfs(neighbor, visited, rec_stack)
            elif neighbor in rec_stack:
                cycle_edges.append((v, neighbor))  # This edge causes a cycle

        rec_stack.remove(v)
        return cycle_edges

    visited: set[str] = set()
    rec_stack: set[str] = set()

    return dfs(entry_point, visited, rec_stack)


def should_continue(yielded_counts: dict[str, int], max_iterations: int | None) -> bool:
    if max_iterations is None:
        return True
    return max(yielded_counts.values(), default=0) <= max_iterations


def find_cycle_vertices(edges):
    graph = nx.DiGraph(edges)

    # Initialize a set to collect vertices part of any cycle
    cycle_vertices = set()

    # Utilize the strong component feature in NetworkX to find cycles
    for component in nx.strongly_connected_components(graph):
        if len(component) > 1 or graph.has_edge(tuple(component)[0], tuple(component)[0]):  # noqa: RUF015
            cycle_vertices.update(component)

    return sorted(cycle_vertices)
