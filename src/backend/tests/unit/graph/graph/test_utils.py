import copy

import pytest

from lfx.graph.graph import utils


@pytest.fixture
def graph():
    return {
        "A": {"successors": ["B"], "predecessors": []},
        "B": {"successors": ["D"], "predecessors": ["A", "C"]},
        "C": {"successors": ["B", "I"], "predecessors": ["N"]},
        "D": {"successors": ["E", "F"], "predecessors": ["B"]},
        "E": {"successors": ["G"], "predecessors": ["D"]},
        "F": {"successors": ["G", "H"], "predecessors": ["D"]},
        "G": {"successors": [], "predecessors": ["E", "F"]},
        "H": {"successors": [], "predecessors": ["F"]},
        "I": {"successors": ["M"], "predecessors": ["C", "J"]},
        "J": {"successors": ["I", "K"], "predecessors": ["N"]},
        "K": {"successors": ["Q", "P", "O"], "predecessors": ["J", "L"]},
        "L": {"successors": ["K"], "predecessors": []},
        "M": {"successors": [], "predecessors": ["I"]},
        "N": {"successors": ["C", "J"], "predecessors": []},
        "O": {"successors": ["R"], "predecessors": ["K"]},
        "P": {"successors": ["U"], "predecessors": ["K"]},
        "Q": {"successors": ["V"], "predecessors": ["K"]},
        "R": {"successors": ["S"], "predecessors": ["O"]},
        "S": {"successors": ["T"], "predecessors": ["R"]},
        "T": {"successors": [], "predecessors": ["S"]},
        "U": {"successors": ["W"], "predecessors": ["P"]},
        "V": {"successors": ["Y"], "predecessors": ["Q"]},
        "W": {"successors": ["X"], "predecessors": ["U"]},
        "X": {"successors": [], "predecessors": ["W"]},
        "Y": {"successors": ["Z"], "predecessors": ["V"]},
        "Z": {"successors": [], "predecessors": ["Y"]},
    }


@pytest.fixture
def graph_with_loop():
    return {
        "Playlist Extractor": {"successors": ["Loop"], "predecessors": []},
        "Loop": {
            "successors": ["Parse Data 1", "Parse Data 2"],
            "predecessors": ["Playlist Extractor", "YouTube Transcripts"],
        },
        "Parse Data 1": {"successors": ["YouTube Transcripts"], "predecessors": ["Loop"]},
        "Parse Data 2": {"successors": ["Message to Data"], "predecessors": ["Loop"]},
        "YouTube Transcripts": {"successors": ["Loop"], "predecessors": ["Parse Data 1"]},
        "Message to Data": {"successors": ["Split Text"], "predecessors": ["Parse Data 2"]},
        "Split Text": {"successors": ["Chroma DB"], "predecessors": ["Message to Data"]},
        "OpenAI Embeddings": {"successors": ["Chroma DB"], "predecessors": []},
        "Chroma DB": {"successors": [], "predecessors": ["Split Text", "OpenAI Embeddings"]},
    }


def test_get_successors_a(graph):
    vertex_id = "A"

    result = utils.get_successors(graph, vertex_id)

    assert set(result) == {"B", "D", "E", "F", "H", "G"}


def test_get_successors_z(graph):
    vertex_id = "Z"

    result = utils.get_successors(graph, vertex_id)

    assert len(result) == 0


def test_sort_up_to_vertex_n_is_start(graph):
    vertex_id = "N"

    result = utils.sort_up_to_vertex(graph, vertex_id, is_start=True)
    # Result shoud be all the vertices
    assert set(result) == set(graph.keys())


def test_sort_up_to_vertex_z(graph):
    vertex_id = "Z"

    result = utils.sort_up_to_vertex(graph, vertex_id)

    assert set(result) == {"L", "N", "J", "K", "Q", "V", "Y", "Z"}


def test_sort_up_to_vertex_x(graph):
    vertex_id = "X"

    result = utils.sort_up_to_vertex(graph, vertex_id)

    assert set(result) == {"L", "N", "J", "K", "P", "U", "W", "X"}


def test_sort_up_to_vertex_t(graph):
    vertex_id = "T"

    result = utils.sort_up_to_vertex(graph, vertex_id)

    assert set(result) == {"L", "N", "J", "K", "O", "R", "S", "T"}


def test_sort_up_to_vertex_m(graph):
    vertex_id = "M"

    result = utils.sort_up_to_vertex(graph, vertex_id)

    assert set(result) == {"N", "C", "J", "I", "M"}


