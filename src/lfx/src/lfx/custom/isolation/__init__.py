"""Isolation for code validation and execution.

This module provides isolated import and execution environments to ensure
user-provided code executes in an isolated namespace without access to
dangerous system modules or builtins.

NOTE: Currently, this isolation is ONLY used during code validation
(via /api/v1/validate/code endpoint). It is NOT used during actual
flow execution. Code that passes validation will execute with full
system access during flow runs.

TODO: Consider adding isolation to runtime flow execution
for additional security. This would require modifying create_class()
and execute_function() in validate.py to use execute_in_isolated_env()
instead of regular exec().

Security Levels:
    MODERATE (default): Allows common legitimate operations (HTTP requests, async,
        temp files, serialization) while blocking direct system access (file I/O,
        subprocess, dynamic code execution).

    STRICT: Blocks all potentially dangerous operations including HTTP requests,
        file operations, and async operations. Maximum security but may block
        legitimate use cases.

    DISABLED: No restrictions. Code can access all Python builtins and modules.
        Use only in trusted environments or for debugging.

Configuration:
    Set LANGFLOW_ISOLATION_SECURITY_LEVEL to one of: "moderate", "strict", "disabled"
    Default: "moderate"
"""

from lfx.custom.isolation.config import SecurityLevel, SecurityViolationError
from lfx.custom.isolation.execution import execute_in_isolated_env
from lfx.custom.isolation.isolation import create_isolated_import, create_isolated_builtins
from lfx.custom.isolation.transformer import DunderAccessTransformer

__all__ = [
    "SecurityViolationError",
    "SecurityLevel",
    "execute_in_isolated_env",
    "create_isolated_import",
    "create_isolated_builtins",
    "DunderAccessTransformer",
]


