"""Re-export shim: the message ORM models moved to ``lfx.services.database.models.message``.

lfx owns the execution-history schema (rows produced during graph runs);
langflow keeps the alembic migrations and this import path for backward
compatibility. Class identity is preserved — ``langflow`` and ``lfx``
callers get the same class objects.
"""

from lfx.services.database.models.message import (
    MessageBase,
    MessageCreate,
    MessageRead,
    MessageTable,
    MessageUpdate,
)

__all__ = [
    "MessageBase",
    "MessageCreate",
    "MessageRead",
    "MessageTable",
    "MessageUpdate",
]
