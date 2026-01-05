"""Security configuration for isolation.

Defines security levels and blocked modules/builtins.
"""

import os
from enum import Enum


class SecurityViolationError(Exception):
    """Raised when code attempts to escape isolation or use blocked operations."""


class SecurityLevel(str, Enum):
    """Security levels for isolation."""

    MODERATE = "moderate"  # Default: Allows common operations, blocks system access
    STRICT = "strict"  # Maximum security: Blocks most operations
    DISABLED = "disabled"  # No restrictions (use with caution)


# Parse security level from environment variable
_SANDBOX_SECURITY_ENV = os.getenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "moderate").lower()

try:
    SECURITY_LEVEL = SecurityLevel(_SANDBOX_SECURITY_ENV)
except ValueError:
    # Invalid value, default to MODERATE
    SECURITY_LEVEL = SecurityLevel.MODERATE

# Builtins that are always blocked (even in MODERATE mode)
# These allow direct system access or code injection
CRITICAL_BUILTINS: set[str] = {
    "eval",  # Dynamic evaluation - code injection risk
    "exec",  # Dynamic execution - code injection risk
    "compile",  # Code compilation - code injection risk
    "__import__",  # Dynamic imports (we provide our own isolated version)
    "input",  # User input - can block execution
    "raw_input",  # User input (Python 2)
    "exit",
    "quit",  # Process control
    "breakpoint",  # Debugger access
    "reload",  # Module reloading
    "file",  # File I/O (Python 2)
}

# Builtins blocked in STRICT mode but allowed in MODERATE mode
# These are common legitimate operations that don't directly access system
MODERATE_BUILTINS: set[str] = {
    "open",  # File I/O - common but can access filesystem
}

# Modules blocked in STRICT mode but allowed in MODERATE mode
# These are common legitimate operations (HTTP, async, temp files, etc.)
MODERATE_MODULES: set[str] = {
    # HTTP libraries - very common for API calls
    "requests",
    "httpx",
    "urllib",
    "urllib2",
    "urllib3",
    # Async operations - common for modern Python code
    "asyncio",
    # Temporary files - common for data processing
    "tempfile",
    # Serialization - common for caching/data storage
    "pickle",
    "shelve",
    # Database - common for local storage
    "sqlite3",
    "dbm",
    # Network protocols (less common but legitimate)
    "ftplib",
    "telnetlib",
    "smtplib",
}

# Modules always blocked (even in MODERATE mode)
# These provide direct system access
CRITICAL_MODULES: set[str] = {
    # Direct system access
    "os",  # File system, environment, process control
    "sys",  # System-specific parameters, interpreter access
    "subprocess",  # Process execution
    "signal",  # Signal handling
    "resource",  # Resource usage
    "platform",  # Platform identification
    # Low-level network access
    "socket",  # Raw network sockets
    # File system operations
    "shutil",  # High-level file operations
    # Foreign function calls (can execute arbitrary code)
    "ctypes",
    "cffi",
    # Concurrency (can be used for DoS)
    "multiprocessing",
    "threading",
    # Other dangerous
    "marshal",  # Serialization format (can be exploited)
    "gc",  # Garbage collector manipulation
    "inspect",  # Can be used for introspection attacks
    "importlib",  # importlib allows bypassing our __import__ hook
}

# Compute blocked sets based on security level
if SECURITY_LEVEL == SecurityLevel.DISABLED:
    BLOCKED_BUILTINS: set[str] = set()
    BLOCKED_MODULES: set[str] = set()
elif SECURITY_LEVEL == SecurityLevel.STRICT:
    # STRICT: Block everything potentially dangerous
    BLOCKED_BUILTINS = CRITICAL_BUILTINS | MODERATE_BUILTINS
    BLOCKED_MODULES = CRITICAL_MODULES | MODERATE_MODULES
else:  # MODERATE (default)
    # MODERATE: Block critical operations, allow common legitimate uses
    BLOCKED_BUILTINS = CRITICAL_BUILTINS
    BLOCKED_MODULES = CRITICAL_MODULES

# Note: We don't maintain a whitelist of allowed modules.
# Instead, we block dangerous modules and allow everything else.
# This allows users to import legitimate third-party libraries (AI libraries, utilities, etc.)
# while still blocking dangerous system-level operations.


