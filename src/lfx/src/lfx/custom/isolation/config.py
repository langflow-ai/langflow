"""Security configuration for isolation.

Defines security levels and blocked modules/builtins.
"""

from enum import Enum
from functools import lru_cache


class SecurityViolationError(Exception):
    """Raised when code attempts to escape isolation or use blocked operations."""


class SecurityLevel(str, Enum):
    """Security levels for isolation."""

    MODERATE = "moderate"  # Default: Allows common operations, blocks system access
    STRICT = "strict"  # Maximum security: Blocks most operations
    DISABLED = "disabled"  # No restrictions (use with caution)


@lru_cache(maxsize=1)
def _get_security_level() -> SecurityLevel:
    """Get security level from settings service.
    
    Returns:
        SecurityLevel: The current security level, defaults to MODERATE.
    """
    try:
        from lfx.services.deps import get_settings_service

        settings_service = get_settings_service()
        if not settings_service or not settings_service.settings:
            # Default to MODERATE if settings service not available
            return SecurityLevel.MODERATE
        env_value = getattr(settings_service.settings, "isolation_security_level", None)
        if not env_value:
            # Default to MODERATE if not set
            return SecurityLevel.MODERATE
        return SecurityLevel(str(env_value).lower())
    except (ValueError, AttributeError) as e:
        # Default to MODERATE on error
        return SecurityLevel.MODERATE
    except Exception:
        # Default to MODERATE on any other error
        return SecurityLevel.MODERATE


def get_security_level() -> SecurityLevel:
    """Get the current security level.
    
    Returns:
        SecurityLevel: The current security level.
    """
    return _get_security_level()


def clear_cache() -> None:
    """Clear all cached values."""
    _get_security_level.cache_clear()
    _get_blocked_builtins.cache_clear()
    _get_blocked_modules.cache_clear()

# Builtins that are always blocked (even in MODERATE mode)
# These allow direct system access or code injection
CRITICAL_BUILTINS: frozenset[str] = frozenset({
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
})

# Builtins blocked in STRICT mode but allowed in MODERATE mode
# These are common legitimate operations that don't directly access system
MODERATE_BUILTINS: frozenset[str] = frozenset({
    "open",  # File I/O - common but can access filesystem
})

# Modules blocked in STRICT mode but allowed in MODERATE mode
# These are common legitimate operations (HTTP, async, temp files, etc.)
MODERATE_MODULES: frozenset[str] = frozenset({
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
})

# Modules always blocked (even in MODERATE mode)
CRITICAL_MODULES: frozenset[str] = frozenset({
    # Direct system access modules
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
})

@lru_cache(maxsize=1)
def _get_blocked_builtins() -> frozenset[str]:
    """Get blocked builtins based on current security level."""
    level = _get_security_level()
    if level == SecurityLevel.DISABLED:
        return frozenset()
    elif level == SecurityLevel.STRICT:
        return CRITICAL_BUILTINS | MODERATE_BUILTINS
    else:  # MODERATE (default)
        return CRITICAL_BUILTINS


@lru_cache(maxsize=1)
def _get_blocked_modules() -> frozenset[str]:
    """Get blocked modules based on current security level."""
    level = _get_security_level()
    if level == SecurityLevel.DISABLED:
        return frozenset()
    elif level == SecurityLevel.STRICT:
        return CRITICAL_MODULES | MODERATE_MODULES
    else:  # MODERATE (default)
        return CRITICAL_MODULES


def get_blocked_builtins() -> frozenset[str]:
    """Get the set of blocked builtins.
    
    Returns:
        frozenset[str]: Set of blocked builtin names.
    """
    return _get_blocked_builtins()


def get_blocked_modules() -> frozenset[str]:

    """Get the set of blocked modules.
    
    Returns:
        frozenset[str]: Set of blocked module names.
    """
    return _get_blocked_modules()

# Note: We don't maintain a whitelist of allowed modules.
# Instead, we block dangerous modules and allow everything else.
# This allows users to import legitimate third-party libraries (AI libraries, utilities, etc.)
# while still blocking dangerous system-level operations.


