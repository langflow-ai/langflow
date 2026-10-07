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

import contextlib
import os
import threading
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from importlib.metadata import EntryPoint

    from lfx.utils.sandbox.base import SandboxBackend

# The one name that never reaches a backend: it means "no sandbox at all".
SANDBOX_BACKEND_NONE = "none"

_ENTRY_POINT_GROUP = "lfx.sandbox_backends"

# Guards the registry dictionaries only. Never held while third-party code
# runs, so a factory or a plugin import can call back into this module.
_lock = threading.Lock()
# Held across the whole entry-point load, so a second thread waits for the
# load to FINISH rather than observing a half-populated registry. Reentrant:
# a plugin module that calls back into this module during its own import must
# not deadlock against the load that imported it.
_load_lock = threading.RLock()
_factories: dict[str, Callable[[], SandboxBackend]] = {}
_instances: dict[str, SandboxBackend] = {}
_entry_points_loaded = False
# Names owned by in-tree backends, frozen by seal_builtins(). A plugin can
# never take one of these over.
_builtin_names: frozenset[str] = frozenset()


def register_sandbox_backend(name: str, factory: Callable[[], SandboxBackend]) -> None:
    """Register ``factory`` under ``name``.

    The factory is called lazily when the backend is first used, so registering
    a backend costs nothing until an operator selects it. Concurrent first
    resolutions may construct more than one candidate; the registry keeps one
    singleton and shuts the others down. A name may be registered only once:
    replacing a live backend would orphan its process-wide resources and could
    race an in-flight resolution against two different factories.

    The name is stripped and lowercased. The settings validator normalizes
    ``sandbox_backend`` before comparing it against
    :func:`known_sandbox_backends`, so a name registered with an uppercase
    letter would be listed as available and yet never be selectable.
    """
    name = name.strip().lower()
    if not name:
        msg = "a sandbox backend name cannot be empty"
        raise ValueError(msg)
    if name == SANDBOX_BACKEND_NONE:
        msg = f"{SANDBOX_BACKEND_NONE!r} is reserved and cannot name a backend"
        raise ValueError(msg)
    if not callable(factory):
        msg = f"sandbox backend {name!r} must register a callable factory"
        raise TypeError(msg)
    if name in _builtin_names:
        # Replacing a built-in would let anything that can run an import
        # substitute its own executor for exec-sandbox while the
        # operator's settings still name the backend they trusted.
        msg = f"{name!r} is a built-in sandbox backend and cannot be replaced"
        raise ValueError(msg)
    with _lock:
        if name in _factories:
            msg = f"sandbox backend {name!r} is already registered"
            raise ValueError(msg)
        _factories[name] = factory


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
    name = name.lower()
    _load_entry_points()
    with _lock:
        instance = _instances.get(name)
        if instance is not None:
            return instance
        factory = _factories[name]

    # Built outside the lock. A factory validates control-plane configuration
    # or probes hardware acceleration, and it may call back into this module;
    # `_lock` is not reentrant, so holding it here would deadlock the process
    # on the first such factory and would block `known_sandbox_backends()` --
    # which the settings validator calls at startup -- for the whole probe.
    built = factory()

    with _lock:
        # Another thread may have finished first while we were building.
        # Whoever landed first wins, so the singleton stays a singleton.
        winner = _instances.setdefault(name, built)

    if winner is not built:
        # The loser is unreachable: it is not in _instances, so
        # live_sandbox_backends() never returns it and shutdown_sandbox()
        # cannot reach it. A factory that acquired a loop thread or a client
        # pool would leak it for the process lifetime.
        with contextlib.suppress(Exception):
            built.shutdown()
    return winner


def live_sandbox_backends() -> tuple[SandboxBackend, ...]:
    """Every backend instance that was actually built.

    Used by process-wide hooks (fork, shutdown) that must touch what exists
    without constructing anything that does not.
    """
    with _lock:
        return tuple(_instances.values())


