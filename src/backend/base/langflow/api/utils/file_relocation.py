"""Move uploaded file bytes to the target's object storage.

The bytes of an uploaded file live outside the database, so adopting the database
does not bring them. Each ``file`` row addresses its bytes as ``<user_id>/<name>``,
and both storage backends keep that logical pair; only the root differs, a local
directory on one side and a bucket and prefix on the other. So this copies each
file under the key it already has, and nothing in the database has to change.

Nothing is deleted from the source, and a file counts as copied only once the
target reports an object of the same size. Running it again skips what is already
there, so an interrupted run can be repeated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.database.models.file.model import File
from langflow.services.deps import get_session_service, get_settings_service, get_storage_service, session_scope
from langflow.services.storage.s3 import S3StorageService

if TYPE_CHECKING:
    from langflow.services.storage.service import StorageService

RelocationStatus = Literal["copied", "would_copy", "skipped", "failed"]


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
) -> list[FileRelocationResult]:
    """Copy every uploaded file's bytes into the target bucket.

    Returns one result per file and never raises for a single file's failure, so
    one unreadable file does not stop the rest.
    """
    source = get_storage_service()
    target = _target_storage(target_bucket, target_prefix, target_tags)
    files = await _uploaded_files(username)
    files += await _flow_scoped_files(source, username)

    results = []
    for owner, file_name, size in files:
        results.append(await _relocate_one(source, target, owner, file_name, size, dry_run=dry_run))
    await target.teardown()
    return results


async def _uploaded_files(username: str | None) -> list[tuple[str, str, int]]:
    """Each file as its storage address: the owner it is filed under, and the stored name.

    Readers resolve a file by ``(user_id, basename of path)``, so the copy uses the
    same pair rather than trusting the rest of ``path``, which has held more than
    one shape over the years.
    """
    from langflow.services.database.models.user.model import User

    async with session_scope() as session:
        statement = select(File.user_id, File.path, File.size)
        if username:
            statement = statement.join(User, User.id == File.user_id).where(User.username == username)
        rows = (await session.exec(statement)).all()
    return [(str(user_id), PurePosixPath(path).name, size) for user_id, path, size in rows]


async def _flow_scoped_files(source: StorageService, username: str | None) -> list[tuple[str, str, int]]:
    """Files uploaded to a flow, which have no row of their own.

    The v1 upload endpoint writes them under the flow id and records nothing, so
    the storage namespace is the only place they are listed. A flow that was
    deleted takes its namespace with it, and anything left behind is unreachable
    already, so this walks flows rather than directories.
    """
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User

    async with session_scope() as session:
        statement = select(Flow.id)
        if username:
            statement = statement.join(User, User.id == Flow.user_id).where(User.username == username)
        flow_ids = (await session.exec(statement)).all()

    files: list[tuple[str, str, int]] = []
    for flow_id in flow_ids:
        owner = str(flow_id)
        files.extend((owner, file_name, 0) for file_name in await source.list_files(flow_id=owner))
    return files


async def _relocate_one(
    source: StorageService,
    target: S3StorageService,
    owner: str,
    file_name: str,
    recorded_size: int,
    *,
    dry_run: bool,
) -> FileRelocationResult:
    result = FileRelocationResult(
        owner=owner,
        file_name=file_name,
        key=target.build_full_path(owner, file_name),
        status="failed",
        size=recorded_size,
    )
    try:
        existing = await _target_size(target, owner, file_name)
        data = await source.get_file(flow_id=owner, file_name=file_name)
        result.size = len(data)
        if existing is not None:
            # Already carried, or something else of the same name is there. Either way
            # this run must not overwrite it without saying so.
            if existing == len(data):
                result.status = "skipped"
                result.reason = "already in the target"
            else:
                result.reason = f"target already holds {existing} bytes under this key, a different size"
            return result
        if dry_run:
            result.status = "would_copy"
            return result

        await target.save_file(flow_id=owner, file_name=file_name, data=data)
        settled = await _target_size(target, owner, file_name)
        if settled != len(data):
            result.reason = f"target holds {settled} bytes of {len(data)} after the copy"
            return result
        result.status = "copied"
    except FileNotFoundError:
        # The row outlived its bytes. Reported rather than skipped: skipping reads as
        # "nothing to do" in a report a person uses to decide the move is complete.
        result.reason = "no bytes in the source storage"
    except Exception as exc:  # noqa: BLE001 - reported per file
        result.reason = f"{type(exc).__name__}: {exc}"
        await logger.awarning("Relocating file %s/%s failed: %s", owner, file_name, exc)
    return result


async def _target_size(target: S3StorageService, owner: str, file_name: str) -> int | None:
    """The size of the object already under this key, or None when there is none."""
    try:
        return await target.get_file_size(flow_id=owner, file_name=file_name)
    except FileNotFoundError:
        return None


def _target_storage(bucket: str, prefix: str, tags: dict[str, str] | None) -> S3StorageService:
    """An S3 storage service for the target, which is not the one this instance runs on.

    The service reads its bucket and prefix from settings, and the running instance's
    settings describe the source. So the target gets its own view of those few values
    while sharing everything else.
    """
    target_settings = get_settings_service().settings.model_copy(
        update={
            "storage_type": "s3",
            "object_storage_bucket_name": bucket,
            "object_storage_prefix": prefix,
            "object_storage_tags": tags,
        }
    )
    return S3StorageService(get_session_service(), _TargetSettingsService(target_settings))


@dataclass
class _TargetSettingsService:
    """Just enough of the settings service for a storage backend, which reads only ``settings``."""

    settings: object
