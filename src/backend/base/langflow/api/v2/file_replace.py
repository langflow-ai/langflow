"""Replace the content of a file the user already has in My Files."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile

from langflow.api.schemas import UploadFileResponse
from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v2.files import (
    _user_file_namespace,
    _validate_file_name,
    get_file_by_name,
    get_mcp_file,
    save_file_routine,
    upload_user_file,
)
from langflow.services.authorization import FileAction, ensure_file_permission
from langflow.services.authorization.credentials import ensure_mcp_credential_file_access
from langflow.services.settings.service import SettingsService
from langflow.services.storage.service import StorageService


async def replace_user_file(
    file: UploadFile,
    session: DbSession,
    current_user: CurrentActiveUser,
    storage_service: StorageService,
    settings_service: SettingsService,
) -> UploadFileResponse:
    """Store ``file`` as the new content of the user's file with the same name, or upload it when there is none.

    Write File's append mode re-uploads the whole accumulated file on every run,
    so it keeps one entry in My Files instead of adding a numbered copy each time.
    """
    new_filename = _validate_file_name(file.filename)
    root_filename = new_filename.rsplit(".", 1)[0] if "." in new_filename else new_filename
    existing_file = await get_file_by_name(root_filename, current_user, session)
    if (
        existing_file is None
        or new_filename == await get_mcp_file(current_user, extension=True)
        or Path(existing_file.path).suffix != Path(new_filename).suffix
    ):
        return await upload_user_file(
            file=file,
            session=session,
            current_user=current_user,
            storage_service=storage_service,
            settings_service=settings_service,
        )

    await ensure_file_permission(
        current_user, FileAction.WRITE, file_id=existing_file.id, file_user_id=existing_file.user_id
    )
    await ensure_mcp_credential_file_access(
        user_id=current_user.id, names=(existing_file.name, existing_file.path), session=session
    )
    max_megabytes = settings_service.settings.max_file_size_upload
    if file.size is not None and file.size > max_megabytes * 1024 * 1024:
        detail = f"File size is larger than the maximum file size {max_megabytes}MB."
        raise HTTPException(status_code=413, detail=detail)

    namespace = _user_file_namespace(existing_file.path, current_user.id)
    stored_file_name = Path(existing_file.path).name
    await save_file_routine(file, storage_service, current_user, file_name=stored_file_name, namespace=namespace)
    existing_file.size = await storage_service.get_file_size(flow_id=namespace, file_name=stored_file_name)
    existing_file.updated_at = datetime.now(timezone.utc)
    session.add(existing_file)
    await session.commit()
    await session.refresh(existing_file)
    return UploadFileResponse(
        id=existing_file.id, name=existing_file.name, path=existing_file.path, size=existing_file.size
    )
