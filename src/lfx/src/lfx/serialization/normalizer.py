from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

try:
    from pydantic import BaseModel  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment]


def normalize_for_cache(obj: Any) -> Any:
    """Normalize arbitrary Python objects into cache-safe DTOs.

    - Avoids storing executable objects (classes/functions/generators) by replacing
      them with small descriptors.
    - Pydantic models are converted via `.model_dump()`.
    - Vertex-like dicts get a placeholder for `built_object` and a marker `__cache_vertex__`.
    - Recurses into dict/list/tuple/set with cycle protection.
    - Falls back to a repr descriptor when encountering unknown complex objects.
    """
    visited: set[int] = set()

    def _is_primitive(v: Any) -> bool:
        return isinstance(v, (str, int, float, bool, type(None), bytes, bytearray))

    def _normalize(value: Any) -> Any:
        vid = id(value)
        if vid in visited:
            return {"__cycle__": True}
        visited.add(vid)

        # Primitives
        if _is_primitive(value):
            return value

        # Pydantic models
        if BaseModel is not None and isinstance(value, BaseModel):  # type: ignore[arg-type]
            try:
                return value.model_dump()
            except (AttributeError, TypeError, ValueError):
                return dict(getattr(value, "__dict__", {}))

        # Classes
        if isinstance(value, type):
            mod = getattr(value, "__module__", "")
            name = getattr(value, "__name__", "")
            return {"__class_path__": f"{mod}.{name}"}

        # Functions/methods/builtins
        try:
            import inspect

            if inspect.isfunction(value) or inspect.ismethod(value) or inspect.isbuiltin(value):
                mod = getattr(value, "__module__", "")
                name = getattr(value, "__qualname__", getattr(value, "__name__", ""))
                return {"__callable_path__": f"{mod}.{name}"}
        except (AttributeError, ImportError):
            pass

        # Generators/iterators (non-cacheable)
        if isinstance(value, (Iterator, AsyncIterator)):
            return {"__non_cacheable__": "generator"}

        # Dict-like
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            # Treat vertex snapshots specially if recognizable
            is_vertex_like = "built" in value and "results" in value
            for k, v in value.items():
                if k == "built_object":
                    # Never store executable object in cache
                    out[k] = {"__cache_placeholder__": "unbuilt"}
                else:
                    out[k] = _normalize(v)
            if is_vertex_like:
                out["__cache_vertex__"] = True
            return out

        # Sequences
        if isinstance(value, (list, tuple, set)):
            seq = [_normalize(v) for v in value]
            if isinstance(value, tuple):
                return tuple(seq)
            if isinstance(value, set):
                return list(seq)
            return seq

        # Fallback: dynamic/custom instances or unknown complex objects
        cls = value.__class__
        mod = getattr(cls, "__module__", "")
        qual = getattr(cls, "__qualname__", getattr(cls, "__name__", ""))
        if mod.startswith("lfx.custom") or "<locals>" in qual or mod in ("__main__", "builtins"):
            try:
                return {"__repr__": repr(value)}
            except (AttributeError, TypeError, ValueError):
                return {"__class__": f"{mod}.{qual}"}

        # Last resort: shallow repr descriptor
        try:
            return {"__repr__": repr(value)}
        except (AttributeError, TypeError, ValueError):
            return {"__class__": f"{mod}.{qual}"}

    return _normalize(obj)