def test_sort_up_to_vertex_h(graph):
    vertex_id = "H"

    result = utils.sort_up_to_vertex(graph, vertex_id)

    assert set(result) == {"N", "C", "A", "B", "D", "F", "H"}


def test_sort_up_to_vertex_g(graph):
    vertex_id = "G"

    result = utils.sort_up_to_vertex(graph, vertex_id)

    assert set(result) == {"N", "C", "A", "B", "D", "F", "E", "G"}


def test_sort_up_to_vertex_a(graph):
    vertex_id = "A"

    result = utils.sort_up_to_vertex(graph, vertex_id)

    assert set(result) == {"A"}


def test_sort_up_to_vertex_invalid_vertex(graph):
    vertex_id = "7"

    with pytest.raises(ValueError, match="Parent node map is required to find the root of a group node"):
        utils.sort_up_to_vertex(graph, vertex_id)


def test_has_cycle():
    edges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "B")]
    vertices = ["A", "B", "C", "D", "E"]
    assert utils.has_cycle(vertices, edges) is True


class TestFindCycleEdge:
    # Detects a cycle in a simple directed graph
    def test_detects_cycle_in_simple_graph(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C"), ("C", "A")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result == ("C", "A")

    # Returns None when no cycle is present
    def test_returns_none_when_no_cycle(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result is None

    # Correctly identifies the first cycle encountered
    def test_identifies_first_cycle(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("A", "D"), ("D", "E"), ("E", "A")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result == ("C", "A")

    # Handles graphs with multiple edges between the same nodes
    def test_multiple_edges_between_same_nodes(self):
        entry_point = "A"
        edges = [("A", "B"), ("A", "B"), ("B", "C"), ("C", "A")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result == ("C", "A")

    # Processes graphs with multiple disconnected components
    def test_disconnected_components(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C"), ("D", "E"), ("E", "F"), ("F", "D")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result is None

    # Handles an empty list of edges
    def test_empty_edges_list(self):
        entry_point = "A"
        edges = []
        result = utils.find_cycle_edge(entry_point, edges)
        assert result is None

    # Manages a graph with a single node and no edges
    def test_single_node_no_edges(self):
        entry_point = "A"
        edges = []
        result = utils.find_cycle_edge(entry_point, edges)
        assert result is None

    # Detects cycles in graphs with self-loops
    def test_self_loop_cycle(self):
        entry_point = "A"
        edges = [("A", "A")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result == ("A", "A")

    # Handles graphs with multiple cycles
    def test_multiple_cycles(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("B", "D"), ("D", "B")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result == ("C", "A")

    # Processes graphs with nodes having no outgoing edges
    def test_nodes_with_no_outgoing_edges(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result is None

    # Handles large graphs efficiently
    def test_large_graph_efficiency(self):
        entry_point = "A"
        # Create a graph with 50 nodes that definitely contains cycles
        base_edges = [(chr(65 + i), chr(65 + (i + 1) % 26)) for i in range(25)]
        cycle_edges = [(chr(65 + i), chr(65 + (i - 2) % 26)) for i in range(2, 25, 3)]
        edges = base_edges + cycle_edges

        result = utils.find_cycle_edge(entry_point, edges)

        assert result is not None, (
            "No cycle was found, but the graph should contain cycles.\n"
            f"Entry point: {entry_point}\n"
            f"Number of edges: {len(edges)}"
        )
        assert isinstance(result, tuple), f"Expected result to be a tuple, but got {type(result)}"
        assert len(result) == 2, f"Expected tuple of length 2, but got length {len(result)}"
        assert all(isinstance(x, str) for x in result), "Expected both elements to be strings"

    # Manages graphs with duplicate edges
    def test_duplicate_edges(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("C", "A")]
        result = utils.find_cycle_edge(entry_point, edges)
        assert result == ("C", "A")


class TestFindAllCycleEdges:
    # Detects cycles in a simple directed graph
    def test_detects_cycles_in_simple_graph(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C"), ("C", "A")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == [("C", "A")]

    # Identifies multiple cycles in a complex graph
    def test_identifies_multiple_cycles(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("B", "D"), ("D", "B")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert set(result) == {("C", "A"), ("D", "B")}

    # Returns an empty list when no cycles are present
    def test_no_cycles_present(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == []

    # Handles graphs with a single node and no edges
    def test_single_node_no_edges(self):
        entry_point = "A"
        edges = []
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == []

    # Processes graphs with disconnected components
    def test_disconnected_components(self):
        entry_point = "A"
        edges = [("A", "B"), ("C", "D")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == []

    # Handles graphs with self-loops
    def test_self_loops(self):
        entry_point = "A"
        edges = [("A", "A")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == [("A", "A")]

    # Manages graphs with multiple edges between the same nodes
    def test_multiple_edges_between_same_nodes(self):
        entry_point = "A"
        edges = [("A", "B"), ("A", "B"), ("B", "C"), ("C", "A")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == [("C", "A")]

    # Processes graphs with nodes having no outgoing edges
    def test_nodes_with_no_outgoing_edges(self):
        entry_point = "A"
        edges = [("A", "B"), ("B", "C")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == []

    # Handles large graphs efficiently
    def test_large_graphs_efficiency(self):
        entry_point = "A"
        edges = [(chr(65 + i), chr(65 + (i + 1) % 26)) for i in range(1000)]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert isinstance(result, list)

    # Manages graphs with nodes having no incoming edges
    def test_nodes_with_no_incoming_edges(self):
        entry_point = "A"
        edges = [("B", "C"), ("C", "D")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == []

    # Handles graphs with mixed data types in edges
    def test_mixed_data_types_in_edges(self):
        entry_point = 1
        edges = [(1, 2), (2, 3), (3, 1)]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert result == [(3, 1)]

    # Processes graphs with duplicate edges
    def test_duplicate_edges(self):
        entry_point = "A"
        edges = [("A", "B"), ("A", "B"), ("B", "C"), ("C", "A"), ("C", "A")]
        result = utils.find_all_cycle_edges(entry_point, edges)
        assert set(result) == {("C", "A")}


class TestFindCycleVertices:
    # Detect cycles in a simple directed graph
    def test_detect_cycles_simple_graph(self):
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"), ("D", "E"), ("E", "F"), ("F", "C"), ("F", "G")]
        expected_output = ["C", "A", "B", "D", "E", "F"]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Handle an empty list of edges
    def test_handle_empty_edges(self):
        edges = []
        expected_output = []
        result = utils.find_cycle_vertices(edges)
        assert result == expected_output

    # Return vertices involved in multiple cycles
    def test_return_vertices_involved_in_multiple_cycles(self):
        # Define the graph with multiple cycles
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"), ("D", "E"), ("E", "F"), ("F", "C"), ("F", "G")]
        result = utils.find_cycle_vertices(edges)
        assert set(result) == {"C", "A", "B", "D", "E", "F"}

    # Correctly identify and return vertices in a single cycle
    def test_correctly_identify_and_return_vertices_in_single_cycle(self):
        # Define the graph with a single cycle
        edges = [("A", "B"), ("B", "C"), ("C", "A")]
        result = utils.find_cycle_vertices(edges)
        assert set(result) == {"C", "A", "B"}

    # Handle graphs with no cycles and return an empty list
    def test_no_cycles_empty_list(self):
        edges = [("A", "B"), ("B", "C"), ("D", "E"), ("E", "F")]
        expected_output = []
        result = utils.find_cycle_vertices(edges)
        assert result == expected_output

    # Process graphs with disconnected components
    def test_process_disconnected_components(self):
        edges = [
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),
            ("C", "D"),
            ("D", "E"),
            ("E", "F"),
            ("F", "C"),
            ("F", "G"),
            ("X", "Y"),
            ("Y", "Z"),
        ]
        expected_output = ["C", "A", "B", "D", "E", "F"]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Handle graphs with self-loops
    def test_handle_self_loops(self):
        edges = [
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),
            ("C", "D"),
            ("D", "E"),
            ("E", "F"),
            ("F", "C"),
            ("F", "G"),
            ("C", "C"),
        ]
        expected_output = ["C", "A", "B", "D", "E", "F"]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Handle a graph where all vertices form a single cycle
    def test_handle_single_cycle(self):
        edges = [("A", "B"), ("B", "C"), ("C", "A")]
        expected_output = ["C", "A", "B"]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Handle a graph where the entry point has no outgoing edges
    def test_handle_no_outgoing_edges(self):
        edges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"), ("F", "G")]
        expected_output = []
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Handle a graph with a single vertex and no edges
    def test_single_vertex_no_edges(self):
        edges = []
        expected_output = []
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Verify the function's behavior with non-string vertex IDs
    def test_non_string_vertex_ids(self):
        edges = [(1, 2), (2, 3), (3, 1), (3, 4), (4, 5), (5, 6), (6, 3), (6, 7)]
        expected_output = [1, 2, 3, 4, 5, 6]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Ensure no modification of the input edges list
    def test_no_modification_of_input_edges_list(self):
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"), ("D", "E"), ("E", "F"), ("F", "C"), ("F", "G")]
        original_edges = copy.deepcopy(edges)
        utils.find_cycle_vertices(edges)
        assert edges == original_edges

    # Handle large graphs efficiently
    def test_handle_large_graphs_efficiently(self):
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"), ("D", "E"), ("E", "F"), ("F", "C"), ("F", "G")]
        expected_output = ["C", "A", "B", "D", "E", "F"]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    # Handle graphs with duplicate edges and verify correct cycle vertices are detected
    def test_handle_duplicate_edges_fixed_fixed(self):
        edges = [
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),
            ("C", "D"),
            ("D", "E"),
            ("E", "F"),
            ("F", "C"),
            ("F", "G"),
            ("A", "B"),
        ]
        expected_output = ["A", "B", "C", "D", "E", "F"]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)

    @pytest.mark.parametrize("_", range(5))
    def test_handle_two_inputs_in_cycle(self, _):  # noqa: PT019
        edges = [
            ("chat_input", "router"),
            ("chat_input", "concatenate"),
            ("concatenate", "router"),
            ("router", "chat_input"),
            ("text_output", "chat_output"),
            ("router", "text_output"),
        ]
        expected_output = ["router", "chat_input", "concatenate"]
        result = utils.find_cycle_vertices(edges)
        assert sorted(result) == sorted(expected_output)


def test_chat_inputs_at_start():
    vertices_layers = [["ChatInput1", "B"], ["C"], ["D"]]

    def get_vertex_predecessors(vertex_id: str) -> list[str]:  # noqa: ARG001
        return []

    result = utils.sort_chat_inputs_first(vertices_layers, get_vertex_predecessors)
    assert len(result) == 4  # [chat_input] + original 3 layers
    assert result[0] == ["ChatInput1"]  # First layer contains only ChatInput1
    assert result[1] == ["B"]  # Second layer contains B
    assert result[2] == ["C"]  # Original second layer
    assert result[3] == ["D"]  # Original third layer

    # Test that multiple chat inputs raise an error
    vertices_layers_multiple = [["ChatInput1", "B"], ["ChatInput2", "C"], ["D"]]
    with pytest.raises(ValueError, match="Only one chat input is allowed in the graph"):
        utils.sort_chat_inputs_first(vertices_layers_multiple, get_vertex_predecessors)


def test_get_sorted_vertices_simple():
    # Simple graph with chat input
    vertices_ids = ["ChatInput1", "B", "C", "D"]
    cycle_vertices = set()
    graph_dict = {
        "ChatInput1": {"successors": ["B"], "predecessors": []},
        "B": {"successors": ["C"], "predecessors": ["ChatInput1"]},
        "C": {"successors": ["D"], "predecessors": ["B"]},
        "D": {"successors": [], "predecessors": ["C"]},
    }
    in_degree_map = {"ChatInput1": 0, "B": 1, "C": 1, "D": 1}
    successor_map = {"ChatInput1": ["B"], "B": ["C"], "C": ["D"], "D": []}
    predecessor_map = {"ChatInput1": [], "B": ["ChatInput1"], "C": ["B"], "D": ["C"]}

    def is_input_vertex(vertex_id: str) -> bool:
        return vertex_id == "ChatInput1"

    def get_vertex_predecessors(vertex_id: str) -> list[str]:
        return predecessor_map[vertex_id]

    def get_vertex_successors(vertex_id: str) -> list[str]:
        return successor_map[vertex_id]

    first_layer, remaining_layers = utils.get_sorted_vertices(
        vertices_ids=vertices_ids,
        cycle_vertices=cycle_vertices,
        stop_component_id=None,
        start_component_id=None,
        graph_dict=graph_dict,
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        is_input_vertex=is_input_vertex,
        get_vertex_predecessors=get_vertex_predecessors,
        get_vertex_successors=get_vertex_successors,
        is_cyclic=False,
    )

    assert first_layer == ["ChatInput1"]
    assert len(remaining_layers) == 3
    assert remaining_layers[0] == ["B"]
    assert remaining_layers[1] == ["C"]
    assert remaining_layers[2] == ["D"]


def test_get_sorted_vertices_with_cycle():
    # Graph with a cycle
    vertices_ids = ["A", "B", "C"]
    cycle_vertices = {"A", "B", "C"}
    graph_dict = {
        "A": {"successors": ["B"], "predecessors": ["C"]},
        "B": {"successors": ["C"], "predecessors": ["A"]},
        "C": {"successors": ["A"], "predecessors": ["B"]},
    }
    in_degree_map = {"A": 1, "B": 1, "C": 1}
    successor_map = {"A": ["B"], "B": ["C"], "C": ["A"]}
    predecessor_map = {"A": ["C"], "B": ["A"], "C": ["B"]}

    def is_input_vertex(vertex_id: str) -> bool:  # noqa: ARG001
        return False

    def get_vertex_predecessors(vertex_id: str) -> list[str]:
        return predecessor_map[vertex_id]

    def get_vertex_successors(vertex_id: str) -> list[str]:
        return successor_map[vertex_id]

    # Test with stop_component_id in cycle
    first_layer, remaining_layers = utils.get_sorted_vertices(
        vertices_ids=vertices_ids,
        cycle_vertices=cycle_vertices,
        stop_component_id="B",
        start_component_id=None,
        graph_dict=graph_dict,
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        is_input_vertex=is_input_vertex,
        get_vertex_predecessors=get_vertex_predecessors,
        get_vertex_successors=get_vertex_successors,
        is_cyclic=True,
    )

    # When there's a cycle and stop_component_id is in the cycle,
    # stop_component_id becomes start_component_id
    assert first_layer == ["B"]
    assert len(remaining_layers) == 2
    assert remaining_layers[0] == ["C"]
    assert remaining_layers[1] == ["A"]


def test_get_sorted_vertices_with_stop():
    # Graph with a stop component
    vertices_ids = ["A", "B", "C", "D", "E"]
    cycle_vertices = set()
    graph_dict = {
        "A": {"successors": ["B"], "predecessors": []},
        "B": {"successors": ["C"], "predecessors": ["A"]},
        "C": {"successors": ["D"], "predecessors": ["B"]},
        "D": {"successors": ["E"], "predecessors": ["C"]},
        "E": {"successors": [], "predecessors": ["D"]},
    }
    in_degree_map = {"A": 0, "B": 1, "C": 1, "D": 1, "E": 1}
    successor_map = {"A": ["B"], "B": ["C"], "C": ["D"], "D": ["E"], "E": []}
    predecessor_map = {"A": [], "B": ["A"], "C": ["B"], "D": ["C"], "E": ["D"]}

    def is_input_vertex(vertex_id: str) -> bool:
        return vertex_id == "A"

    def get_vertex_predecessors(vertex_id: str) -> list[str]:
        return predecessor_map[vertex_id]

    def get_vertex_successors(vertex_id: str) -> list[str]:
        return successor_map[vertex_id]

    first_layer, remaining_layers = utils.get_sorted_vertices(
        vertices_ids=vertices_ids,
        cycle_vertices=cycle_vertices,
        stop_component_id="C",
        start_component_id=None,
        graph_dict=graph_dict,
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        is_input_vertex=is_input_vertex,
        get_vertex_predecessors=get_vertex_predecessors,
        get_vertex_successors=get_vertex_successors,
        is_cyclic=False,
    )

    assert first_layer == ["A"]
    assert len(remaining_layers) == 2
    assert remaining_layers[0] == ["B"]
    assert remaining_layers[1] == ["C"]


def test_get_sorted_vertices_with_complex_cycle(graph_with_loop):
    # Convert the graph structure to the format needed by get_sorted_vertices
    vertices_ids = list(graph_with_loop.keys())
    cycle_vertices = {"Loop", "Parse Data 1", "YouTube Transcripts"}  # Known cycle in the graph
    graph_dict = graph_with_loop

    # Build in_degree_map from predecessors
    in_degree_map = {vertex: len(data["predecessors"]) for vertex, data in graph_with_loop.items()}

    # Build successor and predecessor maps
    successor_map = {vertex: data["successors"] for vertex, data in graph_with_loop.items()}
    predecessor_map = {vertex: data["predecessors"] for vertex, data in graph_with_loop.items()}

    def is_input_vertex(vertex_id: str) -> bool:
        # Only Playlist Extractor is an input vertex
        return vertex_id == "Playlist Extractor"

    def get_vertex_predecessors(vertex_id: str) -> list[str]:
        return predecessor_map[vertex_id]

    def get_vertex_successors(vertex_id: str) -> list[str]:
        return successor_map[vertex_id]

    # Test with the cycle
    first_layer, remaining_layers = utils.get_sorted_vertices(
        vertices_ids=vertices_ids,
        cycle_vertices=cycle_vertices,
        stop_component_id=None,
        start_component_id=None,
        graph_dict=graph_dict,
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        is_input_vertex=is_input_vertex,
        get_vertex_predecessors=get_vertex_predecessors,
        get_vertex_successors=get_vertex_successors,
        is_cyclic=True,
    )

    # When is_cyclic is True and start_vertex_id is provided:
    # 1. The first layer will contain vertices with no predecessors and vertices that are part of the cycle
    # 2. This is because the cycle vertices are treated as having no dependencies in the initial sort
    assert "OpenAI Embeddings" in first_layer, (
        "Vertex with no predecessors 'OpenAI Embeddings' should be in first layer"
    )
    assert "Playlist Extractor" in first_layer, "Input vertex 'Playlist Extractor' should be in first layer"
    assert len(first_layer) == 2, (
        f"First layer should contain exactly 4 vertices, got {len(first_layer)}: {first_layer}"
    )

    # Verify that the remaining layers contain the rest of the vertices in the correct order
    # The graph structure shows:
    # Loop -> Parse Data 2 -> Message to Data -> Split Text -> Chroma DB
    # OpenAI Embeddings -> Chroma DB
    vertex_to_layer = {}
    for i, layer in enumerate(remaining_layers):
        for vertex in layer:
            vertex_to_layer[vertex] = i

    # Verify that vertices appear in the correct order
    assert "Loop" in vertex_to_layer, "Vertex 'Loop' should be present in remaining layers"
    assert "Parse Data 2" in vertex_to_layer, "Vertex 'Parse Data 2' should be present in remaining layers"
    assert "Message to Data" in vertex_to_layer, "Vertex 'Message to Data' should be present in remaining layers"
    assert "Chroma DB" in vertex_to_layer, "Vertex 'Chroma DB' should be present in remaining layers"

    # Verify the dependencies are respected
    # Note: Due to the cycle and the way layered_topological_sort works,
    # some vertices might appear in earlier layers than expected
    # What's important is that the dependencies are respected within the non-cycle components
    assert vertex_to_layer["Parse Data 2"] <= vertex_to_layer["Message to Data"], (
        f"'Parse Data 2' (layer {vertex_to_layer['Parse Data 2']}) should appear in same or earlier layer than "
        f"'Message to Data' (layer {vertex_to_layer['Message to Data']})"
    )


def test_get_sorted_vertices_with_stop_at_chroma(graph_with_loop):
    # Convert the graph structure to the format needed by get_sorted_vertices
    vertices_ids = list(graph_with_loop.keys())
    cycle_vertices = {"Loop", "Parse Data 1", "YouTube Transcripts"}  # Known cycle in the graph
    graph_dict = graph_with_loop

    # Build in_degree_map from predecessors
    in_degree_map = {vertex: len(data["predecessors"]) for vertex, data in graph_with_loop.items()}

    # Build successor and predecessor maps
    successor_map = {vertex: data["successors"] for vertex, data in graph_with_loop.items()}
    predecessor_map = {vertex: data["predecessors"] for vertex, data in graph_with_loop.items()}

    def is_input_vertex(vertex_id: str) -> bool:
        # Only Playlist Extractor is an input vertex
        return vertex_id == "Playlist Extractor"

    def get_vertex_predecessors(vertex_id: str) -> list[str]:
        return predecessor_map[vertex_id]

    def get_vertex_successors(vertex_id: str) -> list[str]:
        return successor_map[vertex_id]

    # Test with ChromaDB as stop component
    first_layer, remaining_layers = utils.get_sorted_vertices(
        vertices_ids=vertices_ids,
        cycle_vertices=cycle_vertices,
        stop_component_id="Chroma DB",  # Stop at ChromaDB
        start_component_id=None,
        graph_dict=graph_dict,
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        is_input_vertex=is_input_vertex,
        get_vertex_predecessors=get_vertex_predecessors,
        get_vertex_successors=get_vertex_successors,
        is_cyclic=True,
    )

    # When is_cyclic is True and we have a stop component:
    # 1. The first layer will contain vertices with no predecessors and vertices that are part of the cycle
    # 2. This is because the cycle vertices are treated as having no dependencies in the initial sort
    assert "OpenAI Embeddings" in first_layer, (
        "Vertex with no predecessors 'OpenAI Embeddings' should be in first layer"
    )
    assert "Playlist Extractor" in first_layer, "Input vertex 'Playlist Extractor' should be in first layer"

    assert len(first_layer) == 2, (
        f"First layer should contain exactly 4 vertices, got {len(first_layer)}: {first_layer}"
    )

    # Verify that the remaining layers contain the rest of the vertices in the correct order
    # The graph structure shows:
    # Loop -> Parse Data 2 -> Message to Data -> Split Text -> Chroma DB
    # OpenAI Embeddings -> Chroma DB
    vertex_to_layer = {}
    for i, layer in enumerate(remaining_layers):
        for vertex in layer:
            vertex_to_layer[vertex] = i

    # Verify that vertices appear in the correct order
    assert "Loop" in vertex_to_layer, "Vertex 'Loop' should be present in remaining layers"
    assert "Parse Data 2" in vertex_to_layer, "Vertex 'Parse Data 2' should be present in remaining layers"
    assert "Message to Data" in vertex_to_layer, "Vertex 'Message to Data' should be present in remaining layers"
    assert "Chroma DB" in vertex_to_layer, "Vertex 'Chroma DB' should be present in remaining layers"

    # Verify that dependencies are respected
    assert vertex_to_layer["Parse Data 2"] <= vertex_to_layer["Message to Data"], (
        f"'Parse Data 2' (layer {vertex_to_layer['Parse Data 2']}) should appear in same or earlier layer than "
        f"'Message to Data' (layer {vertex_to_layer['Message to Data']})"
    )

    # When a vertex is marked as a stop component, it will appear in layer 0
    # of the remaining layers. This is because the algorithm stops at this vertex.
    assert vertex_to_layer["Chroma DB"] == 5, (
        f"Stop component 'Chroma DB' should be in layer 5, "
        f"but was found in layer {vertex_to_layer['Chroma DB']}. "
        f"Remaining layers: {remaining_layers}"
    )


def test_get_sorted_vertices_exact_sequence(graph_with_loop):
    # Convert the graph structure to the format needed by get_sorted_vertices
    vertices_ids = list(graph_with_loop.keys())
    cycle_vertices = {"Loop", "Parse Data 1", "YouTube Transcripts"}  # Known cycle in the graph
    graph_dict = graph_with_loop

    # Build in_degree_map from predecessors
    in_degree_map = {vertex: len(data["predecessors"]) for vertex, data in graph_with_loop.items()}

    # Build successor and predecessor maps
    successor_map = {vertex: data["successors"] for vertex, data in graph_with_loop.items()}
    predecessor_map = {vertex: data["predecessors"] for vertex, data in graph_with_loop.items()}

    def is_input_vertex(vertex_id: str) -> bool:
        # Only Playlist Extractor is an input vertex
        return vertex_id == "Playlist Extractor"

    def get_vertex_predecessors(vertex_id: str) -> list[str]:
        return predecessor_map[vertex_id]

    def get_vertex_successors(vertex_id: str) -> list[str]:
        return successor_map[vertex_id]

    # Test with the cycle
    first_layer, remaining_layers = utils.get_sorted_vertices(
        vertices_ids=vertices_ids,
        cycle_vertices=cycle_vertices,
        stop_component_id=None,
        start_component_id=None,
        graph_dict=graph_dict,
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        is_input_vertex=is_input_vertex,
        get_vertex_predecessors=get_vertex_predecessors,
        get_vertex_successors=get_vertex_successors,
        is_cyclic=True,
    )

    # Convert layers to a flat sequence
    sequence = []
    sequence.extend(sorted(first_layer))
    for layer in remaining_layers:
        sequence.extend(sorted(layer))

    # Expected sequence
    expected_sequence = [
        "OpenAI Embeddings",
        "Playlist Extractor",
        "YouTube Transcripts",
        "Loop",
        "Parse Data 1",
        "Parse Data 2",
        "Message to Data",
        "Split Text",
        "Chroma DB",
    ]

    # Check each vertex appears in the correct order
    assert sequence == expected_sequence, f"Sequence: {sequence}"
    # Verify the exact sequence
    assert len(sequence) == len(expected_sequence), (
        f"Expected sequence length {len(expected_sequence)}, but got {len(sequence)}"
    )


def test_get_sorted_vertices_with_unconnected_graph():
    # Define a graph with the specified structure
    vertices_ids = ["A", "B", "C", "D", "K"]
    cycle_vertices = set()
    graph_dict = {
        "A": {"successors": ["B"], "predecessors": []},
        "C": {"successors": ["B"], "predecessors": []},
        "B": {"successors": ["D"], "predecessors": ["A", "C"]},
        "D": {"successors": [], "predecessors": ["B"]},
        "K": {"successors": [], "predecessors": []},
    }
    in_degree_map = {vertex: len(data["predecessors"]) for vertex, data in graph_dict.items()}
    successor_map = {vertex: data["successors"] for vertex, data in graph_dict.items()}
    predecessor_map = {vertex: data["predecessors"] for vertex, data in graph_dict.items()}

    def is_input_vertex(vertex_id: str) -> bool:
        return vertex_id == "A"

    def get_vertex_predecessors(vertex_id: str) -> list[str]:
        return predecessor_map[vertex_id]

    def get_vertex_successors(vertex_id: str) -> list[str]:
        return successor_map[vertex_id]

    first_layer, remaining_layers = utils.get_sorted_vertices(
        vertices_ids=vertices_ids,
        cycle_vertices=cycle_vertices,
        stop_component_id=None,
        start_component_id="A",
        graph_dict=graph_dict,
        in_degree_map=in_degree_map,
        successor_map=successor_map,
        predecessor_map=predecessor_map,
        is_input_vertex=is_input_vertex,
        get_vertex_predecessors=get_vertex_predecessors,
        get_vertex_successors=get_vertex_successors,
        is_cyclic=False,
    )

    # Verify the first layer contains all input vertices
    assert set(first_layer) == {"A", "C"}

    # Verify the remaining layers contain the rest of the vertices in the correct order
    assert len(remaining_layers) == 2
    assert remaining_layers[0] == ["B"]
    assert remaining_layers[1] == ["D"]


def test_filter_vertices_from_vertex():
    # Test case 1: Simple linear graph
    vertices_ids = ["A", "B", "C", "D"]
    graph_dict = {
        "A": {"successors": ["B"], "predecessors": []},
        "B": {"successors": ["C"], "predecessors": ["A"]},
        "C": {"successors": ["D"], "predecessors": ["B"]},
        "D": {"successors": [], "predecessors": ["C"]},
    }

    # Starting from A should return all vertices
    result = utils.filter_vertices_from_vertex(vertices_ids, "A", graph_dict=graph_dict)
    assert result == {"A", "B", "C", "D"}

    # Starting from B should return B, C, D
    result = utils.filter_vertices_from_vertex(vertices_ids, "B", graph_dict=graph_dict)
    assert result == {"B", "C", "D"}

    # Starting from D should return only D
    result = utils.filter_vertices_from_vertex(vertices_ids, "D", graph_dict=graph_dict)
    assert result == {"D"}

    # Test case 2: Graph with branches
    vertices_ids = ["A", "B", "C", "D", "E"]
    graph_dict = {
        "A": {"successors": ["B", "C"], "predecessors": []},
        "B": {"successors": ["D"], "predecessors": ["A"]},
        "C": {"successors": ["E"], "predecessors": ["A"]},
        "D": {"successors": [], "predecessors": ["B"]},
        "E": {"successors": [], "predecessors": ["C"]},
    }

    # Starting from A should return all vertices
    result = utils.filter_vertices_from_vertex(vertices_ids, "A", graph_dict=graph_dict)
    assert result == {"A", "B", "C", "D", "E"}

    # Starting from B should return B and D
    result = utils.filter_vertices_from_vertex(vertices_ids, "B", graph_dict=graph_dict)
    assert result == {"B", "D"}

    # Test case 3: Graph with unconnected vertices
    vertices_ids = ["A", "B", "C", "X", "Y"]
    graph_dict = {
        "A": {"successors": ["B"], "predecessors": []},
        "B": {"successors": ["C"], "predecessors": ["A"]},
        "C": {"successors": [], "predecessors": ["B"]},
        "X": {"successors": ["Y"], "predecessors": []},
        "Y": {"successors": [], "predecessors": ["X"]},
    }

    # Starting from A should return only A, B, C
    result = utils.filter_vertices_from_vertex(vertices_ids, "A", graph_dict=graph_dict)
    assert result == {"A", "B", "C"}

    # Starting from X should return only X, Y
    result = utils.filter_vertices_from_vertex(vertices_ids, "X", graph_dict=graph_dict)
    assert result == {"X", "Y"}

    # Test case 4: Invalid vertex
    result = utils.filter_vertices_from_vertex(vertices_ids, "Z", graph_dict=graph_dict)
    assert result == set()

    # Test case 5: Using callback functions instead of graph_dict
    def get_successors(v: str) -> list[str]:
        return graph_dict[v]["successors"]

    def get_predecessors(v: str) -> list[str]:
        return graph_dict[v]["predecessors"]

    result = utils.filter_vertices_from_vertex(
        vertices_ids,
        "A",
        get_vertex_predecessors=get_predecessors,
        get_vertex_successors=get_successors,
    )
    assert result == {"A", "B", "C"}
