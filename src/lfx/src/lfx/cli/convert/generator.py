"""Python code generation from parsed flow data.

This module orchestrates code generation by delegating to specialized generators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .helpers import (
    generate_builder_function,
    generate_custom_components,
    generate_get_graph_function,
    generate_global_variables_section,
    generate_header,
    generate_imports,
    generate_main_block,
    generate_prompts,
    generate_unknown_components_warning,
)
from .parsing import _parse_to_snake_case

if TYPE_CHECKING:
    from .types import FlowInfo


def generate_python_code(flow_info: FlowInfo) -> str:
    """Generate Python code from parsed flow info."""
    lines: list[str] = []
    flow_name = _parse_to_snake_case(flow_info.name) or "unnamed_flow"

    generate_header(lines, flow_info)
    generate_imports(lines, flow_info)
    generate_unknown_components_warning(lines, flow_info)
    generate_global_variables_section(lines, flow_info)
    generate_custom_components(lines, flow_info)
    generate_prompts(lines, flow_info)
    generate_builder_function(lines, flow_info, flow_name)
    generate_get_graph_function(lines, flow_name)
    generate_main_block(lines, flow_name)

    return "\n".join(lines)
