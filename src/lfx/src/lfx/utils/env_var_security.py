"""Guard the global-variable → environment-variable fallback.

When a flow field is marked *load from DB* and the named global variable is not found,
the loader can fall back to ``os.getenv(<name the flow author typed>)`` (controlled by
``LANGFLOW_FALLBACK_TO_ENV_VAR``, default ``True``). The looked-up name comes straight
from the flow definition, so in a multi-tenant deployment any authenticated tenant can
name a *server* environment variable and have its value injected into their flow output —
e.g. set a field's value to ``LANGFLOW_SECRET_KEY`` or ``LANGFLOW_DATABASE_URL`` and read
back the master encryption key (which decrypts every tenant's stored credentials) or the
database URL.

This module blocks that fallback for server-reserved / sensitive variable names. It does
NOT touch values that come from the database (a tenant's own stored global variables); it
only constrains which process-environment names the fallback is allowed to read.

This is a denylist, not an allowlist, so it stays compatible with the documented
single-user behavior (arbitrary env vars usable as global variables) while neutralizing
the catastrophic leaks. Operators who want a strict allowlist should instead disable the
fallback entirely with ``LANGFLOW_FALLBACK_TO_ENV_VAR=false`` and provision values as
database-backed global variables.
"""

from __future__ import annotations

# Variable-name prefixes that belong to the application/runtime itself. Langflow and lfx
# read all of their own configuration (secret key, database URL, auth secrets, superuser
# password, ...) from variables under these prefixes via a settings ``env_prefix``. None of
# them are ever meant to be surfaced as a flow value, and several are crown-jewel secrets.
_RESERVED_ENV_PREFIXES: tuple[str, ...] = (
    "LANGFLOW_",
    "LFX_",
)

# Exact names that carry infrastructure secrets but do not use a reserved prefix. Kept
# deliberately small and obvious; the prefix rule above covers the application's own config.
_RESERVED_ENV_NAMES: frozenset[str] = frozenset(
    {
        "DATABASE_URL",
        "SECRET_KEY",
        "POSTGRES_PASSWORD",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    }
)


def is_protected_env_var(name: str) -> bool:
    """Return True if ``name`` must never be resolved via the env-var fallback.

    Matching is case-insensitive so that, e.g., ``langflow_secret_key`` cannot slip
    through. An empty or non-string name is treated as protected (fail closed).
    """
    if not name or not isinstance(name, str):
        return True

    upper = name.upper()
    if upper in _RESERVED_ENV_NAMES:
        return True
    return any(upper.startswith(prefix) for prefix in _RESERVED_ENV_PREFIXES)


def safe_getenv(name: str) -> str | None:
    """``os.getenv(name)`` that refuses server-reserved / sensitive variable names.

    Returns ``None`` for a protected name (as if the variable were unset) so callers can
    treat it identically to a missing variable without leaking whether it exists.
    """
    import os

    if is_protected_env_var(name):
        return None
    return os.getenv(name)
