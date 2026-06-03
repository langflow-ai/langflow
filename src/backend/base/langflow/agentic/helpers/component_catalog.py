"""Component catalog builder for flow generation LLM prompts.

Condenses the live Langflow component registry into a compact, token-efficient
summary suitable for use in LLM prompts. The catalog is registry-aware:
any custom components registered via LANGFLOW_COMPONENTS_PATH will automatically
appear in the catalog with no code changes.
"""

from __future__ import annotations

from typing import Any

# Common flow patterns to show in the catalog preamble
COMMON_PATTERNS = """\
## Common Flow Patterns (compact format examples)

### Simple Chatbot
{"nodes": [{"id": "n1", "type": "ChatInput"}, {"id": "n2", "type": "OpenAIModel", "values": {"model_name": "gpt-4o"}}, {"id": "n3", "type": "ChatOutput"}], "edges": [{"source": "n1", "source_output": "message", "target": "n2", "target_input": "input_value"}, {"source": "n2", "source_output": "text_output", "target": "n3", "target_input": "input_value"}]}

### RAG Pipeline (Retrieval-Augmented Generation)
{"nodes": [{"id": "n1", "type": "ChatInput"}, {"id": "n2", "type": "Milvus", "values": {"collection_name": "docs"}}, {"id": "n3", "type": "OpenAIModel"}, {"id": "n4", "type": "ChatOutput"}], "edges": [{"source": "n1", "source_output": "message", "target": "n2", "target_input": "search_query"}, {"source": "n2", "source_output": "search_results", "target": "n3", "target_input": "context"}, {"source": "n1", "source_output": "message", "target": "n3", "target_input": "input_value"}, {"source": "n3", "source_output": "text_output", "target": "n4", "target_input": "input_value"}]}

### Text Processing Pipeline
{"nodes": [{"id": "n1", "type": "TextInput"}, {"id": "n2", "type": "Prompt", "values": {"template": "Summarize: {input}"}}, {"id": "n3", "type": "OpenAIModel"}, {"id": "n4", "type": "TextOutput"}], "edges": [{"source": "n1", "source_output": "text", "target": "n2", "target_input": "input"}, {"source": "n2", "source_output": "prompt", "target": "n3", "target_input": "input_value"}, {"source": "n3", "source_output": "text_output", "target": "n4", "target_input": "input_value"}]}
"""


def _get_visible_inputs(template: dict[str, Any], max_inputs: int = 8) -> list[tuple[str, str]]:
    """Extract non-advanced, visible input fields from a component template."""
    inputs = []
    for field_name, field_data in template.items():
        if not isinstance(field_data, dict):
            continue
        # Skip hidden, advanced, or special fields
        if field_data.get("advanced", False):
            continue
        if not field_data.get("show", True):
            continue
        if field_name.startswith("_"):
            continue
        field_type = field_data.get("type", "str")
        inputs.append((field_name, field_type))
        if len(inputs) >= max_inputs:
            break
    return inputs


def _get_output_names(outputs: list[dict[str, Any]]) -> list[str]:
    """Extract output names from a component's outputs list."""
    return [o.get("name", "") for o in outputs if isinstance(o, dict) and o.get("name")]


def _truncate_description(description: str, max_chars: int = 80) -> str:
    """Take the first sentence, capped at max_chars."""
    if not description:
        return ""
    # Take up to the first period/newline
    for sep in (".", "\n"):
        idx = description.find(sep)
        if 0 < idx < max_chars:
            return description[: idx + 1].strip()
    return description[:max_chars].strip()


def _format_component_line(display_name: str, comp_data: dict[str, Any]) -> str:
    """Format a single component as a compact catalog line."""
    description = _truncate_description(comp_data.get("description", ""))
    template = comp_data.get("template", {})
    outputs = comp_data.get("outputs", [])

    inputs = _get_visible_inputs(template)
    output_names = _get_output_names(outputs)

    parts = [f"- {display_name}"]
    if description:
        parts.append(f": {description}")

    if inputs:
        input_str = ", ".join(f"{name}({typ})" for name, typ in inputs)
        parts.append(f" | Inputs: {input_str}")

    if output_names:
        parts.append(f" | Outputs: {', '.join(output_names)}")

    return "".join(parts)


async def build_component_catalog_prompt(
    include_categories: list[str] | None = None,
    exclude_categories: list[str] | None = None,
    settings_service: Any | None = None,
) -> str:
    """Build a compact component catalog string for LLM prompts.

    Condenses the live Langflow component registry (~100K+ tokens) into a
    ~3-5K token summary. Categories and components are derived from the live
    registry, so custom components (e.g., CosmosAI components) appear
    automatically when registered.

    Args:
        include_categories: If set, only include these categories.
        exclude_categories: Categories to skip entirely.
        settings_service: Settings service for registry access. Auto-detected if None.

    Returns:
        A formatted string listing all components grouped by category,
        prefixed with common flow patterns.
    """
    from lfx.interface.components import get_and_cache_all_types_dict

    if settings_service is None:
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    all_types_dict = await get_and_cache_all_types_dict(settings_service)

    exclude_set = set(exclude_categories or [])
    include_set = set(include_categories or [])

    lines: list[str] = [COMMON_PATTERNS, "## Available Components by Category\n"]

    for category, components in sorted(all_types_dict.items()):
        if not isinstance(components, dict) or not components:
            continue
        if exclude_set and category in exclude_set:
            continue
        if include_set and category not in include_set:
            continue

        # Collect component lines for this category
        comp_lines = []
        for comp_name, comp_data in components.items():
            if not isinstance(comp_data, dict):
                continue
            display_name = comp_data.get("display_name", comp_name)
            comp_lines.append(_format_component_line(display_name, comp_data))

        if not comp_lines:
            continue

        # Format category header (title-case, replace underscores)
        category_title = category.replace("_", " ").title()
        lines.append(f"### {category_title}")
        lines.extend(comp_lines)
        lines.append("")  # blank line between categories

    return "\n".join(lines)


async def get_all_types_dict(settings_service: Any | None = None) -> dict[str, Any]:
    """Get the full component registry dict (cached).

    Convenience wrapper used by flow_generation_service and flow_validation
    to share the same registry call.
    """
    from lfx.interface.components import get_and_cache_all_types_dict

    if settings_service is None:
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    return await get_and_cache_all_types_dict(settings_service)
