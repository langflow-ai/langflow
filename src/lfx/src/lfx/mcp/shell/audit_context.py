"""Audit context for shell-MCP log records.

A small immutable carrier for the IDs we want to surface in the
structured logs: ``request_id`` (always present, unique per call) and
``client_id`` (the MCP host's identifier when the transport supplies
one). Kept separate from :class:`ShellServerConfig` because the config
is per-server and frozen at boot, while audit data is per-call.

Builders are provided so callers don't have to know about FastMCP
internals: production code passes a :class:`mcp.server.fastmcp.Context`
to :func:`from_fastmcp_context`; tests can construct
:class:`AuditContext` directly.

V1 KNOWN LIMITATION (PR review #6) — multi-tenant attribution gap:
``client_id`` is the FastMCP *host*'s identifier. Over stdio that is
the langflow process itself, not the langflow user who triggered the
flow. As written, the audit log can attribute a command to a Langflow
deployment but NOT to the human (or service-account) that initiated
the call. A real identity passthrough — Langflow stamping the calling
user into the MCP context, the server reading it from a per-call header
or token — is V2 work. Single-tenant deployments still get useful
forensic value; multi-tenant operators must layer their own attribution
upstream until V2 lands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class AuditContext:
    """Per-call IDs propagated into every structured log entry."""

    request_id: str
    client_id: str | None = None

    def as_log_fields(self) -> Mapping[str, Any]:
        """Render to a kwargs dict suitable for ``logger.info(...)``.

        ``client_id`` is always emitted (possibly as ``None``) so that
        log filters expecting the field to exist behave consistently
        across calls — the absence of a client identity is itself
        information worth recording.
        """
        return {"request_id": self.request_id, "client_id": self.client_id}


def from_fastmcp_context(ctx: object | None) -> AuditContext | None:
    """Build an :class:`AuditContext` from a FastMCP ``Context``.

    Returns ``None`` if ``ctx`` is missing — the handler then logs
    without correlation IDs, which keeps direct ``handle_execute_command``
    callers (tests, future internal uses) working.
    """
    if ctx is None:
        return None
    request_id = getattr(ctx, "request_id", None)
    if not request_id:
        return None
    return AuditContext(
        request_id=str(request_id),
        client_id=getattr(ctx, "client_id", None),
    )
