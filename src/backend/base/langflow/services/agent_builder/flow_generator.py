"""Dynamic flow JSON generation from agent configuration.

Builds a complete Langflow flow dict (ChatInput -> Agent -> ChatOutput + tool nodes)
that can be loaded via aload_flow_from_json().
"""

import copy
import importlib
import inspect
import json
import pkgutil
import secrets
import string

from langflow.services.agent_builder.flow_constants import (
    AGENT_TEMPLATE,
    AGENT_TYPE,
    CHAT_INPUT_TEMPLATE,
    CHAT_INPUT_TYPE,
    CHAT_OUTPUT_TEMPLATE,
    CHAT_OUTPUT_TYPE,
    TOOL_OUTPUT,
)

# Mapping of core node types to their Python module paths.
_CORE_MODULE_MAP: dict[str, str] = {
    "ChatInput": "lfx.components.input_output.chat",
    "Agent": "lfx.components.models_and_agents.agent",
    "ChatOutput": "lfx.components.input_output.chat_output",
}

# Module-level cache: component_type → source code string.
_source_cache: dict[str, str] = {}

NODE_ID_SUFFIX_LENGTH = 5
NODE_ID_CHARS = string.ascii_letters + string.digits

_CHAT_INPUT_OUTPUT = {
    "display_name": "Chat Message",
    "method": "message_response",
    "name": "message",
    "selected": "Message",
    "types": ["Message"],
}

_AGENT_OUTPUT = {
    "display_name": "Response",
    "method": "message_response",
    "name": "response",
    "selected": "Message",
    "types": ["Message"],
}

_CHAT_OUTPUT_OUTPUT = {
    "display_name": "Output Message",
    "method": "message_response",
    "name": "message",
    "selected": "Message",
    "types": ["Message"],
}

_CHAT_OUTPUT_INPUT_TYPES = ["Data", "DataFrame", "Message"]


def _get_component_source(component_type: str) -> str | None:
    """Resolve the Python module source code for a component type.

    Returns the source string, or None if the component cannot be found.
    Results are cached in ``_source_cache`` for the process lifetime.
    """
    if component_type in _source_cache:
        return _source_cache[component_type]

    # Fast path: core components with known module paths.
    module_path = _CORE_MODULE_MAP.get(component_type)
    if module_path:
        module = importlib.import_module(module_path)
        source = inspect.getsource(module)
        _source_cache[component_type] = source
        return source

    # Slow path: discover tool/other components by scanning lfx.components.
    source = _discover_component_source(component_type)
    if source is not None:
        _source_cache[component_type] = source
    return source


def _discover_component_source(class_name: str) -> str | None:
    """Scan ``lfx.components`` subpackages to find source for *class_name*."""
    import lfx.components

    # onerror callback prevents walk_packages from propagating ImportErrors
    # raised by subpackage __init__.py files (e.g. optional dependencies).
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        lfx.components.__path__, prefix="lfx.components.", onerror=lambda _name: None
    ):
        try:
            module = importlib.import_module(modname)
        except Exception:  # noqa: BLE001, S112
            continue
        for name, _obj in inspect.getmembers(module, inspect.isclass):
            if name == class_name:
                return inspect.getsource(module)
    return None


def _build_code_field(source: str) -> dict:
    """Build the ``code`` template field required by ``instantiate_class``."""
    return {
        "type": "code",
        "value": source,
        "advanced": True,
        "dynamic": True,
        "required": True,
        "show": True,
        "name": "code",
        "multiline": True,
        "password": False,
        "placeholder": "",
    }


def _pick_tool_output(registry_outputs: list[dict] | None) -> str:
    """Choose the best output to connect to the Agent's tools input.

    LCToolComponent subclasses have ``api_build_tool`` which returns
    properly-named Tool objects (e.g. "calculator", "tavily_search").
    Regular components use ``component_as_tool`` (to_toolkit) which
    derives names from output methods and works when there's only one
    component of each type.
    """
    if registry_outputs:
        for out in registry_outputs:
            if out.get("name") == "api_build_tool":
                return "api_build_tool"
    return "component_as_tool"


