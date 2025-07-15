import io
import re
import uuid
import zipfile
from collections.abc import AsyncGenerator, AsyncIterable
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlmodel import col, select

from langflow.api.schemas import UploadFileResponse
from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.deps import get_settings_service, get_storage_service
from langflow.services.storage.service import StorageService

router = APIRouter(tags=["Files"], prefix="/files")

# Set the static name of the MCP servers file
MCP_SERVERS_FILE = "_mcp_servers"
SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


async def byte_stream_generator(file_input, chunk_size: int = 8192) -> AsyncGenerator[bytes, None]:
    """Convert bytes object or stream into an async generator that yields chunks."""
    if isinstance(file_input, bytes):
        # Handle bytes object
        for i in range(0, len(file_input), chunk_size):
            yield file_input[i : i + chunk_size]
    # Handle stream object
    elif hasattr(file_input, "read"):
        while True:
            chunk = await file_input.read(chunk_size) if callable(file_input.read) else file_input.read(chunk_size)
            if not chunk:
                break
            yield chunk
    else:
        # Handle async iterator
        async for chunk in file_input:
            yield chunk


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


async def save_file_routine(file, storage_service, current_user: CurrentActiveUser, file_content=None, file_name=None):
    """Routine to save the file content to the storage service."""
    file_id = uuid.uuid4()

    if not file_content:
        file_content = await file.read()
    if not file_name:
        file_name = file.filename

    # Save the file using the storage service.
    await storage_service.save_file(flow_id=str(current_user.id), file_name=file_name, data=file_content)

    return file_id, file_name


