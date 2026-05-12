from __future__ import annotations

from .api_key import ApiKey
from .auth import SSOConfig, SSOUserProfile
from .deployment import Deployment
from .deployment_provider_account import DeploymentProviderAccount
from .file import File
from .flow import Flow
from .flow_version import FlowVersion
from .flow_version_deployment_attachment import FlowVersionDeploymentAttachment
from .folder import Folder
from .jobs import Job
from .memory_base import MemoryBase, MemoryBaseSession, MemoryBaseWorkflowRun, MessageIngestionRecord
from .message import MessageTable
from .user import User
from .variable import Variable

__all__ = [
    "ApiKey",
    "Deployment",
    "DeploymentProviderAccount",
    "File",
    "Flow",
    "FlowVersion",
    "FlowVersionDeploymentAttachment",
    "Folder",
    "Job",
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
]


# SpanTable, TraceTable, and TransactionTable all eagerly import
# langflow.serialization.serialization which loads pandas (~13s). Keep lazy.
def __getattr__(name: str):
    if name in {"SpanTable", "TraceTable"}:
        from .traces.model import SpanTable, TraceTable

        globals()["SpanTable"] = SpanTable
        globals()["TraceTable"] = TraceTable
        return globals()[name]
    if name == "TransactionTable":
        from .transactions import TransactionTable

        globals()["TransactionTable"] = TransactionTable
        return TransactionTable
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
