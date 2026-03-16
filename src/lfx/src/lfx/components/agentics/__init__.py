"""Agentics components for Langflow - LLM-powered data transformation and generation.

This module provides components that leverage the Agentics framework for:
- Semantic data transformation (SemanticMap)
- Data aggregation and summarization (SemanticAggregator)
- Synthetic data generation (SyntheticDataGenerator)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .semantic_aggregator import SemanticAggregator
    from .semantic_map import SemanticMap
    from .synthetic_data_generator import SyntheticDataGenerator

_dynamic_imports = {
    "SemanticAggregator": "semantic_aggregator",
    "SemanticMap": "semantic_map",
    "SyntheticDataGenerator": "synthetic_data_generator",
}

__all__ = [
    "SemanticAggregator",
    "SemanticMap",
    "SyntheticDataGenerator",
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
