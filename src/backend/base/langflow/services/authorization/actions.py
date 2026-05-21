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


class ProjectAction(str, Enum):
    """Actions that can be authorized on a project (folder) resource.

    Projects are the OSS-side persistent name for the folder model; the
    ``project:`` Casbin object prefix matches the API surface and the
    ``project:{folder_id}`` domain used by ``_resolve_flow_domain``.
    """

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"


class KnowledgeBaseAction(str, Enum):
    """Actions that can be authorized on a knowledge base resource.

    Knowledge bases are name-keyed (``knowledge_base:{kb_name}``) rather than
    UUID-keyed, but the action vocabulary mirrors other resources. ``ingest``
    is a distinct verb because ingesting documents has a different cost and
    permission posture than ordinary writes.
    """

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    INGEST = "ingest"


class VariableAction(str, Enum):
    """Actions that can be authorized on a variable resource."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"


class FileAction(str, Enum):
    """Actions that can be authorized on a user-file resource (v2 files)."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"


class ShareAction(str, Enum):
    """Actions that can be authorized on an authz_share row itself.

    Shares are themselves authorizable: creating a share grants someone access
    to a resource you own, so the action vocabulary lives in a dedicated enum
    so audit rows can distinguish ``share:create`` from ``flow:create``.
    """

    READ = "read"
    CREATE = "create"
    DELETE = "delete"
    UPDATE = "update"
