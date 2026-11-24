"""Vector-store backend registry.

Built-in backends load lazily on selection. Extensions register classes with
``register_backend``. Call sites use ``create_backend`` without importing
provider SDKs themselves.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.backends.base import BackendType

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from langchain_core.embeddings import Embeddings

    from lfx.base.knowledge_bases.backends.base import BaseVectorStoreBackend
    from lfx.base.knowledge_bases.backends.sqlite import SQLiteStorageContext


_BACKEND_REGISTRY: dict[BackendType, type[BaseVectorStoreBackend]] = {}

# Resolve provider classes only when selected. In particular, importing the
# SQLite backend or inspecting capabilities must not import Chroma's SDK.
_BUILTIN_BACKENDS = {
    BackendType.SQLITE: ("sqlite", "SQLiteBackend"),
    BackendType.OPENSEARCH: ("opensearch", "OpenSearchBackend"),
    BackendType.POSTGRES: ("postgres", "PostgresBackend"),
}


def register_backend(backend_type: BackendType, backend_class: type[BaseVectorStoreBackend]) -> None:
    """Register ``backend_class`` under ``backend_type``.

    Idempotent: re-registering the same class is a no-op; re-registering a
    different class raises ``ValueError`` to catch accidental collisions.
    """
    if backend_type == BackendType.CHROMA:
        from lfx.base.knowledge_bases.backends.chroma import ChromaMigrationRequiredError

        raise ChromaMigrationRequiredError
    existing = _BACKEND_REGISTRY.get(backend_type)
    if existing is None and backend_type in _BUILTIN_BACKENDS:
        existing = get_backend_class(backend_type)
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
    if resolved == BackendType.CHROMA:
        from lfx.base.knowledge_bases.backends.chroma import ChromaMigrationRequiredError

        raise ChromaMigrationRequiredError
    if resolved not in _BACKEND_REGISTRY and resolved in _BUILTIN_BACKENDS:
        module_name, class_name = _BUILTIN_BACKENDS[resolved]
        module = import_module(f"lfx.base.knowledge_bases.backends.{module_name}")
        _BACKEND_REGISTRY[resolved] = getattr(module, class_name)
    try:
        return _BACKEND_REGISTRY[resolved]
    except KeyError as exc:
        available = ", ".join(bt.value for bt in registered_backends())
        msg = (
            f"Vector-store backend {resolved.value!r} is not registered. Registered backends: {available or '<none>'}."
        )
        raise ValueError(msg) from exc


def registered_backends() -> tuple[BackendType, ...]:
    """Tuple of currently registered backend identifiers (stable ordering)."""
    return tuple(sorted(_BACKEND_REGISTRY.keys() | _BUILTIN_BACKENDS.keys(), key=lambda bt: bt.value))


def is_local_backend(backend_type: BackendType | str | None, backend_config: dict[str, Any] | None) -> bool:
    """Whether this store depends on host-local storage.

    Missing legacy routing continues to mean local Chroma. Unknown routing
    fails closed rather than being mistaken for a deployable remote backend.
    This predicate does not load any optional provider SDK.
    """
    resolved = _resolve_backend_type(backend_type or BackendType.CHROMA)
    return resolved == BackendType.SQLITE or is_local_chroma(resolved, backend_config)


def is_local_chroma(backend_type: BackendType | str | None, backend_config: dict[str, Any] | None) -> bool:
    """True when this KB's vectors live in a local Chroma directory on this box.

    This legacy predicate identifies Chroma's display-name-based layout. Use
    ``is_local_backend`` for locality/production/deployment decisions, which
    must also account for SQLite's immutable identity-based layout.

    Cloud-vs-local is not visible in ``backend_type`` — both Chroma modes are
    stored as ``"chroma"`` and the discriminator is ``backend_config["mode"]``.
    That is why a bare ``backend_type == BackendType.CHROMA`` comparison is a bug:
    it reads a Chroma Cloud KB as local and then consults a directory that does
    not (and should not) exist.

    ``None``/missing ``backend_type`` resolves to Chroma for backwards
    compatibility with rows written before the backend selector existed.
    """
    resolved = backend_type or BackendType.CHROMA
    try:
        resolved = _resolve_backend_type(resolved)
    except ValueError:
        # An unknown backend string is certainly not local Chroma. Let the
        # caller's own resolution path surface the error with better context.
        return False
    if resolved != BackendType.CHROMA:
        return False
    return str((backend_config or {}).get("mode", "local")).lower() != "cloud"


def create_backend(
    backend_type: BackendType | str,
    kb_name: str,
    kb_path: Path | None = None,
    *,
    backend_config: dict[str, Any] | None = None,
    embedding_function: Embeddings | None = None,
    user_id: UUID | str | None = None,
    storage_context: SQLiteStorageContext | None = None,
    create: bool = False,
) -> BaseVectorStoreBackend:
    """Factory: build a backend instance for ``kb_name``.

    SQLite additionally requires trusted ``storage_context``. Its normal open
    path never creates a missing database. Only new-store creation or an
    unpublished migration generation may explicitly pass ``create=True``.

    SQLite derives its path from immutable storage context. Remote backends
    pass ``None`` for ``kb_path``. Legacy Chroma routing requires migration.

    ``user_id`` is forwarded so backends can resolve credential *variables*
    through Langflow's ``variable_service`` (same pattern as the connector
    ingestion sources). Legacy call sites that pass ``None`` still work —
    the backends fall back to ``os.environ`` in that case.

    Retired Chroma routing always raises a migration-required error.
    """
    resolved = _resolve_backend_type(backend_type)
    if resolved == BackendType.CHROMA:
        from lfx.base.knowledge_bases.backends.chroma import ChromaMigrationRequiredError

        raise ChromaMigrationRequiredError

    if resolved == BackendType.SQLITE:
        from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend

        if storage_context is None:
            msg = "SQLite requires trusted owner, KB and storage-generation context."
            raise ValueError(msg)
        return SQLiteBackend(
            kb_name=kb_name,
            kb_path=kb_path,
            backend_config=backend_config,
            embedding_function=embedding_function,
            user_id=user_id,
            storage_context=storage_context,
            create=create,
        )
    if storage_context is not None or create:
        msg = "Explicit local storage context and creation are supported only by SQLite."
        raise ValueError(msg)

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
