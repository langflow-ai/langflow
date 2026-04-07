"""Component registry cache — fetches and searches component types.

Loads the full component catalog from /api/v1/all and provides
pure search/describe functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.mcp.client import LangflowClient


async def load_registry(client: LangflowClient) -> dict[str, dict]:
    """Fetch all component templates from the server.

    Returns a flat dict: {component_type: template_dict}.
    Raises RuntimeError if the server returns no components.
    """
    data = await client.get("/all")
    registry: dict[str, dict] = {
        name: comp_data
        for items in data.values()
        if isinstance(items, dict)
        for name, comp_data in items.items()
        if isinstance(comp_data, dict) and "template" in comp_data
    }
    if not registry:
        msg = "Server returned no components — check the server URL and authentication"
        raise RuntimeError(msg)
    return registry


def search_registry(
    registry: dict[str, dict],
    query: str | None = None,
    category: str | None = None,
    output_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search the registry by name/category/output_type. Pure function."""
    results = []
    for name, tmpl in sorted(registry.items()):
        cat = tmpl.get("category", "")
        if category and cat.lower() != category.lower():
            continue
        if query and query.lower() not in name.lower() and query.lower() not in cat.lower():
            continue
        if output_type:
            all_types = [t for o in tmpl.get("outputs", []) for t in o.get("types", [])]
            if output_type not in all_types:
                continue
        results.append(
            {
                "type": name,
                "category": cat,
                "display_name": tmpl.get("display_name", name),
                "description": tmpl.get("description", ""),
            }
        )
    return results


def describe_component(registry: dict[str, dict], component_type: str) -> dict[str, Any]:
    """Describe a component type's inputs, outputs, and fields. Pure function."""
    if component_type not in registry:
        available = ", ".join(sorted(registry.keys())[:20])
        msg = f"Unknown component: {component_type}. Available: {available}..."
        raise ValueError(msg)

    tmpl = registry[component_type]
    outputs = [{"name": o["name"], "types": o.get("types", [])} for o in tmpl.get("outputs", [])]

    # If any output supports tool_mode, add component_as_tool as an available output
    tool_mode_outputs = [o["name"] for o in tmpl.get("outputs", []) if o.get("tool_mode")]
    if tool_mode_outputs:
        uses = ", ".join(tool_mode_outputs)
        outputs.append(
            {
                "name": "component_as_tool",
                "types": ["Tool"],
                "description": f"Wraps this component as a Tool (uses: {uses}). Connect to an Agent's 'tools' input.",
            }
        )
    fields = []
    advanced_fields: list[str] = []
    inputs = []
    for fname, fdata in tmpl.get("template", {}).items():
        if not isinstance(fdata, dict):
            continue
        is_advanced = fdata.get("advanced", False)
        if fdata.get("input_types"):
            if is_advanced:
                advanced_fields.append(fname)
            else:
                inputs.append(
                    {
                        "name": fname,
                        "input_types": fdata["input_types"],
                        "type": fdata.get("type", ""),
                        "required": fdata.get("required", False),
                    }
                )
        elif fdata.get("show", True) and fdata.get("type") and fname != "code":
            if is_advanced:
                advanced_fields.append(fname)
            else:
                field_info: dict[str, Any] = {
                    "name": fname,
                    "type": fdata.get("type", ""),
                }
                if fdata.get("required"):
                    field_info["required"] = True
                fields.append(field_info)

    result: dict[str, Any] = {
        "type": component_type,
        "category": tmpl.get("category", ""),
        "display_name": tmpl.get("display_name", component_type),
        "description": tmpl.get("description", ""),
        "outputs": outputs,
        "inputs": inputs,
    }
    if fields:
        result["fields"] = fields
    if advanced_fields:
        result["advanced_fields"] = sorted(advanced_fields)
    return result
