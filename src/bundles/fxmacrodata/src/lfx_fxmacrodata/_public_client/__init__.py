"""Documented public client contracts for FXMacroData integrations."""
from .client import FXMacroDataClient, FXMacroDataError, Operation, Result, list_operations

__all__ = ["FXMacroDataClient", "FXMacroDataError", "Operation", "Result", "list_operations"]
