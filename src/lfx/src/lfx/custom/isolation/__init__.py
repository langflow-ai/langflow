"""Isolation for code validation and execution.

This module provides isolated import and execution environments to ensure
user-provided code executes in an isolated namespace without access to
dangerous system modules or builtins.

SECURITY STATUS:
- ✅ Module-level imports ARE blocked during validation and runtime execution
- ✅ Runtime imports in function/method bodies ARE detected and blocked during validation via static analysis
- ✅ Function definitions (including decorators) execute in isolation during validation
- ✅ Runtime execution isolation is enforced for custom components (create_class, execute_function, create_function)
- ✅ Core components (matching component index) bypass isolation and can use all builtins

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
from lfx.custom.isolation.isolation import create_isolated_builtins, create_isolated_import
from lfx.custom.isolation.transformer import DunderAccessTransformer

__all__ = [
    "DunderAccessTransformer",
    "SecurityLevel",
    "SecurityViolationError",
    "create_isolated_builtins",
    "create_isolated_import",
    "execute_in_isolated_env",
]
