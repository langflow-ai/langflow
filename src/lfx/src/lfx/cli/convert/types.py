"""Data types for JSON to Python flow conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeInfo:
    """Parsed node information from a Langflow JSON flow."""

    node_id: str
    node_type: str
    display_name: str
    var_name: str
    config: dict[str, Any] = field(default_factory=dict)
    has_custom_code: bool = False
    custom_code: str | None = None


@dataclass
class EdgeInfo:
    """Parsed edge information representing a connection between nodes."""

    source_id: str
    source_output: str  # Output name from JSON (e.g., "message")
    source_method: str  # Method name to call (e.g., "message_response")
    target_id: str
    target_input: str


@dataclass
class FlowInfo:
    """Complete parsed flow information."""

    name: str
    description: str
    nodes: list[NodeInfo] = field(default_factory=list)
    edges: list[EdgeInfo] = field(default_factory=list)
    prompts: dict[str, str] = field(default_factory=dict)
