"""Canonical authorization action vocabulary."""

from __future__ import annotations

from enum import Enum


class FlowAction(str, Enum):
    """Actions that can be authorized on a flow resource.

    Values are the Casbin ``act`` strings consumed by the enterprise policy
    engine. Subclassing ``str`` lets these be passed wherever a bare string is
    accepted, so callers can migrate incrementally.
    """

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"
    DEPLOY = "deploy"


class DeploymentAction(str, Enum):
    """Actions that can be authorized on a deployment resource."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"
