"""Re-export shim: these ORM models moved to ``lfx.services.database.models.flow_version_deployment_attachment``.

lfx owns the ORM model definitions; langflow keeps the alembic migrations
and this import path for backward compatibility. Class identity is
preserved.
"""

from lfx.services.database.models.flow_version_deployment_attachment import (
    FlowVersionDeploymentAttachment,
)

__all__ = [
    "FlowVersionDeploymentAttachment",
]
