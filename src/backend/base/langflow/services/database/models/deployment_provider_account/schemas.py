"""Re-export shim: these ORM models moved to ``lfx.services.database.models.deployment_provider_account.schemas``.

lfx owns the ORM model definitions; langflow keeps the alembic migrations
and this import path for backward compatibility. Class identity is
preserved.
"""

from lfx.services.database.models.deployment_provider_account.schemas import (
    DeploymentProviderKey,
)

__all__ = [
    "DeploymentProviderKey",
]