def generate_agent_flow(
    system_prompt: str,
    tool_class_names: list[str],
    tool_codes: dict[str, str] | None = None,
    tool_outputs: dict[str, list[dict]] | None = None,
) -> dict:
    """Build a complete flow dict from agent configuration.

    The returned dict is compatible with aload_flow_from_json().
    Model injection is handled separately via inject_model_into_flow().

    Args:
        system_prompt: The agent's system prompt.
        tool_class_names: List of tool component registry keys.
        tool_codes: Optional mapping of tool registry key → Python source code.
            When provided, these are used directly instead of source discovery.
        tool_outputs: Optional mapping of tool registry key → list of output dicts
            from the component registry.  Includes proper ``types`` so that
            ``_should_skip_output`` can filter correctly, preventing duplicate
            tool names sent to the LLM.
    """
    chat_input_id = _generate_node_id(CHAT_INPUT_TYPE)
    agent_id = _generate_node_id(AGENT_TYPE)
    chat_output_id = _generate_node_id(CHAT_OUTPUT_TYPE)

    agent_template = copy.deepcopy(AGENT_TEMPLATE)
    agent_template["system_prompt"]["value"] = system_prompt

    nodes = [
        _build_chat_input_node(chat_input_id),
        _build_agent_node(agent_id, agent_template),
        _build_chat_output_node(chat_output_id),
    ]

    edges = [
        _build_edge(
            chat_input_id,
            CHAT_INPUT_TYPE,
            "message",
            ["Message"],
            agent_id,
            "input_value",
            ["Message"],
            "str",
        ),
        _build_edge(
            agent_id,
            AGENT_TYPE,
            "response",
            ["Message"],
            chat_output_id,
            "input_value",
            _CHAT_OUTPUT_INPUT_TYPES,
            "other",
        ),
    ]

    resolved_tool_codes = tool_codes or {}
    resolved_tool_outputs = tool_outputs or {}
    # Deduplicate tool names to avoid "Tool names must be unique" API errors.
    seen_tools: set[str] = set()
    for class_name in tool_class_names:
        if class_name in seen_tools:
            continue
        seen_tools.add(class_name)
        tool_id = _generate_node_id(class_name)
        tool_code = resolved_tool_codes.get(class_name)
        comp_outputs = resolved_tool_outputs.get(class_name)
        nodes.append(_build_tool_node(tool_id, class_name, tool_code, comp_outputs))

        # LCToolComponent types (CalculatorTool, TavilyAISearch, etc.) have an
        # api_build_tool output whose build_tool() returns a properly-named Tool.
        # Using component_as_tool (to_toolkit) on these produces generic names
        # like "run_model" that collide across components.
        source_output = _pick_tool_output(comp_outputs)
        edges.append(
            _build_edge(
                tool_id,
                class_name,
                source_output,
                ["Tool"],
                agent_id,
                "tools",
                ["Tool"],
                "other",
            )
        )

    return {
        "data": {
            "edges": edges,
            "nodes": nodes,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
        "is_component": False,
    }


def _generate_node_id(node_type: str) -> str:
    """Generate a unique node ID in Langflow format: {Type}-{5charRandom}."""
    suffix = "".join(secrets.choice(NODE_ID_CHARS) for _ in range(NODE_ID_SUFFIX_LENGTH))
    return f"{node_type}-{suffix}"


def _build_chat_input_node(node_id: str) -> dict:
    """Build a minimized ChatInput node."""
    template = copy.deepcopy(CHAT_INPUT_TEMPLATE)
    source = _get_component_source(CHAT_INPUT_TYPE)
    if source:
        template["code"] = _build_code_field(source)
    return _build_node_wrapper(
        node_id=node_id,
        node_type=CHAT_INPUT_TYPE,
        display_name="Chat Input",
        template=template,
        outputs=[_CHAT_INPUT_OUTPUT],
        show_node=False,
        selected_output="message",
    )


def _build_agent_node(node_id: str, template: dict) -> dict:
    """Build the main Agent node."""
    source = _get_component_source(AGENT_TYPE)
    if source:
        template["code"] = _build_code_field(source)
    return _build_node_wrapper(
        node_id=node_id,
        node_type=AGENT_TYPE,
        display_name="Agent",
        template=template,
        outputs=[_AGENT_OUTPUT],
        show_node=True,
        selected_output="response",
    )


def _build_chat_output_node(node_id: str) -> dict:
    """Build a minimized ChatOutput node."""
    template = copy.deepcopy(CHAT_OUTPUT_TEMPLATE)
    source = _get_component_source(CHAT_OUTPUT_TYPE)
    if source:
        template["code"] = _build_code_field(source)
    return _build_node_wrapper(
        node_id=node_id,
        node_type=CHAT_OUTPUT_TYPE,
        display_name="Chat Output",
        template=template,
        outputs=[_CHAT_OUTPUT_OUTPUT],
        show_node=False,
        selected_output="message",
    )


def _build_tool_node(
    node_id: str,
    class_name: str,
    code_source: str | None = None,
    registry_outputs: list[dict] | None = None,
) -> dict:
    """Build a tool component node.

    When *registry_outputs* is provided (from the component registry), the
    node includes the component's real outputs with proper ``types``.
    For LCToolComponent types, the selected output is ``api_build_tool``
    which produces properly-named Tool objects.
    """
    template: dict = {
        "_type": "Component",
        "tools_metadata": {"_input_type": "ToolsInput", "type": "tools", "value": []},
    }
    # Prefer pre-resolved code (from registry), fall back to source discovery.
    source = code_source or _get_component_source(class_name)
    if source:
        template["code"] = _build_code_field(source)

    # Build output list from registry outputs if available.
    selected_output = _pick_tool_output(registry_outputs)
    node_outputs: list[dict] = []
    if registry_outputs:
        node_outputs.extend(copy.deepcopy(out) for out in registry_outputs)
    # Always ensure component_as_tool output is present (fallback).
    has_tool_output = any(o.get("name") == "component_as_tool" for o in node_outputs)
    if not has_tool_output:
        node_outputs.append(copy.deepcopy(TOOL_OUTPUT))

    return _build_node_wrapper(
        node_id=node_id,
        node_type=class_name,
        display_name=class_name,
        template=template,
        outputs=node_outputs,
        show_node=True,
        selected_output=selected_output,
        tool_mode=True,
    )


def _build_node_wrapper(
    *,
    node_id: str,
    node_type: str,
    display_name: str,
    template: dict,
    outputs: list[dict],
    show_node: bool,
    selected_output: str,
    tool_mode: bool = False,
) -> dict:
    """Build the common node wrapper structure."""
    node_data: dict = {
        "display_name": display_name,
        "key": node_type,
        "outputs": outputs,
        "template": template,
    }
    if tool_mode:
        node_data["tool_mode"] = True

    return {
        "data": {
            "id": node_id,
            "node": node_data,
            "selected_output": selected_output,
            "showNode": show_node,
            "type": node_type,
        },
        "id": node_id,
        "position": {"x": 0, "y": 0},
        "type": "genericNode",
    }


def _build_edge(
    source_id: str,
    source_type: str,
    source_output: str,
    source_output_types: list[str],
    target_id: str,
    target_field: str,
    target_input_types: list[str],
    target_handle_type: str,
) -> dict:
    """Build an edge connecting two nodes."""
    source_handle = {
        "dataType": source_type,
        "id": source_id,
        "name": source_output,
        "output_types": source_output_types,
    }
    target_handle = {
        "fieldName": target_field,
        "id": target_id,
        "inputTypes": target_input_types,
        "type": target_handle_type,
    }

    source_handle_str = json.dumps(source_handle)
    target_handle_str = json.dumps(target_handle)

    return {
        "data": {
            "sourceHandle": source_handle,
            "targetHandle": target_handle,
        },
        "id": f"reactflow__edge-{source_id}{source_handle_str}-{target_id}{target_handle_str}",
        "source": source_id,
        "sourceHandle": source_handle_str,
        "target": target_id,
        "targetHandle": target_handle_str,
    }
