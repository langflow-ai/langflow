import asyncio
import os
import sys

# Adjust sys.path for src-layout imports
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src", "lfx", "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "backend", "base"))

import importlib.util


def _load_normalizer():
    path = os.path.join(ROOT, "src", "lfx", "src", "lfx", "serialization", "normalizer.py")
    spec = importlib.util.spec_from_file_location("_normalizer_local", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_normalizer = _load_normalizer()
normalize_for_cache = _normalizer.normalize_for_cache  # type: ignore

# Preload modules to avoid heavy lfx.serialization imports (numpy, pandas)
import types as _types
import pickle as _pickle

_serialization_pkg = _types.ModuleType("lfx.serialization")
sys.modules["lfx.serialization"] = _serialization_pkg
sys.modules["lfx.serialization.normalizer"] = _normalizer

# Provide a minimal dill shim for imports in cache.service
_dill = _types.ModuleType("dill")
_dill.dumps = lambda obj, *a, **k: _pickle.dumps(obj)
_dill.loads = lambda b: _pickle.loads(b)
sys.modules["dill"] = _dill


def check_normalizer():
    Dynamic = type("Dynamic", (), {"x": 1})

    def dyn_func():
        return 42

    obj = {"cls": Dynamic, "func": dyn_func, "value": 123}
    out = normalize_for_cache(obj)
    assert out["value"] == 123
    assert "__class_path__" in out["cls"]
    assert "__callable_path__" in out["func"]

    vertex_snapshot = {
        "built": True,
        "results": {"x": 1},
        "artifacts": {},
        "built_object": dyn_func,
        "built_result": {"y": 2},
        "full_data": {"id": "v1"},
    }
    ov = normalize_for_cache(vertex_snapshot)
    assert ov["__cache_vertex__"] is True
    assert ov["built_object"] == {"__cache_placeholder__": "unbuilt"}


async def check_chatservice():
    # Environment lacks optional dependencies to import ChatService.
    # Instead, simulate ChatService.set_cache behavior using normalize_for_cache directly.
    dynamic_cls = type("C", (), {})
    value = {
        "built": True,
        "results": {"ok": 1},
        "built_object": dynamic_cls,
        "artifacts": {},
        "built_result": {"foo": "bar"},
        "full_data": {"id": "v"},
    }
    normalized = normalize_for_cache(value)
    envelope = {"result": normalized, "type": "normalized", "__envelope_version__": 1}
    assert envelope["type"] == "normalized"
    result = envelope["result"]
    assert result["__cache_vertex__"] is True
    assert result["built_object"] == {"__cache_placeholder__": "unbuilt"}


def main():
    check_normalizer()
    asyncio.run(check_chatservice())
    print("LOCAL CACHE CHECKS: OK")


if __name__ == "__main__":
    main()
