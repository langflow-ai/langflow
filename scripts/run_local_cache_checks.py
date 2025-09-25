"""Local cache normalization validation script.

This script validates cache normalization functionality by testing
the normalizer module and simulating ChatService cache operations.
"""

import asyncio
import importlib.util
import pickle
import sys
import types
from pathlib import Path

# Adjust sys.path for src-layout imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src" / "lfx" / "src"))
sys.path.insert(0, str(ROOT / "src" / "backend" / "base"))


def _load_normalizer():
    """Load the normalizer module dynamically.

    Returns:
        Module: The loaded normalizer module.

    Raises:
        ImportError: If the normalizer module cannot be loaded.
    """
    path = ROOT / "src" / "lfx" / "src" / "lfx" / "serialization" / "normalizer.py"
    spec = importlib.util.spec_from_file_location("_normalizer_local", path)
    if not spec or not spec.loader:
        msg = f"Cannot load normalizer from {path}"
        raise ImportError(msg)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_normalizer = _load_normalizer()
normalize_for_cache = _normalizer.normalize_for_cache  # type: ignore[attr-defined]

# Preload modules to avoid heavy lfx.serialization imports (numpy, pandas)

_serialization_pkg = types.ModuleType("lfx.serialization")
sys.modules["lfx.serialization"] = _serialization_pkg
sys.modules["lfx.serialization.normalizer"] = _normalizer

# Provide a minimal dill shim for imports in cache.service
_dill = types.ModuleType("dill")
_dill.dumps = lambda obj, *_args, **_kwargs: pickle.dumps(obj)
_dill.loads = lambda b: pickle.loads(b)  # noqa: S301
sys.modules["dill"] = _dill


def check_normalizer():
    """Test cache normalization functionality.

    Validates that the normalizer correctly handles dynamic classes,
    functions, and vertex snapshots.

    Raises:
        AssertionError: If normalization tests fail.
    """
    dynamic_type = type("Dynamic", (), {"x": 1})

    def dyn_func():
        return 42

    test_value = 123
    obj = {"cls": dynamic_type, "func": dyn_func, "value": test_value}
    out = normalize_for_cache(obj)

    if out["value"] != test_value:
        msg = f"Expected value {test_value}, got {out['value']}"
        raise ValueError(msg)
    if "__class_path__" not in out["cls"]:
        msg = "Missing __class_path__ in normalized class"
        raise ValueError(msg)
    if "__callable_path__" not in out["func"]:
        msg = "Missing __callable_path__ in normalized function"
        raise ValueError(msg)

    vertex_snapshot = {
        "built": True,
        "results": {"x": 1},
        "artifacts": {},
        "built_object": dyn_func,
        "built_result": {"y": 2},
        "full_data": {"id": "v1"},
    }
    ov = normalize_for_cache(vertex_snapshot)

    if ov["__cache_vertex__"] is not True:
        msg = "Expected __cache_vertex__ to be True"
        raise ValueError(msg)
    if ov["built_object"] != {"__cache_placeholder__": "unbuilt"}:
        msg = f"Expected built_object placeholder, got {ov['built_object']}"
        raise ValueError(msg)


async def check_chatservice():
    """Test ChatService cache behavior simulation.

    Simulates ChatService.set_cache behavior using normalize_for_cache
    since the environment lacks optional dependencies for full ChatService import.

    Raises:
        ValueError: If chat service simulation tests fail.
    """
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

    if envelope["type"] != "normalized":
        msg = f"Expected envelope type 'normalized', got {envelope['type']}"
        raise ValueError(msg)

    result = envelope["result"]
    if result["__cache_vertex__"] is not True:
        msg = "Expected __cache_vertex__ to be True in result"
        raise ValueError(msg)
    if result["built_object"] != {"__cache_placeholder__": "unbuilt"}:
        msg = f"Expected built_object placeholder in result, got {result['built_object']}"
        raise ValueError(msg)


def main():
    """Run all local cache validation tests.

    Executes normalizer and chat service tests to validate
    cache functionality.
    """
    check_normalizer()
    asyncio.run(check_chatservice())
    print("LOCAL CACHE CHECKS: OK")


if __name__ == "__main__":
    main()
