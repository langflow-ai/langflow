"""Agentics components for Langflow - LLM-powered data transformation and generation.

This module provides components that leverage the Agentics framework for:
- Semantic data transformation (aMap)
- Data aggregation and summarization (aReduce)
- Synthetic data generation (aGenerate)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .agenerate_component import AgenerateComponent
    from .amap_component import AMapComponent
    from .areduce_component import AreduceComponent

_dynamic_imports = {
    "AgenerateComponent": "agenerate_component",
    "AMapComponent": "amap_component",
    "AreduceComponent": "areduce_component",
}

__all__ = [
    "AMapComponent",
    "AgenerateComponent",
    "AreduceComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import agentics components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
