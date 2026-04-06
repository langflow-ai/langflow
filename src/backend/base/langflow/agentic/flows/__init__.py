"""Langflow Agentic Flows.

This package contains flow definitions for the Langflow Assistant feature.

Available flows:
- translation_flow: Intent classification and translation flow (Python)
- LangflowAssistant.json: Main assistant flow for Q&A and component generation (JSON)
"""

from langflow.agentic.flows.translation_flow import get_graph as get_translation_flow_graph

__all__ = [
    "get_translation_flow_graph",
]