@router.post("", status_code=HTTPStatus.CREATED)
@router.post("/", status_code=HTTPStatus.CREATED)
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
        max_file_size_upload = settings_service.server.max_file_size_upload
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

    # Create a new database record for the uploaded file.
    try:
        # Enforce unique constraint on name, except for the special _mcp_servers file
        new_filename = file.filename
        try:
            root_filename, file_extension = new_filename.rsplit(".", 1)
        except ValueError:
            root_filename, file_extension = new_filename, ""

        # Special handling for the MCP servers config file: always keep the same root filename
        if root_filename == MCP_SERVERS_FILE:
            # Check if an existing record exists; if so, delete it to replace with the new one
            existing_mcp_file = await get_file_by_name(root_filename, current_user, session)
            if existing_mcp_file:
                await delete_file(existing_mcp_file.id, current_user, session, storage_service)
            unique_filename = new_filename
        else:
            # For normal files, ensure unique name by appending a count if necessary
            stmt = select(UserFile).where(col(UserFile.name).like(f"{root_filename}%"))
            existing_files = await session.exec(stmt)
            files = existing_files.all()  # Fetch all matching records

            if files:
                counts = []

                # Extract the count from the filename
                for my_file in files:
                    match = re.search(r"\((\d+)\)(?=\.\w+$|$)", my_file.name)
                    if match:
                        counts.append(int(match.group(1)))

                count = max(counts) if counts else 0
                root_filename = f"{root_filename} ({count + 1})"

            # Create the unique filename with extension for storage
            unique_filename = f"{root_filename}.{file_extension}" if file_extension else root_filename

        # Read file content and save with unique filename
        try:
            file_id, stored_file_name = await save_file_routine(
                file, storage_service, current_user, file_name=unique_filename
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving file: {e}") from e

        # Compute the file size based on the path
        file_size = await storage_service.get_file_size(
            flow_id=str(current_user.id),
            file_name=stored_file_name,
        )

        # Create a new file record
        new_file = UserFile(
            id=file_id,
            user_id=current_user.id,
            name=root_filename,
            path=f"{current_user.id}/{stored_file_name}",
            size=file_size,
        )
        session.add(new_file)

        await session.commit()
        await session.refresh(new_file)
    except Exception as e:
        # Optionally, you could also delete the file from disk if the DB insert fails.
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    return UploadFileResponse(id=new_file.id, name=new_file.name, path=Path(new_file.path), size=new_file.size)


async def get_file_by_name(
    file_name: str,  # The name of the file to search for
    current_user: CurrentActiveUser,
    session: DbSession,
) -> UserFile | None:
    """Get the file associated with a given file name for the current user."""
    try:
        # Fetch from the UserFile table
        stmt = select(UserFile).where(UserFile.user_id == current_user.id).where(UserFile.name == file_name)
        result = await session.exec(stmt)

        return result.first() or None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching file: {e}") from e


async def load_sample_files(current_user: CurrentActiveUser, session: DbSession, storage_service: StorageService):
    # Check if the sample files in the SAMPLE_DATA_DIR exist
    for sample_file_path in Path(SAMPLE_DATA_DIR).iterdir():
        sample_file_name = sample_file_path.name
        root_filename, _ = sample_file_name.rsplit(".", 1)

        # Check if the sample file exists in the storage service
        existing_sample_file = await get_file_by_name(
            file_name=root_filename, current_user=current_user, session=session
        )
        if existing_sample_file:
            continue

        # Read the binary data of the sample file
        binary_data = sample_file_path.read_bytes()

        # Write the sample file content to the storage service
        file_id, _ = await save_file_routine(
            sample_file_path,
            storage_service,
            current_user,
            file_content=binary_data,
            file_name=sample_file_name,
        )
        file_size = await storage_service.get_file_size(
            flow_id=str(current_user.id),
            file_name=sample_file_name,
        )
        # Create a UserFile object for the sample file
        sample_file = UserFile(
            id=file_id,
            user_id=current_user.id,
            name=root_filename,
            path=sample_file_name,
            size=file_size,
        )

        session.add(sample_file)

        await session.commit()
        await session.refresh(sample_file)


@router.get("")
@router.get("/", status_code=HTTPStatus.OK)
async def list_files(
    current_user: CurrentActiveUser,
    session: DbSession,
    # storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> list[UserFile]:
    """List the files available to the current user."""
    try:
        # Load sample files if they don't exist
        # TODO: Pending further testing
        # await load_sample_files(current_user, session, get_storage_service())
        # Fetch from the UserFile table
        stmt = select(UserFile).where(UserFile.user_id == current_user.id)
        results = await session.exec(stmt)

        full_list = list(results)

        # Filter out the _mcp_servers file
        return [file for file in full_list if file.name != MCP_SERVERS_FILE]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {e}") from e


@router.delete("/batch/", status_code=HTTPStatus.OK)
async def delete_files_batch(
    file_ids: list[uuid.UUID],
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Delete multiple files by their IDs."""
    try:
        # Fetch all files from the DB
        stmt = select(UserFile).where(col(UserFile.id).in_(file_ids), col(UserFile.user_id) == current_user.id)
        results = await session.exec(stmt)
        files = results.all()

        if not files:
            raise HTTPException(status_code=404, detail="No files found")

        # Delete all files from the storage service
        for file in files:
            await storage_service.delete_file(flow_id=str(current_user.id), file_name=file.path)
            await session.delete(file)

        # Delete all files from the database
        await session.commit()  # Commit deletion

    except Exception as e:
        await session.rollback()  # Rollback on failure
        raise HTTPException(status_code=500, detail=f"Error deleting files: {e}") from e

    return {"message": f"{len(files)} files deleted successfully"}


@router.post("/batch/", status_code=HTTPStatus.OK)
async def download_files_batch(
    file_ids: list[uuid.UUID],
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Download multiple files as a zip file by their IDs."""
    try:
        # Fetch all files from the DB
        stmt = select(UserFile).where(col(UserFile.id).in_(file_ids), col(UserFile.user_id) == current_user.id)
        results = await session.exec(stmt)
        files = results.all()

        if not files:
            raise HTTPException(status_code=404, detail="No files found")

        # Create a byte stream to hold the ZIP file
        zip_stream = io.BytesIO()

        # Create a ZIP file
        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            for file in files:
                # Get the file content from storage
                file_content = await storage_service.get_file(
                    flow_id=str(current_user.id), file_name=file.path.split("/")[-1]
                )

                # Get the file extension from the original filename
                file_extension = Path(file.path).suffix
                # Create the filename with extension
                filename_with_extension = f"{file.name}{file_extension}"

                # Write the file to the ZIP with the proper extension
                zip_file.writestr(filename_with_extension, file_content)

        # Seek to the beginning of the byte stream
        zip_stream.seek(0)

        # Generate the filename with the current datetime
        current_time = datetime.now(tz=ZoneInfo("UTC")).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_langflow_files.zip"

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading files: {e}") from e


async def read_file_content(file_stream: AsyncIterable[bytes] | bytes, *, decode: bool = True) -> str | bytes:
    """Read file content from a stream or bytes into a string or bytes.

    Args:
        file_stream: An async iterable yielding bytes or a bytes object.
        decode: If True, decode the content to UTF-8; otherwise, return bytes.

    Returns:
        The file content as a string (if decode=True) or bytes.

    Raises:
        ValueError: If the stream yields non-bytes chunks.
        HTTPException: If decoding fails or an error occurs while reading.
    """
    content = b""
    try:
        if isinstance(file_stream, bytes):
            content = file_stream
        else:
            async for chunk in file_stream:
                if not isinstance(chunk, bytes):
                    msg = "File stream must yield bytes"
                    raise TypeError(msg)
                content += chunk
        if not decode:
            return content
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=500, detail="Invalid file encoding") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Error reading file: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error reading file: {exc}") from exc


@router.get("/{file_id}")
async def download_file(
    file_id: uuid.UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    *,
    return_content: bool = False,
):
    """Download a file by its ID or return its content as a string/bytes.

    Args:
        file_id: UUID of the file.
        current_user: Authenticated user.
        session: Database session.
        storage_service: File storage service.
        return_content: If True, return raw content (str) instead of StreamingResponse.

    Returns:
        StreamingResponse for client downloads or str for internal use.
    """
    try:
        # Fetch the file from the DB
        file = await fetch_file_object(file_id, current_user, session)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # Get the basename of the file path
        file_name = file.path.split("/")[-1]

        # Get file stream
        file_stream = await storage_service.get_file(flow_id=str(current_user.id), file_name=file_name)

        if file_stream is None:
            raise HTTPException(status_code=404, detail="File stream not available")

        # If return_content is True, read the file content and return it
        if return_content:
            return await read_file_content(file_stream, decode=True)

        # For streaming, ensure file_stream is an async iterator returning bytes
        byte_stream = byte_stream_generator(file_stream)

        # Create the filename with extension
        file_extension = Path(file.path).suffix
        filename_with_extension = f"{file.name}{file_extension}"

        # Return the file as a streaming response
        return StreamingResponse(
            byte_stream,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename_with_extension}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {e}") from e


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
        # Fetch the file object
        file_to_delete = await fetch_file_object(file_id, current_user, session)
        if not file_to_delete:
            raise HTTPException(status_code=404, detail="File not found")

        # Delete the file from the storage service
        await storage_service.delete_file(flow_id=str(current_user.id), file_name=file_to_delete.path)

        # Delete from the database
        await session.delete(file_to_delete)
        await session.commit()

    except HTTPException:
        # Re-raise HTTPException to avoid being caught by the generic exception handler
        raise
    except Exception as e:
        # Log and return a generic server error
        logger.error("Error deleting file %s: %s", file_id, e)
        raise HTTPException(status_code=500, detail=f"Error deleting file: {e}") from e
    return {"detail": f"File {file_to_delete.name} deleted successfully"}


@router.delete("")
@router.delete("/", status_code=HTTPStatus.OK)
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
        await session.commit()  # Commit deletion

    except Exception as e:
        await session.rollback()  # Rollback on failure
        raise HTTPException(status_code=500, detail=f"Error deleting files: {e}") from e

    return {"message": "All files deleted successfully"}
