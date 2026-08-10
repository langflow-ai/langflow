"""Starter-template tools for the flow-builder assistant.

Let the agent instantiate a curated starter project in ONE tool call
instead of a search → describe → build loop. The template's flow JSON is
loaded server-side and pushed through the same ``set_flow`` proposal gate
as ``build_flow`` — it never enters the LLM context; the tool returns only
a compact summary (name, node count, node types).

Decoupled from ``langflow`` via late imports (``lfx`` ships without the
backend), the same pattern as ``RunFlow`` / ``GenerateComponent``.
"""

from __future__ import annotations

import copy
from typing import Any

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema import Data

from ._state import _emit, _ensure_working_flow, emit_tool_start

_DESCRIPTION_PREVIEW_CHARS = 140

_TEMPLATES_UNAVAILABLE = "Starter templates are not available in this environment."


def _load_starter_templates(fields: list[str]) -> list[dict[str, Any]] | None:
    """Return the starter templates via langflow, or None when it isn't installed."""
    try:
        from langflow.agentic.utils.template_search import list_templates as lf_list_templates
    except ImportError:
        return None
    return lf_list_templates(fields=fields)


def _one_line_description(description: str | None) -> str:
    text = (description or "").strip().splitlines()[0] if (description or "").strip() else ""
    if len(text) > _DESCRIPTION_PREVIEW_CHARS:
        text = text[: _DESCRIPTION_PREVIEW_CHARS - 1].rstrip() + "…"
    return text


def _node_types(flow: dict[str, Any]) -> list[str]:
    """Sorted unique component types in a flow dict."""
    nodes = (flow.get("data") or {}).get("nodes") or []
    types = {(node.get("data") or {}).get("type", "") for node in nodes if isinstance(node, dict)}
    return sorted(t for t in types if t)


class ListTemplates(Component):
    display_name = "List Templates"
    description = "List the available starter templates (name + one-line description)."
    icon = "LayoutTemplate"
    name = "ListTemplates"

    inputs = [
        MessageTextInput(
            name="reason",
            display_name="Reason",
            info="Optional short note on why you are listing templates (does not change anything).",
            required=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Templates", method="list_templates"),
    ]

    def list_templates(self) -> Data:
        # Pure read of on-disk JSON metadata — cache per request like the
        # other read tools so repeated planning turns don't re-walk the dir.
        from lfx.mcp.tool_cache import cached_tool_call

        def producer() -> Data:
            templates = _load_starter_templates(fields=["name", "description"])
            if templates is None:
                return Data(data={"error": _TEMPLATES_UNAVAILABLE, "text": _TEMPLATES_UNAVAILABLE})
            entries = [
                {"name": t.get("name", ""), "description": _one_line_description(t.get("description"))}
                for t in templates
                if t.get("name")
            ]
            entries.sort(key=lambda e: e["name"])
            text = "\n".join(f"- {e['name']}: {e['description']}" for e in entries)
            return Data(data={"templates": entries, "count": len(entries), "text": text})

        return cached_tool_call("list_templates", {}, producer)


class UseTemplate(Component):
    display_name = "Use Template"
    description = (
        "Instantiate a starter template by name as the proposed flow (same review gate as "
        "build_flow — the user approves before the canvas changes). Returns a compact "
        "summary, never the flow JSON. Use list_templates to see valid names."
    )
    icon = "LayoutTemplate"
    name = "UseTemplate"

    inputs = [
        MessageTextInput(
            name="template_name",
            display_name="Template Name",
            info="Exact starter template name (case-insensitive), e.g. 'Memory Chatbot'.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="use_template"),
    ]

    def use_template(self) -> Data:
        requested = (self.template_name or "").strip()
        emit_tool_start("use_template", template_name=requested)
        if not requested:
            msg = "template_name is required. Call list_templates to see the available names."
            return Data(data={"error": msg, "text": msg})

        # Same per-request memoization as list_templates — retries and
        # multi-template turns must not re-walk every starter JSON.
        from lfx.mcp.tool_cache import cached_tool_call

        templates = cached_tool_call(
            "load_templates_full",
            {},
            lambda: _load_starter_templates(fields=["name", "description", "data"]),
        )
        if templates is None:
            return Data(data={"error": _TEMPLATES_UNAVAILABLE, "text": _TEMPLATES_UNAVAILABLE})

        wanted = requested.casefold()
        template = next((t for t in templates if (t.get("name") or "").strip().casefold() == wanted), None)
        if template is None:
            available = ", ".join(sorted(t.get("name", "") for t in templates if t.get("name")))
            msg = f"Unknown template {requested!r}. Available templates: {available}"
            logger.warning("use_template: unknown template %r", requested)
            return Data(data={"error": msg, "text": msg})

        # Deep copy so the cached template dict never aliases the working
        # flow, which later tools mutate in place.
        flow_data = copy.deepcopy(template.get("data") or {})
        nodes = flow_data.get("nodes") or []
        if not nodes:
            msg = f"Template {template.get('name')!r} has no components and cannot be instantiated."
            logger.warning("use_template: empty template %r", requested)
            return Data(data={"error": msg, "text": msg})

        flow = {
            "name": template.get("name", requested),
            "description": template.get("description", ""),
            "data": flow_data,
        }
        # Same proposal gate as build_flow: mutate the working flow in place (a
        # ContextVar rebind is invisible to sibling tools), then emit set_flow.
        working = _ensure_working_flow()
        working.clear()
        working.update(flow)
        _emit("set_flow", flow=flow)

        node_types = _node_types(flow)
        edge_count = len(flow_data.get("edges") or [])
        text = (
            f"Template '{flow['name']}' instantiated as the proposed flow "
            f"({len(nodes)} nodes, {edge_count} edges; components: {', '.join(node_types)}). "
            "It is pending the user's review — do not rebuild it."
        )
        return Data(
            data={
                "text": text,
                "template": flow["name"],
                "node_count": len(nodes),
                "edge_count": edge_count,
                "node_types": node_types,
            }
        )
