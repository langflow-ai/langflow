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
        name: {**comp_data, "category": category}
        for category, items in data.items()
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
    *,
    include_legacy: bool = False,
) -> list[dict[str, Any]]:
    """Search the registry by name/category/output_type. Pure function.

    LEGACY components are excluded by default: the agent's discovery path
    must not surface deprecated nodes (screenshot 5: a Legacy Calculator).
    They stay reachable via ``describe_component`` by exact name, and an
    explicit ``include_legacy=True`` opt-in still lists them.

    BETA components ARE included (user decision 2026-05-18): they are
    usable, just newer — only legacy is hidden.
    """
    results = []
    for name, tmpl in sorted(registry.items()):
        if not include_legacy and tmpl.get("legacy"):
            continue
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
    outputs = []
    loop_inputs = []
    for o in tmpl.get("outputs", []):
        entry: dict[str, Any] = {"name": o["name"], "types": o.get("types", [])}
        if o.get("allows_loop"):
            # An allows_loop output doubles as the loop-feedback target (Loop.item):
            # surface it as an input too, or the agent cannot discover loop wiring.
            entry["allows_loop"] = True
            types = o.get("types") or []
            selected = o.get("selected") or (types[0] if types else "Message")
            loop_inputs.append(
                {
                    "name": o["name"],
                    "input_types": [selected, *(o.get("loop_types") or [])],
                    "type": "loop",
                    "required": False,
                    "description": "Loop feedback input: connect the loop body's final output back here.",
                }
            )
        outputs.append(entry)

    # Tool mode = any INPUT field with tool_mode=True (mirrors Component._handle_tool_mode);
    # output-side tool_mode is accepted for backward compat.
    template_fields = tmpl.get("template", {})
    tool_mode_inputs = [
        name for name, fdata in template_fields.items() if isinstance(fdata, dict) and fdata.get("tool_mode")
    ]
    tool_mode_outputs = [o["name"] for o in tmpl.get("outputs", []) if o.get("tool_mode")]
    if tool_mode_inputs or tool_mode_outputs:
        uses = ", ".join(tool_mode_inputs or tool_mode_outputs)
        label = "tool inputs" if tool_mode_inputs else "uses"
        description = f"Wraps this component as a Tool ({label}: {uses}). Connect to an Agent's 'tools' input."
        outputs.append(
            {
                "name": "component_as_tool",
                "types": ["Tool"],
                "description": description,
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

    # Template wins on a name collision (mirrors connect.py's priority):
    # never describe the same port twice.
    template_input_names = {name for name, fdata in template_fields.items() if isinstance(fdata, dict) and fdata}
    loop_inputs = [li for li in loop_inputs if li["name"] not in template_input_names]

    result: dict[str, Any] = {
        "type": component_type,
        "category": tmpl.get("category", ""),
        "display_name": tmpl.get("display_name", component_type),
        "description": tmpl.get("description", ""),
        "outputs": outputs,
        "inputs": [*inputs, *loop_inputs],
    }
    if fields:
        result["fields"] = fields
    if advanced_fields:
        result["advanced_fields"] = sorted(advanced_fields)
    # search_registry hides legacy/beta, but describe-by-exact-name still
    # reaches them — flag so the agent knows what it picked.
    if tmpl.get("legacy"):
        result["legacy"] = True
    if tmpl.get("beta"):
        result["beta"] = True
    return result
