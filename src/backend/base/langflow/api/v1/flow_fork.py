"""Forking a flow into an independent copy.

When a save is refused because someone else changed the flow, the way out is a
duplicate that carries the author's own work. That duplicate must be inert: it
inherits the graph, and nothing that makes a flow reachable from the outside.

The neutralisation lives here rather than in each client so a caller cannot
forget a field. Duplicating a flow that exposed an endpoint, an MCP tool or a
webhook would otherwise stand up a second live listener nobody asked for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from langflow.services.database.models.flow.model import AccessTypeEnum, FlowCreate

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


class FlowFork(BaseModel):
    """What the caller may choose about a fork. Everything else is inherited or neutralised."""

    name: str | None = Field(default=None, description="Name for the copy; the source name plus a suffix by default")
    data: dict | None = Field(default=None, description="Graph for the copy; the source graph when omitted")


def build_fork_payload(source: Flow, fork: FlowFork) -> FlowCreate:
    """Return the FlowCreate for an inert copy of *source*.

    ``_new_flow`` de-duplicates the name afterwards, so a fork can always be
    created no matter how many copies already exist — the exit offered by the
    conflict banner is the one that must never fail.

    The folder is deliberately not inherited: the copy belongs to whoever forked
    it, and the source may live in a project they cannot write to.
    """
    return FlowCreate(
        name=fork.name or f"{source.name} (copy)",
        description=source.description,
        data=fork.data if fork.data is not None else source.data,
        icon=source.icon,
        icon_bg_color=source.icon_bg_color,
        gradient=source.gradient,
        is_component=source.is_component,
        tags=source.tags,
        flow_type=source.flow_type,
        endpoint_name=None,
        webhook=False,
        mcp_enabled=False,
        locked=False,
        access_type=AccessTypeEnum.PRIVATE,
    )
