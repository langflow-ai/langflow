"""Canonical authorization action vocabulary."""

from __future__ import annotations

from enum import Enum


class FlowAction(str, Enum):
    """Actions authorized on a flow resource."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"
    DEPLOY = "deploy"


class DeploymentAction(str, Enum):
    """Actions authorized on a deployment resource."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"


class ProjectAction(str, Enum):
    """Actions authorized on a project (folder) resource."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"


class KnowledgeBaseAction(str, Enum):
    """Actions authorized on a knowledge base resource."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    INGEST = "ingest"


class VariableAction(str, Enum):
    """Actions authorized on a variable resource."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"


class FileAction(str, Enum):
    """Actions authorized on a user-file resource (v2 files)."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"


class ShareAction(str, Enum):
    """Actions authorized on an authz_share row."""

    READ = "read"
    CREATE = "create"
    DELETE = "delete"
    UPDATE = "update"
