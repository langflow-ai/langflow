from __future__ import annotations

__all__ = [
    "ApiKey",
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

_SOURCE_MAP: dict[str, str] = {
    "ApiKey": ".api_key",
    "SSOConfig": ".auth",
    "SSOUserProfile": ".auth",
    "Deployment": ".deployment",
    "DeploymentProviderAccount": ".deployment_provider_account",
    "File": ".file",
    "Flow": ".flow",
    "FlowVersion": ".flow_version",
    "FlowVersionDeploymentAttachment": ".flow_version_deployment_attachment",
    "Folder": ".folder",
    "IngestionRun": ".ingestion_run",
    "IngestionRunStatus": ".ingestion_run",
    "Job": ".jobs",
    "KnowledgeBaseRecord": ".knowledge_base",
    "KnowledgeBaseStatus": ".knowledge_base",
    "MemoryBase": ".memory_base",
    "MemoryBaseSession": ".memory_base",
    "MemoryBaseWorkflowRun": ".memory_base",
    "MessageIngestionRecord": ".memory_base",
    "MessageTable": ".message",
    "SpanTable": ".traces.model",
    "TraceTable": ".traces.model",
    "TransactionTable": ".transactions",
    "User": ".user",
    "Variable": ".variable",
}


def __getattr__(name: str):
    if name not in _SOURCE_MAP:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    import importlib

    mod = importlib.import_module(_SOURCE_MAP[name], package=__spec__.parent)
    val = getattr(mod, name)
    globals()[name] = val
    return val


def import_all() -> None:
    """Import every model class so they register in SQLModel.metadata.

    Call this before running Alembic migrations or any code that iterates
    __dict__ to discover SQLModel subclasses (e.g. schema health checks).
    Models are lazy by default to reduce cold-start import cost (each submodule
    pulls in SQLAlchemy validators, pydantic field definitions, etc.).

    Call sites: database/service.py (migration + health-check paths) and
    alembic/env.py (so out-of-band `alembic upgrade` sees complete metadata).
    All call sites must call import_all() before iterating SQLModel.metadata
    or __dict__ for model discovery.
    """
    for name in __all__:
        getattr(__import__(__name__, fromlist=[name]), name)
