"""Agentics components for Langflow - LLM-powered data transformation and generation.

This module provides components that leverage the Agentics framework for:
- Semantic data transformation (SemanticMap)
- Data aggregation and summarization (SemanticAggregator)
- Synthetic data generation (SyntheticDataGenerator)
"""

from lfx.components.agentics.constants import ERROR_AGENTICS_NOT_INSTALLED

__all__: list[str] = []

try:
    import crewai  # noqa: F401
    from agentics import AG  # noqa: F401
    from agentics.core.atype import create_pydantic_model  # noqa: F401
except ImportError as e:
    raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

from lfx.components.agentics.semantic_aggregator import SemanticAggregator
from lfx.components.agentics.semantic_map import SemanticMap
from lfx.components.agentics.synthetic_data_generator import SyntheticDataGenerator

__all__ = ["SemanticAggregator", "SemanticMap", "SyntheticDataGenerator"]
