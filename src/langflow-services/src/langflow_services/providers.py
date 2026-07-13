"""Host-injected providers for seams that live outside this package.

Concrete services must not import ``langflow.*``. Host bootstrap registers
CRUD callables and other host-owned helpers here during startup.
"""

from __future__ import annotations

from typing import Any

_CRUD: dict[str, Any] = {}
_HOOKS: dict[str, Any] = {}


def register_crud(name: str, provider: Any) -> None:
    """Register a CRUD module or namespace object under ``name``."""
    _CRUD[name] = provider


def get_crud(name: str) -> Any:
    try:
        return _CRUD[name]
    except KeyError as exc:
        msg = (
            f"CRUD provider {name!r} is not registered. "
            "langflow-base must call langflow_services.providers.register_crud during bootstrap."
        )
        raise RuntimeError(msg) from exc


def register_hook(name: str, hook: Any) -> None:
    """Register an arbitrary host callback under ``name``."""
    _HOOKS[name] = hook


def get_hook(name: str, default: Any = None) -> Any:
    return _HOOKS.get(name, default)


def require_hook(name: str) -> Any:
    hook = _HOOKS.get(name)
    if hook is None:
        msg = f"Host hook {name!r} is not registered. langflow-base must register it during service bootstrap."
        raise RuntimeError(msg)
    return hook


def get_version_info() -> Any:
    """Return host Langflow version metadata (never the LFX stub)."""
    return require_hook("get_version_info")()
