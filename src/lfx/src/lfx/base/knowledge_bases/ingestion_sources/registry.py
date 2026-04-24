"""Ingestion-source registry — mirror of ``backends.registry`` for sources.

Sources register themselves on import (see ``ingestion_sources/__init__.py``).
Call sites use ``create_source`` so swapping or adding a source is a
one-line change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.ingestion_sources.base import KBIngestionSource, SourceType

if TYPE_CHECKING:
    from uuid import UUID


_SOURCE_REGISTRY: dict[SourceType, type[KBIngestionSource]] = {}


def register_source(source_type: SourceType, source_class: type[KBIngestionSource]) -> None:
    """Register ``source_class`` under ``source_type``.

    Idempotent: re-registering the same class is a no-op; re-registering
    a different class raises ``ValueError`` so accidental collisions
    surface at import time rather than producing mysterious runtime
    behavior.
    """
    existing = _SOURCE_REGISTRY.get(source_type)
    if existing is not None and existing is not source_class:
        msg = (
            f"Ingestion source {source_type.value!r} is already registered to "
            f"{existing.__name__}; refusing to overwrite with {source_class.__name__}."
        )
        raise ValueError(msg)
    _SOURCE_REGISTRY[source_type] = source_class


def get_source_class(source_type: SourceType | str) -> type[KBIngestionSource]:
    """Return the registered class for ``source_type`` or raise."""
    resolved = _resolve_source_type(source_type)
    try:
        return _SOURCE_REGISTRY[resolved]
    except KeyError as exc:
        available = ", ".join(sorted(st.value for st in _SOURCE_REGISTRY))
        msg = f"Ingestion source {resolved.value!r} is not registered. Registered sources: {available or '<none>'}."
        raise ValueError(msg) from exc


def registered_sources() -> tuple[SourceType, ...]:
    """Tuple of registered source-type identifiers (stable ordering)."""
    return tuple(sorted(_SOURCE_REGISTRY, key=lambda st: st.value))


def create_source(
    source_type: SourceType | str,
    *,
    user_id: UUID | str | None,
    source_config: dict[str, Any] | None = None,
) -> KBIngestionSource:
    """Factory: build a source instance for ``source_type``.

    Single entry point so call sites never import concrete source
    classes directly. Keeps the source catalog open for Phase 3
    connectors without touching ``perform_ingestion``.
    """
    source_class = get_source_class(source_type)
    return source_class(user_id=user_id, source_config=source_config or {})


def _resolve_source_type(value: SourceType | str) -> SourceType:
    """Coerce strings from config / API payloads into a ``SourceType``."""
    if isinstance(value, SourceType):
        return value
    try:
        return SourceType(value)
    except ValueError as exc:
        allowed = ", ".join(st.value for st in SourceType)
        msg = f"Unknown ingestion source {value!r}. Expected one of: {allowed}."
        raise ValueError(msg) from exc
