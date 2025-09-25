import types
from pydantic import BaseModel, create_model

from lfx.serialization.normalizer import normalize_for_cache


def test_normalize_dynamic_class_and_function():
    # Dynamic class
    Dynamic = type("Dynamic", (), {"x": 1})
    # Dynamic function
    def dyn_func():
        return 42

    obj = {
        "cls": Dynamic,
        "func": dyn_func,
        "value": 123,
    }

    out = normalize_for_cache(obj)
    assert out["value"] == 123
    assert out["cls"].get("__class_path__")
    assert out["func"].get("__callable_path__")


def test_normalize_pydantic_model():
    Model = create_model("X", a=(int, ...))
    m = Model(a=3)
    out = normalize_for_cache(m)
    assert out == {"a": 3}


def test_normalize_vertex_like_dict_replaces_built_object():
    vertex_snapshot = {
        "built": True,
        "results": {"x": 1},
        "artifacts": {},
        "built_object": lambda x: x,  # should never be cached as executable
        "built_result": {"y": 2},
        "full_data": {"id": "v1"},
    }
    out = normalize_for_cache(vertex_snapshot)
    assert out["__cache_vertex__"] is True
    assert out["built"] is True
    assert out["results"] == {"x": 1}
    assert out["artifacts"] == {}
    assert out["built_result"] == {"y": 2}
    assert out["full_data"] == {"id": "v1"}
    assert out["built_object"] == {"__cache_placeholder__": "unbuilt"}

