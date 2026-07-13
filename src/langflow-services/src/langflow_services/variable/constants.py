"""Re-export shim: variable type constants moved to ``lfx.services.database.models.variable``."""

from lfx.services.database.models.variable import CREDENTIAL_TYPE, GENERIC_TYPE

__all__ = ["CREDENTIAL_TYPE", "GENERIC_TYPE"]
