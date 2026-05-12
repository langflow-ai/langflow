"""Ingestion-source registry.

Thin wrapper over :class:`lfx.services.adapters.registry.AdapterRegistry`
that keeps the original ``register_source`` / ``create_source`` /
``get_source_class`` / ``registered_sources`` public API while adding
third-party plugin discovery.

Third parties can ship an ingestion source in two new ways on top of
the original in-tree registration:

* **Entry point** under the ``lfx.ingestion_source.adapters`` group::

      [project.entry-points."lfx.ingestion_source.adapters"]
      box = "langflow_box.source:BoxSource"

* **Config file** — ``lfx.toml`` (preferred) or ``pyproject.toml``::

      [ingestion_source.adapters]
      box = "langflow_box.source:BoxSource"

Both paths resolve to the same registry as an import-time
``register_source(...)`` call. Sources are instantiated per request
(each call to ``create_source`` returns a fresh object) — we use the
registry's ``get_class`` accessor and do not share singleton instances
because each source carries request-scoped ``user_id`` + ``source_config``.

The ``SourceType`` enum stays the source of truth for the built-in
source identifiers so typos in call sites still fail at static
analysis time. Third-party plugins may register under any string key —
``create_source("box", ...)`` works whether or not ``box`` is in the
enum.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.ingestion_sources.base import KBIngestionSource, SourceType
from lfx.services.adapters.registry import get_adapter_registry
from lfx.services.adapters.schema import AdapterType

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.adapters.registry import AdapterRegistry


_discovery_lock = threading.Lock()


def _registry() -> AdapterRegistry[KBIngestionSource]:
    """Return the singleton ``AdapterRegistry`` for ingestion sources."""
    return get_adapter_registry(adapter_type=AdapterType.INGESTION_SOURCE)


def _ensure_discovered() -> None:
    """Run entry-point + config-file discovery exactly once.

    Mirrors the pattern in :func:`lfx.services.deps.get_deployment_adapter`:
    discovery is lazy so importing this module doesn't pay for TOML
    parsing or entry-point enumeration until a source is actually
    resolved.
    """
    registry = _registry()
    if registry.is_discovered:
        return
    with _discovery_lock:
        if registry.is_discovered:
            return
        # Import here to avoid a top-level dependency on settings when
        # lfx is used as a plain library (e.g. from tests) — the
        # deployment path does the same.
        from lfx.services.config_discovery import resolve_config_dir
        from lfx.services.deps import get_settings_service

        config_dir = resolve_config_dir(None, settings_service=get_settings_service())
        registry.discover(config_dir=config_dir)


def register_source(source_type: SourceType | str, source_class: type[KBIngestionSource]) -> None:
    """Register ``source_class`` under ``source_type``.

    Re-registering the same class under the same key is a no-op.
    Re-registering a *different* class raises ``ValueError`` so
    accidental collisions surface at import time rather than as
    mysterious runtime behavior. ``AdapterRegistry.register_class`` is
    otherwise permissive (override=True by default); the collision
    check is added here to preserve the behavior of the original
    hand-rolled registry.
    """
    key = _resolve_key(source_type)
    registry = _registry()
    existing = registry.get_class(key)
    if existing is not None and existing is not source_class:
        msg = (
            f"Ingestion source {key!r} is already registered to "
            f"{existing.__name__}; refusing to overwrite with {source_class.__name__}."
        )
        raise ValueError(msg)
    registry.register_class(key, source_class, override=True)


def get_source_class(source_type: SourceType | str) -> type[KBIngestionSource]:
    """Return the registered class for ``source_type`` or raise.

    Looks up the class only — instantiation happens in ``create_source``
    so each call builds a fresh source with its own ``user_id`` and
    ``source_config``. Triggers lazy discovery on first use.

    Raises:
        ValueError: With ``"Unknown ingestion source"`` when the input
            is a string that is neither a built-in ``SourceType`` value
            nor a registered plugin key (typo at the call site).
            With ``"not registered"`` when the input is a known key
            but no class is bound to it (built-in source not imported,
            or plugin not yet discovered).
    """
    _ensure_discovered()
    key = _resolve_key(source_type)
    registry = _registry()
    source_class = registry.get_class(key)
    if source_class is not None:
        return source_class

    # Split the error message to preserve the contract of the original
    # hand-rolled registry:
    #   * unknown string (not a built-in enum AND not a plugin key) →
    #     "Unknown ingestion source …" — surfaces config typos.
    #   * known enum / plugin key without a bound class →
    #     "Ingestion source … is not registered" — surfaces missing
    #     import / failed plugin discovery.
    if isinstance(source_type, str) and not _is_known_key(key, registry):
        allowed = ", ".join(st.value for st in SourceType)
        msg = f"Unknown ingestion source {key!r}. Expected one of: {allowed}."
        raise ValueError(msg)

    available = ", ".join(registry.list_keys())
    msg = f"Ingestion source {key!r} is not registered. Registered sources: {available or '<none>'}."
    raise ValueError(msg)


def _is_known_key(key: str, registry: AdapterRegistry[KBIngestionSource]) -> bool:
    """Return True if ``key`` is a built-in ``SourceType`` value or a registered plugin key."""
    if key in registry.list_keys():
        return True
    try:
        SourceType(key)
    except ValueError:
        return False
    return True


def registered_sources() -> tuple[SourceType, ...]:
    """Tuple of registered ``SourceType`` identifiers (stable ordering).

    Third-party plugins registering under keys not in the ``SourceType``
    enum are *excluded* from this tuple — the return type is still
    ``tuple[SourceType, ...]`` for backward compatibility with callers
    that key UI pickers and switch statements off the enum. Use
    ``registered_source_keys`` for the full list including plugins.
    """
    _ensure_discovered()
    built_ins: list[SourceType] = []
    for key in _registry().list_keys():
        try:
            built_ins.append(SourceType(key))
        except ValueError:
            # Third-party plugin using a key outside the built-in enum.
            continue
    return tuple(sorted(built_ins, key=lambda st: st.value))


def registered_source_keys() -> tuple[str, ...]:
    """All registered source keys including third-party plugin keys.

    New API introduced with the AdapterRegistry migration. Call sites
    that want to expose plugin sources in a picker (e.g. the connector
    catalog endpoint) should prefer this over ``registered_sources``.
    """
    _ensure_discovered()
    return tuple(_registry().list_keys())


def create_source(
    source_type: SourceType | str,
    *,
    user_id: UUID | str | None,
    source_config: dict[str, Any] | None = None,
) -> KBIngestionSource:
    """Factory: build a fresh source instance for ``source_type``.

    Each call instantiates a new source — the registry does not cache
    instances. Sources carry request-scoped state (``user_id``,
    ``source_config``) so instance sharing would be incorrect.
    """
    source_class = get_source_class(source_type)
    return source_class(user_id=user_id, source_config=source_config or {})


def _resolve_key(value: SourceType | str) -> str:
    """Coerce an enum or string into the registry key.

    Built-in callers pass ``SourceType.S3``; HTTP payloads pass the
    string ``"s3"``. Unknown strings pass through unchanged so
    third-party plugin keys are honoured. Validation against the
    built-in enum still happens at API boundaries (see the
    ``ConnectorIngestRequest`` schema).
    """
    if isinstance(value, SourceType):
        return value.value
    return value
