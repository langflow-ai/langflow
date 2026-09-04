"""The action vocabulary the v2 workflow router asks a host to authorize.

Kept tiny and explicit so the router never passes a raw ``"execute"`` /
``"read"`` string into ``host.authorize`` and risks silent authz drift. The
langflow host maps these to its internal ``FlowAction``; bare ``lfx serve``
ignores them (single-tenant, no-op authorize).
"""

from __future__ import annotations

from enum import Enum


class WorkflowAction(str, Enum):
    """Actions a host authorizes for a resolved flow."""

    EXECUTE = "execute"  # POST /workflows run
    READ = "read"  # status reconstruction / GET
