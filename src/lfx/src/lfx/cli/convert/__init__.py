"""JSON to Python flow conversion module.

This module provides functionality to convert Langflow JSON flow definitions
into Python code that can be version-controlled and maintained as code.

Usage:
    from lfx.cli.convert import convert_command, convert_flow_to_python

    # CLI command (used by typer app)
    convert_command(flow_json=Path("flow.json"), output=Path("flow.py"))

    # Programmatic usage
    python_code = convert_flow_to_python(Path("flow.json"))
"""

from .command import convert_command, convert_flow_to_python
from .types import EdgeInfo, FlowInfo, NodeInfo

__all__ = [
    "EdgeInfo",
    "FlowInfo",
    "NodeInfo",
    "convert_command",
    "convert_flow_to_python",
]