def reset_registry_after_fork() -> None:
    """Replace this module's mutexes in a freshly forked child.

    A lock held by another thread at fork time is inherited LOCKED with no
    owner, and the child has no thread that can release it. Every reader here
    would then block forever, including the fork hook itself, which reads the
    registry before it touches anything else.

    Only safe in the child's single-threaded post-fork window, which is the
    only place it is called from.
    """
    global _lock, _load_lock  # noqa: PLW0603 - post-fork mutex replacement
    _lock = threading.Lock()
    _load_lock = threading.RLock()


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
    # Lowercased, because register_sandbox_backend lowercases too. Matching
    # verbatim on one side and normalizing on the other means an operator who
    # spells the case differently from the entry point gets a silent skip and
    # a startup failure reporting the backend as unknown.
    raw = os.environ.get("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "")
    return frozenset(name.strip().lower() for name in raw.split(",") if name.strip())


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
    # The latch is read AND set under a lock that stays held for the whole
    # load. Set it before importing a plugin so a same-thread callback into
    # known_sandbox_backends() sees the registry state collected so far rather
    # than recursively starting the entry-point load again. Other threads
    # cannot observe the early value: they remain blocked on _load_lock until
    # the load has finished.
    with _load_lock:
        if _entry_points_loaded:
            return
        _entry_points_loaded = True
        _load_entry_points_locked()


def _load_entry_points_locked() -> None:
    """The body of :func:`_load_entry_points`, run once with ``_load_lock`` held."""
    allowed = _plugin_allowlist()
    if not allowed:
        return

    from importlib.metadata import entry_points

    try:
        discovered = entry_points(group=_ENTRY_POINT_GROUP)
    except Exception:  # noqa: BLE001 - a broken environment must not block startup
        logger.warning("Could not enumerate %s entry points", _ENTRY_POINT_GROUP, exc_info=True)
        return

    # Grouped by name BEFORE anything is loaded. Two installed distributions can
    # publish the same entry-point name, and the allowlist names a backend, not a
    # distribution -- so it cannot say which of the two the operator meant.
    # Loading either one would be a guess, and the guess is made by whatever order
    # importlib.metadata happens to return, which the operator cannot see or pin.
    # Worse, the loop would import BOTH and let the second overwrite the first, so
    # the code that ran an import is not even the code that ends up registered.
    # Refusing the name is the only answer that never runs unintended code.
    by_name: dict[str, list[EntryPoint]] = {}
    for entry_point in discovered:
        by_name.setdefault(entry_point.name.strip().lower(), []).append(entry_point)

    for plugin_name, candidates in by_name.items():
        if plugin_name not in allowed:
            logger.debug("Ignoring sandbox backend %r: not listed in LANGFLOW_SANDBOX_BACKEND_PLUGINS", plugin_name)
            continue
        if len(candidates) > 1:
            logger.warning(
                "Refusing sandbox backend plugin %r: %d installed distributions provide that name (%s). "
                "Uninstall all but one, because the allowlist names a backend and cannot choose between them.",
                plugin_name,
                len(candidates),
                ", ".join(sorted(_distribution_of(candidate) for candidate in candidates)),
            )
            continue
        entry_point = candidates[0]
        if plugin_name in _builtin_names:
            logger.warning(
                "Refusing sandbox backend plugin %r: that name belongs to a built-in backend", entry_point.name
            )
            continue
        try:
            factory = entry_point.load()
        except Exception:  # noqa: BLE001 - one bad plugin must not hide the others
            logger.warning("Could not load sandbox backend %r", entry_point.name, exc_info=True)
            continue
        try:
            register_sandbox_backend(plugin_name, factory)
        except (TypeError, ValueError):
            # Malformed factory, reserved name, or duplicate name. The docstring promises a broken
            # plugin is absent rather than fatal, so this cannot propagate out
            # of the settings validator.
            logger.warning("Refusing sandbox backend plugin %r", entry_point.name, exc_info=True)
            continue
        logger.info("Registered out-of-tree sandbox backend %r", entry_point.name)


def _distribution_of(entry_point: EntryPoint) -> str:
    """Name the installed distribution an entry point came from, for a refusal message.

    Best effort: ``EntryPoint.dist`` is populated by ``entry_points()`` but is
    documented as optional, and the operator still has to be told the name is
    contested even when we cannot say by whom.
    """
    dist = getattr(entry_point, "dist", None)
    return getattr(dist, "name", None) or "unknown distribution"


def get_sandbox_backend() -> str:
    """Return the configured sandbox backend name (``none`` when unset).

    ``get_settings_service()`` returns None when the settings stack failed to
    build, which is indistinguishable here from "never configured". Answering
    ``none`` in that case would send user code to in-process ``exec`` on a
    deployment that explicitly asked for a sandbox, so the environment is read
    directly as a fallback. A name that no backend claims then fails closed in
    :func:`run_code_in_sandbox` rather than running unsandboxed.
    """
    try:
        from lfx.services.deps import get_settings_service

        settings_service = get_settings_service()
    except ImportError:
        settings_service = None
    if settings_service is not None:
        backend = getattr(settings_service.settings, "sandbox_backend", None)
        if backend:
            return backend.lower()
    return os.environ.get("LANGFLOW_SANDBOX_BACKEND", "").strip().lower() or SANDBOX_BACKEND_NONE


def is_sandbox_enabled() -> bool:
    """True when a non-default sandbox backend is configured."""
    return get_sandbox_backend() != SANDBOX_BACKEND_NONE
