"""Canonical authorization action vocabulary."""

from __future__ import annotations

from enum import Enum


class FlowAction(str, Enum):
    """Actions that can be authorized on a flow resource.

    Values are the Casbin ``act`` strings consumed by the enterprise policy
    engine. Subclassing ``str`` lets these be passed wherever a bare string is
    accepted, so callers can migrate incrementally.

    ``MANAGE`` is a strictly higher privilege than ``WRITE``: route handlers
    gate it on PATCH/PUT payloads that touch sensitive administrative fields
    (see :data:`langflow.services.authorization.sensitive_fields.SENSITIVE_FLOW_FIELDS`).
    """

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"
    DEPLOY = "deploy"
    MANAGE = "manage"


class DeploymentAction(str, Enum):
    """Actions that can be authorized on a deployment resource.

    ``MANAGE`` mirrors :attr:`FlowAction.MANAGE`. No deployment field maps to
    it today; the action exists so the enterprise plugin has a stable verb
    to grant when sensitive deployment fields land.
    """

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"
    MANAGE = "manage"


class ProjectAction(str, Enum):
    """Actions that can be authorized on a project (folder) resource.

    Projects are the OSS-side persistent name for the folder model; the
    ``project:`` Casbin object prefix matches the API surface and the
    ``project:{folder_id}`` domain used by ``_resolve_flow_domain``.

    ``MANAGE`` mirrors :attr:`FlowAction.MANAGE`. Gated on PATCH payloads
    that touch governance / hierarchy fields — see
    :data:`langflow.services.authorization.sensitive_fields.SENSITIVE_PROJECT_FIELDS`.
    """

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    MANAGE = "manage"


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
