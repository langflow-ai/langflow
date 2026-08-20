"""Backend registry: the one place that maps a backend name to its implementation.

Before this registry the name ``exec-sandbox`` had to be spelled in two
independent allowlists — the dispatch chain here and a second copy inside
``lfx.services.settings.groups.security.validate_sandbox_backend``. A backend
added to one and missed in the other made Langflow raise at startup. The
registry owns the list, so the two cannot drift.

A backend registers itself at import. In-tree backends are imported by
``lfx.utils.sandbox``; an out-of-tree backend ships a package that declares an
``lfx.sandbox_backends`` entry point, which is the same mechanism the service
layer uses (``lfx.services.manager._discover_from_entry_points``).
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.utils.sandbox.base import SandboxBackend

# The one name that never reaches a backend: it means "no sandbox at all".
SANDBOX_BACKEND_NONE = "none"

_ENTRY_POINT_GROUP = "lfx.sandbox_backends"

_lock = threading.Lock()
_factories: dict[str, Callable[[], SandboxBackend]] = {}
_instances: dict[str, SandboxBackend] = {}
_entry_points_loaded = False
# Names owned by in-tree backends, frozen by seal_builtins(). A plugin can
# never take one of these over.
_builtin_names: frozenset[str] = frozenset()


def register_sandbox_backend(name: str, factory: Callable[[], SandboxBackend]) -> None:
    """Register ``factory`` under ``name``.

    The factory is called at most once per process, the first time the backend
    is actually used, so registering a backend costs nothing until an operator
    selects it. Re-registering a name replaces the factory and drops any
    instance already built from the previous one.
    """
    if name == SANDBOX_BACKEND_NONE:
        msg = f"{SANDBOX_BACKEND_NONE!r} is reserved and cannot name a backend"
        raise ValueError(msg)
    if name in _builtin_names:
        # Replacing a built-in would let anything that can run an import
        # substitute its own executor for exec-sandbox or createos while the
        # operator's settings still name the backend they trusted.
        msg = f"{name!r} is a built-in sandbox backend and cannot be replaced"
        raise ValueError(msg)
    with _lock:
        _factories[name] = factory
        _instances.pop(name, None)


def known_sandbox_backends() -> tuple[str, ...]:
    """Every accepted value of LANGFLOW_SANDBOX_BACKEND, including ``none``.

    Read by the dispatcher and by the settings validator, so an operator can
    never be told a backend is unknown by one and accepted by the other.
    """
    _load_entry_points()
    with _lock:
        return (SANDBOX_BACKEND_NONE, *sorted(_factories))


def resolve_sandbox_backend(name: str) -> SandboxBackend:
    """Return the singleton instance of the backend called ``name``.

    Raises:
        KeyError: No backend is registered under that name. The caller turns
            this into the operator-facing message, because only the caller
            knows which setting supplied the name.
    """
    _load_entry_points()
    with _lock:
        instance = _instances.get(name)
        if instance is None:
            factory = _factories[name]
            instance = _instances[name] = factory()
        return instance


def live_sandbox_backends() -> tuple[SandboxBackend, ...]:
    """Every backend instance that was actually built.

    Used by process-wide hooks (fork, shutdown) that must touch what exists
    without constructing anything that does not.
    """
    with _lock:
        return tuple(_instances.values())


def seal_builtins() -> None:
    """Mark everything registered so far as in-tree.

    Called once, after the in-tree backends import themselves. A name recorded
    here can never be taken over afterwards, so an installed package cannot
    quietly become ``exec-sandbox``.
    """
    global _builtin_names  # noqa: PLW0603 - module-level one-shot latch
    with _lock:
        _builtin_names = frozenset(_factories)


def _plugin_allowlist() -> frozenset[str]:
    """Entry-point names the operator has explicitly permitted.

    Empty by default, which means no out-of-tree code is imported at all.

    This is an environment variable rather than a settings field for two
    reasons. The settings validator calls
    :func:`known_sandbox_backends`, so reading settings from here would
    recurse. More importantly, trusting a package to enforce an isolation
    boundary is a deployment decision about what is installed on the host, not
    an application preference someone should be able to edit through the app.
    """
    raw = os.environ.get("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "")
    return frozenset(name.strip() for name in raw.split(",") if name.strip())


def _load_entry_points() -> None:
    """Load the out-of-tree backends the operator named, once per process.

    Discovery is deliberately NOT automatic. ``entry_point.load()`` imports
    third-party code into the Langflow process, and this function runs on the
    path that decides whether user code is isolated -- including from the
    settings validator at startup. Importing every installed package that
    happens to declare the group would let a compromised or merely mistaken
    dependency execute here, before anything has chosen a backend, and the
    later policy gate cannot help: it only compares fields the backend reports
    about itself.

    So capability declarations are configuration metadata, not evidence of
    enforcement, and the trust decision is the operator's:
    ``LANGFLOW_SANDBOX_BACKEND_PLUGINS`` names the entry points that may load.
    Anything unnamed is never imported. A name already used in-tree is refused
    rather than replaced.

    A broken third-party package must not stop a correctly configured Langflow
    from starting, so a failure here is logged and the backend is simply
    absent. It cannot fail open: an absent backend makes the dispatcher refuse
    the run.
    """
    global _entry_points_loaded  # noqa: PLW0603 - module-level one-shot latch
    with _lock:
        if _entry_points_loaded:
            return
        _entry_points_loaded = True

    allowed = _plugin_allowlist()
    if not allowed:
        return

    from importlib.metadata import entry_points

    try:
        discovered = entry_points(group=_ENTRY_POINT_GROUP)
    except Exception:  # noqa: BLE001 - a broken environment must not block startup
        logger.warning("Could not enumerate %s entry points", _ENTRY_POINT_GROUP, exc_info=True)
        return

    for entry_point in discovered:
        if entry_point.name not in allowed:
            logger.debug(
                "Ignoring sandbox backend %r: not listed in LANGFLOW_SANDBOX_BACKEND_PLUGINS", entry_point.name
            )
            continue
        if entry_point.name in _builtin_names:
            logger.warning(
                "Refusing sandbox backend plugin %r: that name belongs to a built-in backend", entry_point.name
            )
            continue
        try:
            factory = entry_point.load()
        except Exception:  # noqa: BLE001 - one bad plugin must not hide the others
            logger.warning("Could not load sandbox backend %r", entry_point.name, exc_info=True)
            continue
        register_sandbox_backend(entry_point.name, factory)
        logger.info("Registered out-of-tree sandbox backend %r", entry_point.name)


def get_sandbox_backend() -> str:
    """Return the configured sandbox backend name (``none`` when unset).

    An absent or unresolvable settings stack means the sandbox was never
    opted into, so the answer is ``none`` — unlike the
    ``allow_custom_components`` gate there is no fail-closed question here;
    the fail-closed behavior lives in :func:`run_code_in_sandbox` once a
    backend IS configured.
    """
    try:
        from lfx.services.deps import get_settings_service

        settings_service = get_settings_service()
    except ImportError:
        return SANDBOX_BACKEND_NONE
    if settings_service is None:
        return SANDBOX_BACKEND_NONE
    backend = getattr(settings_service.settings, "sandbox_backend", SANDBOX_BACKEND_NONE)
    return backend or SANDBOX_BACKEND_NONE


def is_sandbox_enabled() -> bool:
    """True when a non-default sandbox backend is configured."""
    return get_sandbox_backend() != SANDBOX_BACKEND_NONE
