"""Re-export shim: these ORM models moved to ``lfx.services.database.models.variable``.

lfx owns the ORM model definitions; langflow keeps the alembic migrations
and this import path for backward compatibility. Class identity is
preserved.
"""

from lfx.services.database.models.variable import (
    Variable,
    VariableBase,
    VariableCreate,
    VariableRead,
    VariableUpdate,
    utc_now,
)

__all__ = [
    "Variable",
    "VariableBase",
    "VariableCreate",
    "VariableRead",
    "VariableUpdate",
    "utc_now",
]
