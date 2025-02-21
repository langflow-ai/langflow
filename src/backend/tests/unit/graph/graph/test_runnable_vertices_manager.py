import pickle
from typing import TYPE_CHECKING

import pytest
from langflow.graph.graph.runnable_vertices_manager import RunnableVerticesManager

if TYPE_CHECKING:
    from collections import defaultdict


@pytest.fixture
def data():
    run_map: defaultdict(list) = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    run_predecessors: defaultdict(set) = {"A": set(), "B": {"A"}, "C": {"A"}, "D": {"B", "C"}}
    vertices_to_run: set = {"A", "B", "C"}
    vertices_being_run = {"A"}
    return {
        "run_map": run_map,
        "run_predecessors": run_predecessors,
        "vertices_to_run": vertices_to_run,
        "vertices_being_run": vertices_being_run,
    }


def test_to_dict(data):
    result = RunnableVerticesManager.from_dict(data).to_dict()

    assert all(key in result for key in data)


def test_from_dict(data):
    result = RunnableVerticesManager.from_dict(data)

    assert isinstance(result, RunnableVerticesManager)


def test_from_dict_without_run_map__bad_case(data):
    data.pop("run_map")

    with pytest.raises(KeyError):
        RunnableVerticesManager.from_dict(data)


def test_from_dict_without_run_predecessors__bad_case(data):
    data.pop("run_predecessors")

    with pytest.raises(KeyError):
        RunnableVerticesManager.from_dict(data)


def test_from_dict_without_vertices_to_run__bad_case(data):
    data.pop("vertices_to_run")

    with pytest.raises(KeyError):
        RunnableVerticesManager.from_dict(data)


def test_from_dict_without_vertices_being_run__bad_case(data):
    data.pop("vertices_being_run")

    with pytest.raises(KeyError):
        RunnableVerticesManager.from_dict(data)


def test_pickle(data):
    manager = RunnableVerticesManager.from_dict(data)

    binary = pickle.dumps(manager)
    result = pickle.loads(binary)  # noqa: S301

    assert result.run_map == manager.run_map
    assert result.run_predecessors == manager.run_predecessors
    assert result.vertices_to_run == manager.vertices_to_run
    assert result.vertices_being_run == manager.vertices_being_run


def test_update_run_state(data):
    manager = RunnableVerticesManager.from_dict(data)
    run_predecessors = {"E": {"D"}}
    vertices_to_run = {"D"}

    manager.update_run_state(run_predecessors, vertices_to_run)

    assert "D" in manager.run_map
    assert "D" in manager.vertices_to_run
    assert "D" in manager.run_predecessors["E"]


def test_is_vertex_runnable(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "A"
    is_active = True
    is_loop = False

    result = manager.is_vertex_runnable(vertex_id, is_active=is_active, is_loop=is_loop)

    assert result is False


def test_is_vertex_runnable__wrong_is_active(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "A"
    is_active = False
    is_loop = False

    result = manager.is_vertex_runnable(vertex_id, is_active=is_active, is_loop=is_loop)

    assert result is False


def test_is_vertex_runnable__wrong_vertices_to_run(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "D"
    is_active = True
    is_loop = False

    result = manager.is_vertex_runnable(vertex_id, is_active=is_active, is_loop=is_loop)

    assert result is False


def test_is_vertex_runnable__wrong_run_predecessors(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "C"
    is_active = True
    is_loop = False

    result = manager.is_vertex_runnable(vertex_id, is_active=is_active, is_loop=is_loop)

    assert result is False


def test_are_all_predecessors_fulfilled(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "A"
    is_loop = False

    result = manager.are_all_predecessors_fulfilled(vertex_id, is_loop=is_loop)

    assert result is True


def test_are_all_predecessors_fulfilled__wrong(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "D"
    is_loop = False

    result = manager.are_all_predecessors_fulfilled(vertex_id, is_loop=is_loop)

    assert result is False


def test_remove_from_predecessors(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "A"

    manager.remove_from_predecessors(vertex_id)

    assert all(vertex_id not in predecessors for predecessors in manager.run_predecessors.values())


def test_build_run_map(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertices_to_run = {}
    predecessor_map = {"Z": set(), "X": {"Z"}, "Y": {"Z"}, "W": {"X", "Y"}}

    manager.build_run_map(predecessor_map, vertices_to_run)

    assert all(v in manager.run_map for v in ["Z", "X", "Y"])
    assert "W" not in manager.run_map


def test_update_vertex_run_state(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "C"
    is_runnable = True

    manager.update_vertex_run_state(vertex_id, is_runnable=is_runnable)

    assert vertex_id in manager.vertices_to_run


def test_update_vertex_run_state__bad_case(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "C"
    is_runnable = False

    manager.update_vertex_run_state(vertex_id, is_runnable=is_runnable)

    assert vertex_id not in manager.vertices_being_run


def test_remove_vertex_from_runnables(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "C"

    manager.remove_vertex_from_runnables(vertex_id)

    assert vertex_id not in manager.vertices_being_run


def test_add_to_vertices_being_run(data):
    manager = RunnableVerticesManager.from_dict(data)
    vertex_id = "C"

    manager.add_to_vertices_being_run(vertex_id)

    assert vertex_id in manager.vertices_being_run
