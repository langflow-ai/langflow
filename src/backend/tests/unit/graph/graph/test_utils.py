import pytest

from langflow.graph.graph import utils


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


def test_get_successors_a(graph):
    vertex_id = "A"

    result = utils.get_successors(graph, vertex_id)

    assert set(result) == {"A", "B", "D", "E", "F", "H", "G"}


def test_get_successors_z(graph):
    vertex_id = "Z"

    result = utils.get_successors(graph, vertex_id)

    assert set(result) == {"Z"}


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

    with pytest.raises(ValueError):
        utils.sort_up_to_vertex(graph, vertex_id)
