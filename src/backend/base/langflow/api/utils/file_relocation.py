"""Copy uploaded file bytes into the target's object storage.

The bytes of an uploaded file live outside the database, so adopting the database
does not bring them. Storage addresses a file as ``<namespace>/<name>``, where the
namespace is the owning user for an upload and the flow for a file attached to one.
Both backends keep that pair and only the root differs, a local directory on one
side and a bucket and prefix on the other, so each file is copied under the key it
already has and nothing in the database changes.

What is copied is whatever the source holds, not whatever the ``file`` table lists.
Ephemeral chat attachments and v1 flow uploads have no row at all, and a row's
``path`` has held more than one shape over the years, so the storage namespace is
the authority here.

Nothing is deleted from the source, and a file counts as copied only once the
target reports an object of the same size. Running it again skips what is already
there, so an interrupted run can be repeated. "Already there" means the same size
and, where the target gives an MD5 cheaply, the same content; otherwise it is size
alone, and the report says so.

``plan_file`` and ``verify_file`` are the decision and the check on their own, for a
caller that has to show what would happen before anything moves.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

import anyio
from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session_service, get_settings_service, get_storage_service, session_scope
from langflow.services.settings.service import SettingsService
from langflow.services.storage.factory import StorageServiceFactory

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.services.storage.service import StorageService

RelocationStatus = Literal["copied", "would_copy", "skipped", "failed"]

# Read size for streaming a file across. The target buffers up to one multipart part.
_COPY_CHUNK = 1024 * 1024
DEFAULT_CONCURRENCY = 4


class SourceNotLocalError(Exception):
    """The instance is already running on object storage, so there is nothing local to read."""


class NoSuchUserError(Exception):
    """The ``username`` filter names a user this instance does not have."""


@dataclass
class FileRelocationResult:
    owner: str
    file_name: str
    key: str
    status: RelocationStatus
    size: int = 0
    reason: str | None = None


async def relocate_files(
    *,
    target_bucket: str,
    target_prefix: str = "",
    target_tags: dict[str, str] | None = None,
    username: str | None = None,
    dry_run: bool = False,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[FileRelocationResult]:
    """Copy every stored file's bytes into the target bucket.

    Returns one result per file and never raises for a single file's failure, so
    one unreadable file does not stop the rest. Raises before reading anything if
    the instance cannot be the source, or if ``username`` names nobody.

    Up to ``concurrency`` files are copied at once. Each streams across holding at
    most one multipart part (8 MiB) in memory, so memory scales with ``concurrency``
    alone.
    """
    _refuse_a_source_that_is_not_local()
    source = get_storage_service()
    namespaces = await _namespaces(username)
    target = _target_storage(target_bucket, target_prefix, target_tags)
    try:
        work = [(namespace, name) for namespace in namespaces for name in await _stored_names(source, namespace)]
        results: list[FileRelocationResult] = [None] * len(work)  # type: ignore[list-item]
        limiter = anyio.CapacityLimiter(max(1, concurrency))

        async def relocate(index: int, namespace: str, file_name: str) -> None:
            async with limiter:
                results[index] = await _relocate_one(source, target, namespace, file_name, dry_run=dry_run)

        async with anyio.create_task_group() as group:
            for index, (namespace, file_name) in enumerate(work):
                group.start_soon(relocate, index, namespace, file_name)
        results += await _rows_without_bytes(set(work), username)
    finally:
        await target.teardown()
    return results


def _refuse_a_source_that_is_not_local() -> None:
    """The files to copy are the ones on local disk, so the instance has to be reading them.

    Pointed at an instance already configured for object storage, every file would
    be reported missing while its bytes sat on the disk this run never looked at.
    """
    storage_type = get_settings_service().settings.storage_type
    if storage_type.lower() != "local":
        msg = (
            f"this instance is configured for '{storage_type}' storage, so it holds no local files to copy. "
            "Run it with LANGFLOW_STORAGE_TYPE=local, the setting the instance had before the switch"
        )
        raise SourceNotLocalError(msg)


async def _namespaces(username: str | None) -> list[str]:
    """Every id files can be filed under: each user, and each flow.

    Rows are not the authority on which files exist, but they are the authority on
    which namespaces belong to whom, which is what ``username`` filters on.
    """
    async with session_scope() as session:
        if username:
            user = (await session.exec(select(User).where(User.username == username))).first()
            if user is None:
                msg = f"no user named '{username}'"
                raise NoSuchUserError(msg)
            user_ids: list[UUID] = [user.id]
            flow_ids = list((await session.exec(select(Flow.id).where(Flow.user_id == user.id))).all())
        else:
            user_ids = list((await session.exec(select(User.id))).all())
            flow_ids = list((await session.exec(select(Flow.id))).all())
    return [str(identifier) for identifier in [*user_ids, *flow_ids]]


async def _rows_without_bytes(copied: set[tuple[str, str]], username: str | None) -> list[FileRelocationResult]:
    """Rows whose bytes the source does not hold.

    The copy walks storage, so a row like this has nothing to copy and would go
    unmentioned. It is the one thing a report of a completed move has to say: after
    this, the row resolves to nothing on either side, and the first person to learn
    that is whoever opens the flow that reads it.
    """
    async with session_scope() as session:
        statement = select(File.user_id, File.path)
        if username:
            statement = statement.join(User, User.id == File.user_id).where(User.username == username)
        rows = (await session.exec(statement)).all()

    missing = []
    for user_id, path in rows:
        address = (str(user_id), PurePosixPath(path).name)
        if address not in copied:
            missing.append(
                FileRelocationResult(
                    owner=address[0],
                    file_name=address[1],
                    key="",
                    status="failed",
                    reason="no bytes in the source storage",
                )
            )
    return missing


async def _stored_names(source: StorageService, namespace: str) -> list[str]:
    """The files under one namespace, skipping the namespaces that hold none.

    Listing a namespace that has no directory warns, which on an instance with many
    flows is a warning per flow and a report nobody can find under them.
    """
    if not await (anyio.Path(source.data_dir) / namespace).exists():
        return []
    return await source.list_files(flow_id=namespace)


@dataclass
class FilePlan:
    """What copying one file would do, decided before anything moves."""

    action: Literal["copy", "skip", "refuse"]
    key: str
    size: int
    reason: str | None = None


async def plan_file(source: StorageService, target: StorageService, namespace: str, file_name: str) -> FilePlan:
    """Decide what to do with one file without writing anything.

    Reads no bytes, except when the target already holds an object of the same size:
    a file edited between runs can keep its length, so the content is compared where
    the target gives a checksum cheaply. The source's own checksum is asked for first;
    only when it has none is the file hashed, a chunk at a time.
    """
    key = target.build_full_path(namespace, file_name)
    size = await source.get_file_size(flow_id=namespace, file_name=file_name)
    existing = await _target_size(target, namespace, file_name)
    if existing is None:
        return FilePlan("copy", key, size)
    if existing != size:
        # Something else of this name is there. Never overwritten without saying so.
        reason = (
            f"target already holds {existing} bytes under this key, a different size from the source's {size} bytes"
        )
        return FilePlan("refuse", key, size, reason)

    target_md5 = await target.get_file_md5(flow_id=namespace, file_name=file_name)
    if target_md5 is None:
        return FilePlan("skip", key, size, f"already in the target ({size} bytes, identity checked by size only)")
    source_md5 = await source.get_file_md5(flow_id=namespace, file_name=file_name)
    if source_md5 is None:
        source_md5 = await _streamed_md5(source, namespace, file_name)
    if source_md5 != target_md5:
        reason = f"target holds an object of the same size ({size} bytes) with different content"
        return FilePlan("refuse", key, size, reason)
    return FilePlan("skip", key, size, "already in the target")


async def _streamed_md5(source: StorageService, namespace: str, file_name: str) -> str:
    """The MD5 of a file, read a chunk at a time."""
    digest = hashlib.md5()  # noqa: S324 - compared with S3's ETag, not a security use
    async for chunk in source.get_file_stream(flow_id=namespace, file_name=file_name, chunk_size=_COPY_CHUNK):
        digest.update(chunk)
    return digest.hexdigest()


async def verify_file(target: StorageService, namespace: str, file_name: str, *, expected_size: int) -> str | None:
    """None when the target holds an object of the expected size, otherwise what is wrong with it."""
    settled = await _target_size(target, namespace, file_name)
    if settled is None:
        return f"target holds nothing under this key, {expected_size} bytes expected"
    if settled != expected_size:
        return f"target holds {settled} bytes of {expected_size} bytes"
    return None


async def _relocate_one(
    source: StorageService,
    target: StorageService,
    namespace: str,
    file_name: str,
    *,
    dry_run: bool,
) -> FileRelocationResult:
    result = FileRelocationResult(owner=namespace, file_name=file_name, key="", status="failed")
    try:
        # Inside the try: object storage rejects names that local disk once accepted,
        # and one such name must not end a run that still has files to copy.
        plan = await plan_file(source, target, namespace, file_name)
        result.key, result.size, result.reason = plan.key, plan.size, plan.reason
        if plan.action == "skip":
            result.status = "skipped"
            return result
        if plan.action == "refuse":
            return result
        if dry_run:
            result.status = "would_copy"
            return result

        chunks = source.get_file_stream(flow_id=namespace, file_name=file_name, chunk_size=_COPY_CHUNK)
        written = await target.save_file_stream(namespace, file_name, chunks)
        problem = await verify_file(target, namespace, file_name, expected_size=written)
        if problem:
            result.reason = f"{problem} after the copy"
            return result
        result.status = "copied"
    except FileNotFoundError:
        # Listed a moment ago and gone now. Reported rather than skipped: skipping
        # reads as "nothing to do" in a report someone uses to call the move complete.
        result.reason = "no bytes in the source storage"
    except Exception as exc:  # noqa: BLE001 - reported per file
        # The size makes a timeout on a large file recognisable in the report.
        size = f" ({result.size} bytes)" if result.size else ""
        result.reason = f"{type(exc).__name__}: {exc}{size}"
        await logger.awarning("Relocating file %s/%s failed: %s", namespace, file_name, exc)
    return result


async def _target_size(target: StorageService, namespace: str, file_name: str) -> int | None:
    """The size of the object already under this key, or None when there is none."""
    try:
        return await target.get_file_size(flow_id=namespace, file_name=file_name)
    except FileNotFoundError:
        return None


def _target_storage(bucket: str, prefix: str, tags: dict[str, str] | None) -> StorageService:
    """A storage backend for the target, which is not the one this instance runs on.

    A backend reads its bucket and prefix from settings, and this instance's settings
    describe the source, so the target gets its own copy of those few values and the
    usual factory builds the backend they describe.
    """
    settings_service = get_settings_service()
    target_settings = settings_service.settings.model_copy(
        update={
            "storage_type": "s3",
            "object_storage_bucket_name": bucket,
            "object_storage_prefix": prefix,
            "object_storage_tags": tags,
        }
    )
    return StorageServiceFactory().create(
        session_service=get_session_service(),
        settings_service=SettingsService(target_settings, settings_service.auth_settings),
    )
