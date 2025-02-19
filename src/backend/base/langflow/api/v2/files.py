import re
import uuid
from collections.abc import AsyncGenerator
from http import HTTPStatus
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import String, cast, select

from langflow.api.schemas import UploadFileResponse
from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.file import File as UserFile
from langflow.services.deps import get_settings_service, get_storage_service
from langflow.services.storage.service import StorageService

router = APIRouter(tags=["Files"], prefix="/files")


async def byte_stream_generator(file_bytes: bytes, chunk_size: int = 8192) -> AsyncGenerator[bytes, None]:
    """Convert bytes object into an async generator that yields chunks."""
    for i in range(0, len(file_bytes), chunk_size):
        yield file_bytes[i : i + chunk_size]


async def fetch_file_object(file_id: uuid.UUID, current_user: CurrentActiveUser, session: DbSession):
    # Fetch the file from the DB
    stmt = select(UserFile).where(UserFile.id == file_id)
    results = await session.exec(stmt)
    file = results.first()

    # Check if the file exists
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Make sure the user has access to the file
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this file")

    return file


@router.post("", status_code=HTTPStatus.CREATED)
async def upload_user_file(
    file: Annotated[UploadFile, File(...)],
    session: DbSession,
    current_user: CurrentActiveUser,
    storage_service=Depends(get_storage_service),
    settings_service=Depends(get_settings_service),
) -> UploadFileResponse:
    """Upload a file for the current user and track it in the database."""
    # Get the max allowed file size from settings (in MB)
    try:
        max_file_size_upload = settings_service.settings.max_file_size_upload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Settings error: {e}") from e

    # Validate that a file is actually provided
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file size (convert MB to bytes)
    if file.size > max_file_size_upload * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File size is larger than the maximum file size {max_file_size_upload}MB.",
        )

    # Read file content and create a unique file name
    try:
        # Create a unique file name
        file_id = uuid.uuid4()
        file_content = await file.read()

        # Get file extension of the file
        file_extension = "." + file.filename.split(".")[-1] if file.filename and "." in file.filename else ""
        anonymized_file_name = f"{file_id!s}{file_extension}"

        # Here we use the current user's id as the folder name
        folder = str(current_user.id)
        # Save the file using the storage service.
        await storage_service.save_file(flow_id=folder, file_name=anonymized_file_name, data=file_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {e}") from e

    # Create a new database record for the uploaded file.
    try:
        # Enforce unique constraint on name
        # Name it as filename (1), (2), etc.
        # Check if the file name already exists
        new_filename = file.filename
        try:
            root_filename, _ = new_filename.rsplit(".", 1)
        except ValueError:
            root_filename, _ = new_filename, ""

        # Check if there are files with the same name
        stmt = select(UserFile).where(cast(UserFile.name, String).like(f"{root_filename}%"))
        existing_files = await session.exec(stmt)
        files = existing_files.all()  # Fetch all matching records

        # If there are files with the same name, append a count to the filename
        if files:
            counts = []

            # Extract the count from the filename
            for my_file in files:
                match = re.search(r"\((\d+)\)(?=\.\w+$|$)", my_file.name)  # Match (number) before extension or at end
                if match:
                    counts.append(int(match.group(1)))

            # Get the max count and increment by 1
            count = max(counts) if counts else 0  # Default to 0 if no matches found

            # Split the extension from the filename
            root_filename = f"{root_filename} ({count + 1})"

        # Compute the file size based on the path
        file_size = await storage_service.get_file_size(flow_id=folder, file_name=anonymized_file_name)

        # Compute the file path
        file_path = f"{folder}/{anonymized_file_name}"

        # Create a new file record
        new_file = UserFile(
            id=file_id,
            user_id=current_user.id,
            name=root_filename,
            path=file_path,
            size=file_size,
        )
        session.add(new_file)

        await session.commit()
        await session.refresh(new_file)
    except Exception as e:
        # Optionally, you could also delete the file from disk if the DB insert fails.
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    return UploadFileResponse(id=new_file.id, name=new_file.name, path=Path(new_file.path), size=new_file.size)


@router.get("")
async def list_files(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> list[UserFile]:
    """List the files available to the current user."""
    try:
        # Fetch from the UserFile table
        stmt = select(UserFile).where(UserFile.user_id == current_user.id)
        results = await session.exec(stmt)

        return list(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {e}") from e


@router.get("/{file_id}")
async def download_file(
    file_id: uuid.UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Download a file by its ID."""
    try:
        # Fetch the file from the DB
        file = await fetch_file_object(file_id, current_user, session)

        # Get the basename of the file path
        file_name = file.path.split("/")[-1]

        # Get file stream
        file_stream = await storage_service.get_file(flow_id=str(current_user.id), file_name=file_name)

        # Ensure file_stream is an async iterator returning bytes
        byte_stream = byte_stream_generator(file_stream)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {e}") from e

    # Return the file as a streaming response
    return StreamingResponse(
        byte_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file.name}"'},
    )


@router.put("/{file_id}")
async def edit_file_name(
    file_id: uuid.UUID,
    name: str,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> UploadFileResponse:
    """Edit the name of a file by its ID."""
    try:
        # Fetch the file from the DB
        file = await fetch_file_object(file_id, current_user, session)

        # Update the file name
        file.name = name
        await session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error editing file: {e}") from e

    return UploadFileResponse(id=file.id, name=file.name, path=file.path, size=file.size)


@router.delete("/{file_id}")
async def delete_file(
    file_id: uuid.UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Delete a file by its ID."""
    try:
        # Fetch the file from the DB
        file = await fetch_file_object(file_id, current_user, session)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # Delete the file from the storage service
        await storage_service.delete_file(flow_id=str(current_user.id), file_name=file.path)

        # Delete from the database
        await session.delete(file)
        await session.flush()  # Ensures delete is staged
        await session.commit()  # Commit deletion

    except Exception as e:
        await session.rollback()  # Rollback on failure
        raise HTTPException(status_code=500, detail=f"Error deleting file: {e}") from e

    return {"message": "File deleted successfully"}


@router.delete("")
async def delete_all_files(
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Delete all files for the current user."""
    try:
        # Fetch all files from the DB
        stmt = select(UserFile).where(UserFile.user_id == current_user.id)
        results = await session.exec(stmt)
        files = results.all()

        # Delete all files from the storage service
        for file in files:
            await storage_service.delete_file(flow_id=str(current_user.id), file_name=file.path)
            await session.delete(file)

        # Delete all files from the database
        await session.flush()  # Ensures delete is staged
        await session.commit()  # Commit deletion

    except Exception as e:
        await session.rollback()  # Rollback on failure
        raise HTTPException(status_code=500, detail=f"Error deleting files: {e}") from e

    return {"message": "All files deleted successfully"}
