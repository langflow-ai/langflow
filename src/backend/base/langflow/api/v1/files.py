import hashlib
from datetime import datetime, timezone
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from lfx.services.settings.service import SettingsService
from lfx.utils.helpers import build_content_type_from_extension

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas import UploadFileResponse
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service, get_storage_service
from langflow.services.storage.service import StorageService

router = APIRouter(tags=["Files"], prefix="/files")


# Create dep that gets the flow_id from the request
# then finds it in the database and returns it while
# using the current user as the owner
async def get_flow(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
):
    # AttributeError: 'SelectOfScalar' object has no attribute 'first'
    flow = await session.get(Flow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this flow")
    return flow


@router.post("/upload/{flow_id}", status_code=HTTPStatus.CREATED)
async def upload_file(
    *,
    file: UploadFile,
    flow: Annotated[Flow, Depends(get_flow)],
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> UploadFileResponse:
    try:
        max_file_size_upload = settings_service.settings.max_file_size_upload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if file.size > max_file_size_upload * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"File size is larger than the maximum file size {max_file_size_upload}MB."
        )

    if flow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this flow")

    try:
        file_content = await file.read()
        timestamp = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = file.filename or hashlib.sha256(file_content).hexdigest()
        full_file_name = f"{timestamp}_{file_name}"
        folder = str(flow.id)
        await storage_service.save_file(flow_id=folder, file_name=full_file_name, data=file_content)
        return UploadFileResponse(flow_id=str(flow.id), file_path=f"{folder}/{full_file_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/download/{flow_id}/{file_name}")
async def download_file(
    file_name: str, flow_id: UUID, storage_service: Annotated[StorageService, Depends(get_storage_service)]
):
    flow_id_str = str(flow_id)
    extension = file_name.split(".")[-1]

    if not extension:
        raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")
    try:
        content_type = build_content_type_from_extension(extension)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not content_type:
        raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")

    try:
        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        headers = {
            "Content-Disposition": f"attachment; filename={file_name} filename*=UTF-8''{file_name}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(file_content)),
        }
        return StreamingResponse(BytesIO(file_content), media_type=content_type, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/images/{flow_id}/{file_name}")
async def download_image(file_name: str, flow_id: UUID):
    storage_service = get_storage_service()
    extension = file_name.split(".")[-1]
    flow_id_str = str(flow_id)

    if not extension:
        raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")
    try:
        content_type = build_content_type_from_extension(extension)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not content_type:
        raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")
    if not content_type.startswith("image"):
        raise HTTPException(status_code=500, detail=f"Content type {content_type} is not an image")

    try:
        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        return StreamingResponse(BytesIO(file_content), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/profile_pictures/{folder_name}/{file_name}")
async def download_profile_picture(
    folder_name: str,
    file_name: str,
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    """Download profile picture from local filesystem.

    Profile pictures are always stored locally in config_dir/profile_pictures/,
    regardless of the storage_type setting (local, s3, etc.).
    """
    try:
        extension = file_name.split(".")[-1]
        config_dir = settings_service.settings.config_dir
        config_path = Path(config_dir)  # type: ignore[arg-type]
        file_path = config_path / "profile_pictures" / folder_name / file_name

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Profile picture {folder_name}/{file_name} not found")

        content_type = build_content_type_from_extension(extension)
        # Read file directly from local filesystem using async file operations
        file_content = await anyio.Path(file_path).read_bytes()
        return StreamingResponse(BytesIO(file_content), media_type=content_type)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/profile_pictures/list")
async def list_profile_pictures(
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    """List profile pictures from local filesystem.

    Profile pictures are always stored locally in config_dir/profile_pictures/,
    regardless of the storage_type setting (local, s3, etc.).
    """
    try:
        config_dir = settings_service.settings.config_dir
        config_path = Path(config_dir)  # type: ignore[arg-type]

        people_path = config_path / "profile_pictures" / "People"
        space_path = config_path / "profile_pictures" / "Space"

        # List files directly from local filesystem
        people = [f.name for f in people_path.iterdir() if f.is_file()] if people_path.exists() else []
        space = [f.name for f in space_path.iterdir() if f.is_file()] if space_path.exists() else []

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    files = [f"People/{i}" for i in people]
    files += [f"Space/{i}" for i in space]

    return {"files": files}


@router.get("/list/{flow_id}")
async def list_files(
    flow: Annotated[Flow, Depends(get_flow)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    try:
        files = await storage_service.list_files(flow_id=str(flow.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"files": files}


@router.delete("/delete/{flow_id}/{file_name}")
async def delete_file(
    file_name: str,
    flow: Annotated[Flow, Depends(get_flow)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    try:
        await storage_service.delete_file(flow_id=str(flow.id), file_name=file_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"message": f"File {file_name} deleted successfully"}
