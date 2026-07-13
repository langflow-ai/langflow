"""ORM model aggregate for schema health and metadata registration.

Mirrors ``langflow.services.database.models`` for the symbols DatabaseService
historically accessed via ``models.Flow`` / ``models.User`` / etc. Individual
table definitions remain owned by ``lfx.services.database.models``; this module
only re-exports them so ``SQLModel.metadata`` and schema-health checks see the
same set as before the services extraction.
"""

from __future__ import annotations

from lfx.services.database.models.api_key import ApiKey
from lfx.services.database.models.auth.authz import (
    AuthzAuditLog,
    AuthzEditLock,
    AuthzRole,
    AuthzRoleAssignment,
    AuthzShare,
    AuthzTeam,
    AuthzTeamMember,
    CasbinRule,
)
from lfx.services.database.models.auth.sso import SSOConfig, SSOUserProfile
from lfx.services.database.models.deployment import Deployment
from lfx.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from lfx.services.database.models.file import File
from lfx.services.database.models.flow import Flow
from lfx.services.database.models.flow_version import FlowVersion
from lfx.services.database.models.flow_version_deployment_attachment import FlowVersionDeploymentAttachment
from lfx.services.database.models.folder import Folder
from lfx.services.database.models.ingestion_run import IngestionRun, IngestionRunStatus
from lfx.services.database.models.jobs import Job
from lfx.services.database.models.knowledge_base import KnowledgeBaseRecord, KnowledgeBaseStatus
from lfx.services.database.models.mcp_server import MCPServer
from lfx.services.database.models.memory_base import (
    MemoryBase,
    MemoryBaseSession,
    MemoryBaseWorkflowRun,
    MessageIngestionRecord,
)
from lfx.services.database.models.message import MessageTable
from lfx.services.database.models.traces import SpanTable, TraceTable
from lfx.services.database.models.transactions import TransactionTable
from lfx.services.database.models.user import User
from lfx.services.database.models.variable import Variable
from lfx.services.database.models.vertex_builds import VertexBuildTable

__all__ = [
    "ApiKey",
    "AuthzAuditLog",
    "AuthzEditLock",
    "AuthzRole",
    "AuthzRoleAssignment",
    "AuthzShare",
    "AuthzTeam",
    "AuthzTeamMember",
    "CasbinRule",
    "Deployment",
    "DeploymentProviderAccount",
    "File",
    "Flow",
    "FlowVersion",
    "FlowVersionDeploymentAttachment",
    "Folder",
    "IngestionRun",
    "IngestionRunStatus",
    "Job",
    "KnowledgeBaseRecord",
    "KnowledgeBaseStatus",
    "MCPServer",
    "MemoryBase",
    "MemoryBaseSession",
    "MemoryBaseWorkflowRun",
    "MessageIngestionRecord",
    "MessageTable",
    "SSOConfig",
    "SSOUserProfile",
    "SpanTable",
    "TraceTable",
    "TransactionTable",
    "User",
    "Variable",
    "VertexBuildTable",
]
