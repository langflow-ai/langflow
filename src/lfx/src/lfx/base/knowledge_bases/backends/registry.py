"""Vector-store backend registry.

New backends register themselves by calling ``register_backend`` once on
import (see ``backends/__init__.py``). Call sites use ``create_backend`` to
obtain an instance without hard-coding backend classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.backends.base import BackendType

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from langchain_core.embeddings import Embeddings

    from lfx.base.knowledge_bases.backends.base import BaseVectorStoreBackend


_BACKEND_REGISTRY: dict[BackendType, type[BaseVectorStoreBackend]] = {}


def register_backend(backend_type: BackendType, backend_class: type[BaseVectorStoreBackend]) -> None:
    """Register ``backend_class`` under ``backend_type``.

    Idempotent: re-registering the same class is a no-op; re-registering a
    different class raises ``ValueError`` to catch accidental collisions.
    """
    existing = _BACKEND_REGISTRY.get(backend_type)
    if existing is not None and existing is not backend_class:
        msg = (
            f"Backend {backend_type.value!r} is already registered to "
            f"{existing.__name__}; refusing to overwrite with {backend_class.__name__}."
        )
        raise ValueError(msg)
    _BACKEND_REGISTRY[backend_type] = backend_class


def get_backend_class(backend_type: BackendType | str) -> type[BaseVectorStoreBackend]:
    """Look up the registered class for ``backend_type``.

    Accepts the enum or its string value (e.g. "chroma") for convenience at
    config-parsing boundaries.
    """
    resolved = _resolve_backend_type(backend_type)
    try:
        return _BACKEND_REGISTRY[resolved]
    except KeyError as exc:
        available = ", ".join(sorted(bt.value for bt in _BACKEND_REGISTRY))
        msg = (
            f"Vector-store backend {resolved.value!r} is not registered. Registered backends: {available or '<none>'}."
        )
        raise ValueError(msg) from exc


def registered_backends() -> tuple[BackendType, ...]:
    """Tuple of currently registered backend identifiers (stable ordering)."""
    return tuple(sorted(_BACKEND_REGISTRY, key=lambda bt: bt.value))


def create_backend(
    backend_type: BackendType | str,
    kb_name: str,
    kb_path: Path,
    *,
    backend_config: dict[str, Any] | None = None,
    embedding_function: Embeddings | None = None,
    user_id: UUID | str | None = None,
) -> BaseVectorStoreBackend:
    """Factory: build a backend instance for ``kb_name``.

    Parameters mirror ``BaseVectorStoreBackend.__init__``. Intended as the
    single entry point for KB helper code so swapping the default backend is a
    one-line change in ``kb_helpers``.

    ``user_id`` is forwarded so backends can resolve credential *variables*
    through Langflow's ``variable_service`` (same pattern as the connector
    ingestion sources). Legacy call sites that pass ``None`` still work —
    the backends fall back to ``os.environ`` in that case.

    For ``BackendType.CHROMA`` the factory dispatches to ``ChromaLocalBackend``
    or ``ChromaCloudBackend`` based on ``backend_config["mode"]`` so callers
    never need to know which class to use.
    """
    cfg = backend_config or {}
    resolved = _resolve_backend_type(backend_type)

    if resolved == BackendType.CHROMA:
        from lfx.base.knowledge_bases.backends.chroma import (
            ChromaCloudBackend,
            ChromaLocalBackend,
        )

        mode = str(cfg.get("mode", "local")).lower()
        backend_class: type[BaseVectorStoreBackend] = ChromaCloudBackend if mode == "cloud" else ChromaLocalBackend
    else:
        backend_class = get_backend_class(resolved)

    return backend_class(
        kb_name=kb_name,
        kb_path=kb_path,
        backend_config=backend_config,
        embedding_function=embedding_function,
        user_id=user_id,
    )


def _resolve_backend_type(value: BackendType | str) -> BackendType:
    """Coerce user-facing strings into a ``BackendType``.

    Raises ``ValueError`` with a helpful message on unknown values so config
    typos surface immediately rather than at vector-store build time.
    """
    if isinstance(value, BackendType):
        return value
    try:
        return BackendType(value)
    except ValueError as exc:
        allowed = ", ".join(bt.value for bt in BackendType)
        msg = f"Unknown vector-store backend {value!r}. Expected one of: {allowed}."
        raise ValueError(msg) from exc
