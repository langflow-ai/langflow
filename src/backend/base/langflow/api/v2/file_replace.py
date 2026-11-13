"""Keep the My Files entry of a file that Write File appends to in place."""

from datetime import datetime, timezone
from pathlib import Path

from lfx.utils.file_path_security import user_storage_scope
from sqlmodel import select

from langflow.api.schemas import UploadFileResponse
from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v2.files import _release_restricted_file_reads
from langflow.services.authorization import FileAction, ensure_file_permission
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.storage.local import LocalStorageService
from langflow.services.storage.service import StorageService


async def record_appended_user_file(
    file_path: Path,
    session: DbSession,
    current_user: CurrentActiveUser,
    storage_service: StorageService,
) -> UploadFileResponse | None:
    """Update the entry whose stored file is ``file_path``; None when no entry stores that very file.

    Only a file the entry already stores is safe to record: any other local copy
    (remote storage, another folder) never held the entry's content, so uploading
    it over the entry would lose data.
    """
    if not isinstance(storage_service, LocalStorageService):
        return None
    namespace = user_storage_scope(current_user.id)
    stored = Path(storage_service.build_full_path(namespace, file_path.name))
    if stored.resolve() != file_path.resolve():
        return None
    statement = select(UserFile).where(
        UserFile.user_id == current_user.id, UserFile.path == f"{namespace}/{file_path.name}"
    )
    entry = (await session.exec(statement)).first()
    if entry is None:
        return None
    await _release_restricted_file_reads(session, entry)
    await ensure_file_permission(current_user, FileAction.WRITE, file_id=entry.id, file_user_id=entry.user_id)
    entry.size = file_path.stat().st_size
    entry.updated_at = datetime.now(timezone.utc)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return UploadFileResponse(id=entry.id, name=entry.name, path=entry.path, size=entry.size)
