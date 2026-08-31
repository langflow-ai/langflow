"""Compatibility guards for Pydantic models shipped by the MCP SDK."""

from __future__ import annotations

from typing import Any


def _ensure_fastmcp_settings_model_ready(settings_model: Any, fastmcp_type: type[Any]) -> None:
    """Rebuild an unresolved FastMCP Settings model with its local forward reference."""
    if getattr(settings_model, "__pydantic_complete__", True):
        return
    settings_model.model_rebuild(_types_namespace={"FastMCP": fastmcp_type})


def ensure_fastmcp_settings_ready() -> None:
    """Make the installed MCP SDK's Settings model safe to instantiate.

    Some supported MCP/Pydantic combinations leave the ``FastMCP`` forward
    reference unresolved. FastMCP constructs ``Settings`` in ``__init__``, so
    rebuild only when Pydantic reports that the model is incomplete.
    """
    from mcp.server.fastmcp import FastMCP
    from mcp.server.fastmcp.server import Settings

    _ensure_fastmcp_settings_model_ready(Settings, FastMCP)
