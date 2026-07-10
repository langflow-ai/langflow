"""Re-export shim: these ORM models moved to ``lfx.services.database.models.ingestion_run``.

lfx owns the ORM model definitions; langflow keeps the alembic migrations
and this import path for backward compatibility. Class identity is
preserved.
"""

from lfx.services.database.models.ingestion_run import (
    IngestionRun,
    IngestionRunBase,
    IngestionRunStatus,
    JsonVariant,
)

__all__ = [
    "IngestionRun",
    "IngestionRunBase",
    "IngestionRunStatus",
    "JsonVariant",
]
