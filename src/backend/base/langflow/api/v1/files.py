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


def _get_allowed_profile_picture_folders(settings_service: SettingsService) -> set[str]:
    """Return the set of allowed profile picture folders.

    This enumerates subdirectories under the profile_pictures directory in both
    the user's config_dir and the package's bundled assets. This makes the API
    flexible (users may add new folders under config_dir/profile_pictures) while
    still safe because we only ever serve files contained within the resolved
    base directory and validate path containment below.

    If no directories can be found (unexpected), fall back to the curated
    defaults {"People", "Space"} shipped with Langflow.
    """
    allowed: set[str] = set()
    try:
        # Config-provided folders
        config_dir = Path(settings_service.settings.config_dir)
        cfg_base = config_dir / "profile_pictures"
        if cfg_base.exists():
            allowed.update({p.name for p in cfg_base.iterdir() if p.is_dir()})
        # Package-provided folders
        from langflow.initial_setup import setup

        pkg_base = Path(setup.__file__).parent / "profile_pictures"
        if pkg_base.exists():
            allowed.update({p.name for p in pkg_base.iterdir() if p.is_dir()})
    except Exception as _:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Exception occurred while getting allowed profile picture folders")

    # Sensible defaults ensure tests and OOTB behavior
    return allowed or {"People", "Space"}


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
    # Return 404 for both non-existent flows and unauthorized access to prevent information disclosure
    if not flow or flow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.post("/upload/{flow_id}", status_code=HTTPStatus.CREATED)
async def upload_file(
    *,
    file: UploadFile,
    flow: Annotated[Flow, Depends(get_flow)],
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

    # Authorization handled by get_flow dependency
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
    file_name: str,
    flow: Annotated[Flow, Depends(get_flow)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    # Authorization handled by get_flow dependency
    flow_id_str = str(flow.id)
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
async def download_image(
    file_name: str,
    flow: Annotated[Flow, Depends(get_flow)],
):
    # Authorization handled by get_flow dependency
    storage_service = get_storage_service()
    extension = file_name.split(".")[-1]
    flow_id_str = str(flow.id)

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

    Profile pictures are first looked up in config_dir/profile_pictures/,
    then fallback to the package's bundled profile_pictures directory.
    """
    try:
        # SECURITY: Validate inputs to prevent path traversal attacks
        # Reject any path components that contain directory traversal sequences
        if ".." in folder_name or ".." in file_name:
            raise HTTPException(
                status_code=400, detail="Path traversal patterns ('..') are not allowed in folder or file names"
            )

        # Only allow specific folder names (dynamic from config + package)
        allowed_folders = _get_allowed_profile_picture_folders(settings_service)
        if folder_name not in allowed_folders:
            raise HTTPException(status_code=400, detail=f"Folder must be one of: {', '.join(sorted(allowed_folders))}")

        # Validate file name contains no path separators
        if "/" in file_name or "\\" in file_name:
            raise HTTPException(status_code=400, detail="File name cannot contain path separators ('/' or '\\')")

        extension = file_name.split(".")[-1]
        config_dir = settings_service.settings.config_dir
        config_path = Path(config_dir).resolve()  # type: ignore[arg-type]

        # Construct the file path
        file_path = (config_path / "profile_pictures" / folder_name / file_name).resolve()

        # SECURITY: Verify the resolved path is still within the allowed directory
        # This prevents path traversal even if symbolic links are involved
        allowed_base = (config_path / "profile_pictures").resolve()
        if not str(file_path).startswith(str(allowed_base)):
            # Return 404 to prevent path traversal attempts from revealing system structure
            raise HTTPException(status_code=404, detail="Profile picture not found")

        # Fallback to package bundled profile pictures if not found in config_dir
        if not file_path.exists():
            from langflow.initial_setup import setup

            package_base = Path(setup.__file__).parent / "profile_pictures"
            package_path = (package_base / folder_name / file_name).resolve()

            # SECURITY: Verify package path is also within allowed directory
            allowed_package_base = package_base.resolve()
            if not str(package_path).startswith(str(allowed_package_base)):
                # Return 404 to prevent path traversal attempts from revealing system structure
                raise HTTPException(status_code=404, detail="Profile picture not found")

            if package_path.exists():
                file_path = package_path
            else:
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

    Profile pictures are first looked up in config_dir/profile_pictures/,
    then fallback to the package's bundled profile_pictures directory.
    """
    try:
        config_dir = settings_service.settings.config_dir
        config_path = Path(config_dir)  # type: ignore[arg-type]

        # Build list for all allowed folders (dynamic)
        allowed_folders = _get_allowed_profile_picture_folders(settings_service)

        results: list[str] = []
        cfg_base = config_path / "profile_pictures"
        if cfg_base.exists():
            for folder in sorted(allowed_folders):
                p = cfg_base / folder
                if p.exists():
                    results += [f"{folder}/{f.name}" for f in p.iterdir() if f.is_file()]

        # Fallback to package if config_dir produced no results
        if not results:
            from langflow.initial_setup import setup

            package_base = Path(setup.__file__).parent / "profile_pictures"
            for folder in sorted(allowed_folders):
                p = package_base / folder
                if p.exists():
                    results += [f"{folder}/{f.name}" for f in p.iterdir() if f.is_file()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"files": results}


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
