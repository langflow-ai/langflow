"""Langflow Agentic Flows.

This package contains flow definitions for the Langflow Assistant feature.

Available flows:
- translation_flow: Intent classification and translation flow (Python)
- flow_builder_assistant: Flow building + sandboxed file I/O (Python). Handles
  both ``build_flow`` and ``manage_files`` intents; the FileSystemTool
  toolkit lets the agent write/edit documentation files when asked.
- LangflowAssistant.json: Main assistant flow for Q&A and component generation (JSON)
"""

from langflow.agentic.flows.flow_builder_assistant import get_graph as get_flow_builder_graph
from langflow.agentic.flows.translation_flow import get_graph as get_translation_flow_graph

__all__ = [
    "get_flow_builder_graph",
    "get_translation_flow_graph",
]
