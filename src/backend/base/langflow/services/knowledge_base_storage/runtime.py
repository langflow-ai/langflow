"""Owner-aware backend construction and whole-operation, cross-process fences.

The file lock is held until a complete async method or iterator drains. Local
storage is supported on a single host with a local filesystem, never NFS. A
context inherited by a child task does not confer ownership of its parent's lock.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import os
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from filelock import FileLock, Timeout
from lfx.base.knowledge_bases.backends import BackendType, create_backend
from lfx.base.knowledge_bases.backends.base import BackendConfigurationError, BaseVectorStoreBackend, IngestedDocument
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select

from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.deps import get_db_service, get_settings_service, session_scope

_held_locks: dict[tuple[int, object, UUID], _OperationLease] = {}
_pg_transactions: dict[tuple[int, object, str], _PostgresTransaction] = {}
# Leases run on the caller's event loop, so each loop gets its own coordination
# engine. ``test_knowledge_event_loop.py`` checks that the Knowledge component
# and the KB API never take a lease through ``run_until_complete`` or a new loop.
_coordination_engines: dict[tuple[int, str, object], Any] = {}
LOCK_TIMEOUT_SECONDS = 30.0
_READ_METHODS = frozenset(
    {
        "similarity_search",
        "asimilarity_search",
        "asimilarity_search_with_score",
        "count",
        "iter_documents",
        "storage_size_bytes",
        "read_migration_manifest",
        "integrity_check",
    }
)


@dataclass
class _OperationLease:
    """Live ownership survives finalization in a different task/context."""

    owner: tuple[int, object, UUID]
    release: Any
    shared: bool = False
    users: int = 0
    active: bool = True


@dataclass
class _PostgresTransaction:
    owner: tuple[int, object, str]
    manager: Any
    connection: Any
    users: int = 0
    active: bool = True


def _owner(kb_id: UUID) -> tuple[int, object, UUID]:
    """Identify lock ownership by process, asyncio task and immutable KB UUID."""
    return os.getpid(), asyncio.current_task(), kb_id


@asynccontextmanager
async def _use_lease(lease: _OperationLease):
    """Retain a live lease until its final nested operation releases it."""
    lease.users += 1
    try:
        yield
    finally:
        lease.users -= 1
        if not lease.users:
            lease.active = False
            if _held_locks.get(lease.owner) is lease:
                del _held_locks[lease.owner]
            # Ownership cannot remain stale even if releasing the actual lock
            # fails. In that case subsequent callers must acquire it afresh.
            await lease.release()


async def _drain_cleanup(awaitable):
    """Finish asynchronous resource cleanup before propagating cancellation."""
    task = asyncio.ensure_future(awaitable)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            if not cancelled:
                raise
    if cancelled:
        task.exception()
        raise asyncio.CancelledError
    return task.result()


async def _release_transaction(transaction: _PostgresTransaction) -> None:
    """Close the coordination transaction when its last lease is released."""
    transaction.users -= 1
    if not transaction.users:
        transaction.active = False
        if _pg_transactions.get(transaction.owner) is transaction:
            del _pg_transactions[transaction.owner]
        await _drain_cleanup(transaction.manager.__aexit__(None, None, None))


async def _wait_for_lock(deadline: float) -> None:
    """Bound contention without blocking the event loop."""
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        msg = "Knowledge base storage is busy. Retry the operation."
        raise StorageUnavailableError(msg)
    await asyncio.sleep(min(0.05, remaining))


def _check_lease_mode(lease: _OperationLease, *, shared: bool) -> None:
    """Reject a nested write that attempts to upgrade an existing shared lease."""
    if lease.shared and not shared:
        msg = "Cannot upgrade a shared storage operation to a write operation"
        raise StorageUnavailableError(msg)


@asynccontextmanager
async def _file_operation_lock(kb_id: UUID, path: Path, *, shared: bool = False):
    """Acquire a bounded local read or write lease and retain it through finalization."""
    owner = _owner(kb_id)
    existing = _held_locks.get(owner)
    if existing is not None and existing.active:
        _check_lease_mode(existing, shared=shared)
        async with _use_lease(existing):
            yield
        return
    if path.is_symlink():
        msg = "Invalid storage lock path"
        raise StorageUnavailableError(msg)
    deadline = asyncio.get_running_loop().time() + LOCK_TIMEOUT_SECONDS
    if os.name == "posix":
        import fcntl

        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        leased = False
        try:
            while True:
                try:
                    fcntl.flock(descriptor, mode | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await _wait_for_lock(deadline)

            async def release():
                """Unlock and close the descriptor owned by this storage lease."""
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)

            lease = _OperationLease(owner, release, shared=shared)
            _held_locks[owner] = lease
            leased = True
            async with _use_lease(lease):
                yield
        finally:
            if not leased:
                os.close(descriptor)
    else:
        # Windows FileLock preserves the exclusive lifecycle fence.
        lock = FileLock(path, thread_local=False)
        while True:
            try:
                lock.acquire(timeout=0)
                break
            except Timeout:
                await _wait_for_lock(deadline)

        async def release():
            """Release the process-local storage lock."""
            lock.release()

        lease = _OperationLease(owner, release, shared=shared)
        _held_locks[owner] = lease
        async with _use_lease(lease):
            yield


class StorageUnavailableError(ValueError):
    """A missing, fenced or superseded KB cannot be accessed as an empty store."""

    status_code = 409


def storage_unavailable_message(state: str) -> str:
    """Give flow and API callers the same actionable availability message."""
    if state == "detached":
        return (
            "Storage for this base was detached. Contact your administrator to recover it, or "
            "delete the base and create a replacement."
        )
    if state in ("deleting", "deleted"):
        return "This base is being deleted and is unavailable."
    if state == "migrating":
        return (
            "This knowledge or memory base is upgrading automatically. Wait for the upgrade to "
            "finish, then try again. Progress is shown in Langflow."
        )
    return (
        "This knowledge or memory base needs a storage upgrade. Your original data is "
        "preserved. Open the upgrade notice in Langflow, or contact your administrator."
    )


def storage_root() -> Path:
    """Resolve the configured local storage root independently of display names."""
    configured = get_settings_service().settings.knowledge_bases_dir
    if not configured:
        msg = "Knowledge base storage directory is not configured"
        raise StorageUnavailableError(msg)
    return Path(configured).expanduser().resolve()


def private_directory(path: Path) -> Path:
    """Create trusted internal directories without accepting child symlinks."""
    root = storage_root()
    if not path.is_relative_to(root):
        msg = "Storage path escapes its configured root"
        raise StorageUnavailableError(msg)
    for candidate in (root, *reversed(list(path.parents)[: len(path.relative_to(root).parts) - 1]), path):
        if candidate.is_symlink():
            msg = "Knowledge base storage cannot use symbolic links"
            raise StorageUnavailableError(msg)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


@asynccontextmanager
async def exclusive_lock(kb_id: UUID):
    """Serialize all processes and tasks, including migration and deletion."""
    directory = private_directory(storage_root() / ".locks")
    path = directory / f"{UUID(str(kb_id))}.lock"
    async with _file_operation_lock(kb_id, path):
        yield


@asynccontextmanager
async def shared_lock(kb_id: UUID):
    """Allow concurrent local readers while excluding migration and deletion."""
    directory = private_directory(storage_root() / ".locks")
    async with _file_operation_lock(kb_id, directory / f"{UUID(str(kb_id))}.lock", shared=True):
        yield


async def resolve_record(user_id: UUID, name: str) -> KnowledgeBaseRecord:
    """Load owner-scoped routing or reject a KB that no longer exists."""
    async with session_scope() as session:
        row = (
            await session.exec(
                select(KnowledgeBaseRecord).where(
                    KnowledgeBaseRecord.user_id == user_id, KnowledgeBaseRecord.name == name
                )
            )
        ).first()
    if row is None:
        msg = "Knowledge base no longer exists"
        raise StorageUnavailableError(msg)
    return row


@asynccontextmanager
async def operation(record_or_id, *, allowed_states=("ready",), shared=False):
    """Fence a complete operation and reject changed generations or unavailable routing."""
    kb_id = record_or_id.id if isinstance(record_or_id, KnowledgeBaseRecord) else UUID(str(record_or_id))
    async with session_scope() as session:
        initial = await session.get(KnowledgeBaseRecord, kb_id)
    if initial is None:
        msg = "Knowledge base no longer exists"
        raise StorageUnavailableError(msg)
    if initial.storage_state not in allowed_states:
        # Migration holds the exclusive lease through verification. Return
        # useful progress immediately instead of waiting for that lease.
        msg = storage_unavailable_message(initial.storage_state)
        raise StorageUnavailableError(msg)
    local = initial.backend_type == "sqlite" or (
        initial.backend_type == "chroma" and initial.backend_config.get("mode", "local") == "local"
    )
    local_lock = shared_lock if shared else exclusive_lock
    async with local_lock(kb_id) if local else _remote_lock(kb_id, shared=shared):
        async with session_scope() as session:
            current = await session.get(KnowledgeBaseRecord, kb_id)
        if current is None:
            msg = "Knowledge base no longer exists"
            raise StorageUnavailableError(msg)
        if current.storage_state not in allowed_states:
            msg = storage_unavailable_message(current.storage_state)
            raise StorageUnavailableError(msg)
        if isinstance(record_or_id, KnowledgeBaseRecord) and (
            current.storage_generation != record_or_id.storage_generation
            or current.backend_type != record_or_id.backend_type
            or current.user_id != record_or_id.user_id
            or current.backend_config != record_or_id.backend_config
        ):
            msg = "Knowledge base storage changed. Retry with its current routing."
            raise StorageUnavailableError(msg)
        yield current


@asynccontextmanager
async def _remote_lock(kb_id: UUID, *, shared=False):
    """Postgres advisory transaction locks coordinate remote-store replicas."""
    owner = _owner(kb_id)
    existing = _held_locks.get(owner)
    if existing is not None and existing.active:
        _check_lease_mode(existing, shared=shared)
        async with _use_lease(existing):
            yield
        return
    database = get_db_service()
    if database.database_url.startswith(("postgres", "postgresql")):
        deadline = asyncio.get_running_loop().time() + LOCK_TIMEOUT_SECONDS
        query = text(
            "SELECT pg_try_advisory_xact_lock_shared(:key)" if shared else "SELECT pg_try_advisory_xact_lock(:key)"
        )
        key = int.from_bytes(hashlib.sha256(kb_id.bytes).digest()[:8], "big", signed=True)
        # Advisory locks must not consume the app pool while their holder
        # needs that same pool to read routing or resolve credentials. Keep a
        # separate bounded pool, recreated after fork and per event loop.
        engine_key = (os.getpid(), database.database_url, asyncio.get_running_loop())
        engine = _coordination_engines.get(engine_key)
        if engine is None:
            engine = create_async_engine(
                database.database_url,
                pool_size=getattr(get_settings_service().settings, "knowledge_base_storage_pool_size", 20),
                max_overflow=0,
                pool_timeout=30,
                connect_args=database._get_connect_args(),  # noqa: SLF001 -- preserve configured driver TLS options
            )
            _coordination_engines[engine_key] = engine
        transaction_owner = (os.getpid(), asyncio.current_task(), database.database_url)
        transaction = _pg_transactions.get(transaction_owner)
        if transaction is not None and not transaction.active:
            transaction = None
        if transaction is None:
            # The first KB releases the connection between unsuccessful tries.
            # Nested distinct KBs reuse this task's transaction, so any number
            # of sorted locks requires only one bounded-pool connection.
            while True:
                manager = engine.begin()
                try:
                    connection = await asyncio.wait_for(
                        manager.__aenter__(), max(0, deadline - asyncio.get_running_loop().time())
                    )
                except asyncio.TimeoutError as exc:
                    msg = "Knowledge base storage coordination is busy. Retry the operation."
                    raise StorageUnavailableError(msg) from exc
                try:
                    acquired = (await connection.execute(query, {"key": key})).scalar_one()
                except BaseException:
                    await _drain_cleanup(manager.__aexit__(None, None, None))
                    raise
                if acquired:
                    transaction = _PostgresTransaction(transaction_owner, manager, connection, users=1)
                    _pg_transactions[transaction_owner] = transaction
                    break
                await _drain_cleanup(manager.__aexit__(None, None, None))
                await _wait_for_lock(deadline)
        else:
            # Reserve ownership while acquisition awaits. Closing an outer
            # generator in another task cannot release this transaction early.
            transaction.users += 1
            try:
                while not (await transaction.connection.execute(query, {"key": key})).scalar_one():
                    await _wait_for_lock(deadline)
            except BaseException:
                await _release_transaction(transaction)
                raise

        async def release():
            """Release the transaction that owns the PostgreSQL storage lease."""
            await _release_transaction(transaction)

        lease = _OperationLease(owner, release, shared=shared)
        _held_locks[owner] = lease
        async with _use_lease(lease):
            yield
    else:
        # A SQLite application DB is itself single-host. Its directory is
        # configured even when this deployment has no local vector root.
        from langflow.services.database.service import get_sqlite_database_file_path

        database_path = get_sqlite_database_file_path(database.database_url)
        if database_path is None:
            msg = "Unsupported application database for storage coordination"
            raise StorageUnavailableError(msg)
        directory = database_path.parent / ".kb-storage-locks"
        if directory.is_symlink():
            msg = "Invalid storage lock directory"
            raise StorageUnavailableError(msg)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / f"{kb_id}.lock"
        async with _file_operation_lock(kb_id, path, shared=shared):
            yield


def _raw_backend(record, *, embedding_function=None, create=False, credential_user_id=None):
    """Construct a provider backend from authoritative routing and trusted storage identity."""
    if record.backend_type == "chroma":
        msg = "This knowledge base requires the automatic SQLite upgrade before use"
        raise StorageUnavailableError(msg)
    kwargs: dict[str, Any] = {}
    if record.backend_type == "sqlite":
        kwargs = {
            "storage_context": SQLiteStorageContext(
                root=storage_root(), owner_id=record.user_id, kb_id=record.id, generation=record.storage_generation
            ),
            "create": create,
        }
    return create_backend(
        backend_type=BackendType(record.backend_type),
        kb_name=record.name,
        kb_path=None,
        backend_config=record.backend_config,
        embedding_function=embedding_function,
        user_id=credential_user_id or record.user_id,
        **kwargs,
    )


def unfenced_backend(record) -> BaseVectorStoreBackend:
    """Construct the backend a row routes to, without ``backend_for_record``'s storage fences.

    For an offline tool that does its own routing checks, such as ``langflow relocate-kb``.
    """
    return _raw_backend(record)


class _GuardedMethods:
    def __init__(self, target, record, *, before_write=None):
        """Capture the backend and routing snapshot used to guard future operations."""
        self._target = target
        self._record = record
        self._before_write = before_write

    def __getattr__(self, name):
        """Wrap asynchronous methods and iterators with the appropriate storage lease."""
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self._target, name)
        if name == "vector_store":
            return _GuardedMethods(value, self._record)
        if inspect.isasyncgenfunction(value):

            async def iterate(*args, **kwargs):
                """Hold a storage lease while yielding batches from an asynchronous iterator."""
                async with (
                    operation(self._record, shared=name in _READ_METHODS),
                    aclosing(value(*args, **kwargs)) as iterator,
                ):
                    async for batch in iterator:
                        yield batch

            return iterate
        if inspect.iscoroutinefunction(value):

            async def call(*args, **kwargs):
                # Teardown releases handles even after a migration fence appeared.
                """Route an asynchronous operation through the appropriate storage fence."""
                if name == "teardown":
                    return await value(*args, **kwargs)
                if (
                    name == "add_documents"
                    and isinstance(self._target, BaseVectorStoreBackend)
                    and type(self._target)._write_embedded is not BaseVectorStoreBackend._write_embedded  # noqa: SLF001 -- detect the optional extension hook without invoking it
                ):
                    documents = args[0] if args else kwargs["docs"]
                    if not documents:
                        return None
                    async with operation(self._record, shared=True):
                        pass
                    embeddings = self._target.embedding_function
                    if embeddings is None:
                        msg = "Knowledge base ingestion requires an embedding function"
                        raise BackendConfigurationError(msg)
                    vectors = await embeddings.aembed_documents([doc.page_content for doc in documents])
                    if len(vectors) != len(documents):
                        msg = "Embedding provider returned an incorrect number of vectors"
                        raise BackendConfigurationError(msg)
                    embedded = [
                        IngestedDocument(doc.page_content, doc.metadata, vector, id=doc.id)
                        for doc, vector in zip(documents, vectors, strict=True)
                    ]
                    async with operation(self._record):
                        if self._before_write is not None:
                            await self._before_write()
                        return await self._target.add_embedded_documents(embedded)
                read_only = name in _READ_METHODS or (
                    name == "ensure_ready" and not getattr(self._target, "_create", False)
                )
                async with operation(self._record, shared=read_only):
                    if self._before_write is not None and name in ("add_documents", "add_embedded_documents"):
                        await self._before_write()
                    return await value(*args, **kwargs)

            return call
        if callable(value) and name not in ("normalize_score",):

            def unsupported(*_args, **_kwargs):
                """Reject synchronous operations that cannot honor asynchronous storage fences."""
                msg = "Use asynchronous knowledge base operations so storage fences are honored"
                raise StorageUnavailableError(msg)

            return unsupported
        return value


async def backend_for_record(
    record, *, embedding_function=None, create=False, credential_user_id=None, before_write=None
):
    """Validate routing and initialize a guarded backend for its immutable generation."""
    async with operation(record, shared=not create) as current:
        backend = _raw_backend(
            current, embedding_function=embedding_function, create=create, credential_user_id=credential_user_id
        )
    return _GuardedMethods(backend, current, before_write=before_write)


async def backend_for_name(user_id, name, **kwargs):
    """Resolve owner-scoped routing before constructing a guarded backend."""
    return await backend_for_record(await resolve_record(user_id, name), **kwargs)


async def _erase_retired_sqlite_generations(record) -> None:
    """Erase owned routed and unpublished targets while their routing fence is held."""
    generations = {record.storage_generation} if record.backend_type == "sqlite" else set()
    if record.active_migration_id and (
        record.backend_type == "sqlite"
        or (record.backend_type == "chroma" and record.backend_config.get("mode", "local") == "local")
    ):
        async with session_scope() as session:
            run = await session.get(KnowledgeBaseStorageMigration, record.active_migration_id)
        if run is not None:
            if run.kb_id != record.id:
                msg = "Migration target does not belong to this knowledge base"
                raise StorageUnavailableError(msg)
            generations.add(run.target_generation)
    for generation in sorted(generations):
        backend = SQLiteBackend(
            record.name,
            storage_context=SQLiteStorageContext(storage_root(), record.user_id, record.id, generation),
        )
        try:
            await backend.delete_collection()
        except FileNotFoundError:
            pass  # No target was created, or this owned generation is already absent.
        finally:
            await backend.teardown()


async def delete_storage_for_record(record) -> None:
    """Drain old operations, persist the deletion fence, then tombstone the store.

    The caller may remove the metadata row afterwards. Failures remain deleting
    and retryable. The SQLite tombstone is retained, so missing-file recreation
    and stale workers cannot resurrect the deleted generation.
    """
    async with operation(
        record, allowed_states=("ready", "needs_attention", "detached", "deleting", "deleted")
    ) as current:
        if current.storage_state == "deleted":
            return
        if current.storage_state in ("needs_attention", "detached") or current.backend_type == "chroma":
            # Preserve retired provider sources, but erase application-owned
            # SQLite targets before releasing their routing identity.
            from langflow.services.knowledge_base_storage.coordinator import retire_legacy_source

            await retire_legacy_source(current)
            await _erase_retired_sqlite_generations(current)
            async with session_scope() as session:
                row = await session.get(KnowledgeBaseRecord, current.id)
                row.storage_state = "deleted"
                await session.commit()
            return
        backend = _raw_backend(current)
        try:
            if current.backend_type != "sqlite":
                await backend.ensure_ready()
        except BaseException:
            await backend.teardown()
            raise
        async with session_scope() as session:
            row = await session.get(KnowledgeBaseRecord, current.id)
            row.storage_state = "deleting"
            await session.commit()
        try:
            # Remote providers resolve credentials and clients before deletion.
            # SQLite opens tombstoned generations only through delete_collection
            # so a retry must not call its ordinary ready-state check first.
            await backend.delete_collection()
        except FileNotFoundError:
            # Explicit deletion may retire an already absent local generation.
            # Reads and writes still fail closed on the same missing file.
            if current.backend_type != "sqlite":
                raise
        finally:
            await backend.teardown()
        async with session_scope() as session:
            row = await session.get(KnowledgeBaseRecord, current.id)
            row.storage_state = "deleted"
            await session.commit()


async def delete_orphaned_storage(record) -> None:
    """Tombstone a trusted local generation captured before owner-row cascading deletion."""
    if record.backend_type != "sqlite":
        msg = "Orphan cleanup requires a local SQLite generation"
        raise StorageUnavailableError(msg)
    async with exclusive_lock(record.id):
        async with session_scope() as session:
            if await session.get(KnowledgeBaseRecord, record.id) is not None:
                msg = "Knowledge base still exists. Use its guarded deletion operation"
                raise StorageUnavailableError(msg)
        backend = _raw_backend(record)
        try:
            await backend.delete_collection()
        except FileNotFoundError:
            pass  # The orphaned local generation is already absent.
        finally:
            await backend.teardown()


async def close_coordination_pools() -> None:
    """Dispose coordination engines during application shutdown."""
    for key, engine in tuple(_coordination_engines.items()):
        if key[0] == os.getpid() and key[2] is asyncio.get_running_loop():
            await engine.dispose()
            del _coordination_engines[key]
