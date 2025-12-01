import io
import re
import uuid
import zipfile
from collections.abc import AsyncGenerator, AsyncIterable
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.api.schemas import UploadFileResponse
from langflow.api.utils import CurrentActiveUser, DbSession, is_file_used
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service, get_storage_service
from langflow.services.settings.service import SettingsService
from langflow.services.storage.service import StorageService

router = APIRouter(tags=["Files"], prefix="/files")

# Set the static name of the MCP servers file
MCP_SERVERS_FILE = "_mcp_servers"
SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"

# Maximum allowed filename length
MAX_FILENAME_LENGTH = 255
# Maximum reasonable extension length
MAX_EXTENSION_LENGTH = 20


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and other security issues.

    Args:
        filename: The original filename from user input

    Returns:
        A sanitized filename safe for storage and headers
    """
    if not filename:
        return "unnamed"

    # Strip any path components to prevent path traversal (e.g., ../../etc/passwd)
    base_filename = Path(filename).name

    # Replace dangerous characters: control chars, path separators, quotes, etc.
    # Keep only alphanumeric, spaces, dots, hyphens, underscores, and parentheses
    safe_filename = re.sub(r"[^\w.\- ()]", "_", base_filename)

    # Remove leading/trailing whitespace and dots (prevent hidden files)
    safe_filename = safe_filename.strip().strip(".")

    # Ensure we have a valid filename
    if not safe_filename:
        return "unnamed"

    # Truncate to max length while preserving extension
    if len(safe_filename) > MAX_FILENAME_LENGTH:
        name_part, _, ext = safe_filename.rpartition(".")
        if ext and len(ext) < MAX_EXTENSION_LENGTH:
            max_name_len = MAX_FILENAME_LENGTH - len(ext) - 1
            safe_filename = f"{name_part[:max_name_len]}.{ext}"
        else:
            safe_filename = safe_filename[:MAX_FILENAME_LENGTH]

    return safe_filename


def sanitize_content_disposition(filename: str) -> str:
    """Create a safe Content-Disposition header value.

    Uses RFC 5987 encoding for non-ASCII characters and escapes special chars.

    Args:
        filename: The filename to include in the header

    Returns:
        A properly formatted Content-Disposition header value
    """
    # First sanitize the filename
    safe_name = sanitize_filename(filename)

    # Check if filename contains non-ASCII or special characters
    try:
        safe_name.encode("ascii")
    except UnicodeEncodeError:
        # Contains non-ASCII: use RFC 5987 encoding
        encoded = quote(safe_name, safe="")
        return f"attachment; filename*=UTF-8''{encoded}"
    else:
        # ASCII-safe: use simple quoted format, escape quotes
        escaped = safe_name.replace("\\", "\\\\").replace('"', '\\"')
        return f'attachment; filename="{escaped}"'


def is_permanent_storage_failure(error: Exception) -> bool:
    """Check if a storage deletion error is a permanent failure (file/storage gone).

    Permanent failures are safe to delete from DB because the file/storage is already gone.
    Transient failures (network, permissions) should keep DB record for retry.

    Args:
        error: The exception raised during storage deletion

    Returns:
        True if this is a permanent failure (safe to delete from DB), False otherwise
    """
    # Check for standard Python file not found errors (local storage)
    if isinstance(error, FileNotFoundError):
        return True

    # Check for S3 error codes (boto3/aioboto3)
    # S3 errors have a 'response' attribute with Error.Code
    if hasattr(error, "response"):
        response = error.response
        if isinstance(response, dict):
            error_code = response.get("Error", {}).get("Code")
            # Permanent failures: file/bucket doesn't exist
            if error_code in ("NoSuchBucket", "NoSuchKey", "404"):
                return True

    # Fallback: Check error message for known permanent failure patterns
    # This is less ideal but provides a safety net for edge cases
    error_str = str(error)
    permanent_patterns = ("NoSuchBucket", "NoSuchKey", "not found", "FileNotFoundError")

    return any(pattern in error_str for pattern in permanent_patterns)


async def get_mcp_file(current_user: CurrentActiveUser, *, extension: bool = False) -> str:
    # Create a unique MCP servers file with the user id appended
    return f"{MCP_SERVERS_FILE}_{current_user.id!s}" + (".json" if extension else "")


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


async def save_file_routine(
    file,
    storage_service,
    current_user: CurrentActiveUser,
    file_content=None,
    file_name=None,
    *,
    append: bool = False,
):
    """Routine to save the file content to the storage service."""
    file_id = uuid.uuid4()

    if not file_content:
        file_content = await file.read()
    if not file_name:
        file_name = file.filename

    # Save the file using the storage service.
    await storage_service.save_file(flow_id=str(current_user.id), file_name=file_name, data=file_content, append=append)

    return file_id, file_name


@router.post("", status_code=HTTPStatus.CREATED)
@router.post("/", status_code=HTTPStatus.CREATED)
async def upload_user_file(
    file: Annotated[UploadFile, File(...)],
    session: DbSession,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
    *,
    append: bool = False,
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

    # Create a new database record for the uploaded file.
    try:
        # Sanitize filename to prevent path traversal and other security issues
        new_filename = sanitize_filename(file.filename)
        try:
            root_filename, file_extension = new_filename.rsplit(".", 1)
        except ValueError:
            root_filename, file_extension = new_filename, ""

        # Special handling for the MCP servers config file: always keep the same root filename
        mcp_file = await get_mcp_file(current_user)
        mcp_file_ext = await get_mcp_file(current_user, extension=True)

        # Initialize existing_file for append mode
        existing_file = None

        if new_filename == mcp_file_ext:
            # Check if an existing record exists; if so, delete it to replace with the new one
            existing_mcp_file = await get_file_by_name(mcp_file, current_user, session)
            if existing_mcp_file:
                await delete_file(existing_mcp_file.id, current_user, session, storage_service)
                # Flush the session to ensure the deletion is committed before creating the new file
                await session.flush()
            unique_filename = new_filename
        elif append:
            # In append mode, check if file exists and reuse the same filename
            existing_file = await get_file_by_name(root_filename, current_user, session)
            if existing_file:
                # File exists, append to it by reusing the same filename
                # Extract the filename from the path
                unique_filename = existing_file.path.split("/")[-1] if "/" in existing_file.path else existing_file.path
            else:
                # File doesn't exist yet, create new one with extension
                unique_filename = f"{root_filename}.{file_extension}" if file_extension else root_filename
        else:
            # For normal files, ensure unique name by appending a count if necessary
            stmt = select(UserFile).where(
                col(UserFile.name).like(f"{root_filename}%"), UserFile.user_id == current_user.id
            )
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

        # Read file content, save with unique filename, and compute file size in one routine
        try:
            file_id, stored_file_name = await save_file_routine(
                file, storage_service, current_user, file_name=unique_filename, append=append
            )
            file_size = await storage_service.get_file_size(
                flow_id=str(current_user.id),
                file_name=stored_file_name,
            )
        except FileNotFoundError as e:
            # S3 bucket doesn't exist or file not found, or file was uploaded but can't be found
            raise HTTPException(status_code=404, detail=str(e)) from e
        except PermissionError as e:
            # Access denied or invalid credentials
            raise HTTPException(status_code=403, detail=str(e)) from e
        except Exception as e:
            # General error saving file or getting file size
            raise HTTPException(status_code=500, detail=f"Error accessing file: {e}") from e

        if append and existing_file:
            existing_file.size = file_size
            session.add(existing_file)
            await session.commit()
            await session.refresh(existing_file)
            new_file = existing_file
        else:
            # Create a new file record
            new_file = UserFile(
                id=file_id,
                user_id=current_user.id,
                name=root_filename,
                path=f"{current_user.id}/{stored_file_name}",
                size=file_size,
            )

        session.add(new_file)
        try:
            await session.flush()
            await session.refresh(new_file)
        except Exception as db_err:
            # Database insert failed - clean up the uploaded file to avoid orphaned files
            try:
                await storage_service.delete_file(flow_id=str(current_user.id), file_name=stored_file_name)
            except OSError as e:
                #  If delete fails, just log the error
                await logger.aerror(f"Failed to clean up uploaded file {stored_file_name}: {e}")

            raise HTTPException(
                status_code=500, detail=f"Error inserting file metadata into database: {db_err}"
            ) from db_err
    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflicts) without modification
        raise
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

        await session.flush()
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
        mcp_file = await get_mcp_file(current_user)

        return [file for file in full_list if file.name != mcp_file]
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

        # Fetch all flows for the current user to check for file usage
        flows_stmt = select(Flow).where(Flow.user_id == current_user.id)
        flows = (await session.exec(flows_stmt)).all()

        files_not_deleted = []
        files_to_process = []

        for file in files:
            # Check if file is used in any flow
            file_is_used = False
            for flow in flows:
                if is_file_used(flow.data, file.name):
                    file_is_used = True
                    break

            if file_is_used:
                files_not_deleted.append(file.name)
            else:
                files_to_process.append(file)

        files = files_to_process

        # Track storage deletion failures
        storage_failures = []
        # Track database deletion failures
        db_failures = []

        # Delete all files from the storage service
        for file in files:
            # Extract just the filename from the path (strip user_id prefix)
            file_name = file.path.split("/")[-1]
            storage_deleted = False

            try:
                await storage_service.delete_file(flow_id=str(current_user.id), file_name=file_name)
                storage_deleted = True
            except OSError as err:
                # Check if this is a "permanent" failure where file/storage is gone
                # These are safe to delete from DB even if storage deletion failed
                if is_permanent_storage_failure(err):
                    # File/storage is permanently gone - safe to delete from DB
                    await logger.awarning(
                        "File %s not found in storage (permanent failure), will remove from database: %s",
                        file_name,
                        err,
                    )
                    storage_deleted = True  # Treat as "deleted" for DB purposes
                else:
                    # Transient failure (network, timeout, permissions) - keep in DB for retry
                    storage_failures.append(f"{file_name}: {err}")
                    await logger.awarning(
                        "Failed to delete file %s from storage (transient error, keeping in database for retry): %s",
                        file_name,
                        err,
                    )

            # Only delete from database if storage deletion succeeded OR it was a permanent failure
            if storage_deleted:
                try:
                    await session.delete(file)
                except OSError as db_error:
                    # Log database deletion failure but continue processing remaining files
                    db_failures.append(f"{file_name}: {db_error}")
                    await logger.aerror(
                        "Failed to delete file %s from database: %s",
                        file_name,
                        db_error,
                    )

        # If there were storage failures, include them in the response
        if storage_failures:
            await logger.awarning(
                "Batch delete completed with %d storage failures: %s", len(storage_failures), storage_failures
            )
        # If there were database failures, log them
        if db_failures:
            await logger.aerror("Batch delete completed with %d database failures: %s", len(db_failures), db_failures)
            # If all database deletions failed, raise an error
            if len(db_failures) == len(files):
                raise HTTPException(status_code=500, detail=f"Failed to delete any files from database: {db_failures}")

        # Calculate how many files were actually deleted from database
        # Files successfully deleted = total - (kept due to transient storage failures) - (DB deletion failures)
        files_deleted = len(files) - len(storage_failures) - len(db_failures)
        files_kept = len(storage_failures)  # Files with transient storage failures kept in DB

        # Build response message
        if files_deleted == len(files) and not files_not_deleted:
            message = f"{files_deleted} files deleted successfully"
        else:
            message = f"{files_deleted} files deleted successfully"
            if files_kept > 0:
                message += f", {files_kept} files kept in database due to transient storage errors (can retry)"
            if files_not_deleted:
                message += f", {len(files_not_deleted)} files not deleted because they are in use"

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting files: {e}") from e

    return {
        "message": message,
        "deleted_files": [f.name for f in files if f.name not in storage_failures and f.name not in db_failures],
        "files_not_deleted": files_not_deleted,
    }


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

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}") from e
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
    except HTTPException:
        raise
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

        # If return_content is True, read the file content and return it
        if return_content:
            # For content return, get the full file
            file_content = await storage_service.get_file(flow_id=str(current_user.id), file_name=file_name)
            if file_content is None:
                raise HTTPException(status_code=404, detail="File not found")
            return await read_file_content(file_content, decode=True)

        # For streaming, use the appropriate method based on storage type
        if hasattr(storage_service, "get_file_stream"):
            # S3 storage - use streaming method
            file_stream = storage_service.get_file_stream(flow_id=str(current_user.id), file_name=file_name)
            byte_stream = file_stream
        else:
            # Local storage - get file and convert to stream
            file_content = await storage_service.get_file(flow_id=str(current_user.id), file_name=file_name)
            if file_content is None:
                raise HTTPException(status_code=404, detail="File not found")
            byte_stream = byte_stream_generator(file_content)

        # Create the filename with extension and sanitize for Content-Disposition header
        file_extension = Path(file.path).suffix
        filename_with_extension = f"{file.name}{file_extension}"

        # Return the file as a streaming response
        return StreamingResponse(
            byte_stream,
            media_type="application/octet-stream",
            headers={"Content-Disposition": sanitize_content_disposition(filename_with_extension)},
        )

    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}") from e
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
    # Validate and sanitize the new name
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    sanitized_name = sanitize_filename(name)
    if sanitized_name != name.strip():
        raise HTTPException(
            status_code=400,
            detail="Name contains invalid characters. "
            "Only alphanumeric, spaces, dots, hyphens, underscores, and parentheses are allowed.",
        )

    try:
        # Fetch the file from the DB
        file = await fetch_file_object(file_id, current_user, session)

        # Update the file name
        file.name = sanitized_name
        session.add(file)
        await session.commit()
    except HTTPException:
        raise
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

        # Fetch all flows for the current user to check for file usage
        flows_stmt = select(Flow).where(Flow.user_id == current_user.id)
        flows = (await session.exec(flows_stmt)).all()

        # Check if file is used in any flow
        for flow in flows:
            if is_file_used(flow.data, file_to_delete.name):
                return {
                    "detail": f"File {file_to_delete.name} is in use and cannot be deleted",
                    "files_not_deleted": [file_to_delete.name],
                }

        # Extract just the filename from the path (strip user_id prefix)
        file_name = file_to_delete.path.split("/")[-1]

        # Delete the file from the storage service first
        storage_deleted = False
        try:
            await storage_service.delete_file(flow_id=str(current_user.id), file_name=file_name)
            storage_deleted = True
        except Exception as err:
            # Check if this is a "permanent" failure where file/storage is gone
            # These are safe to delete from DB even if storage deletion failed
            if is_permanent_storage_failure(err):
                await logger.awarning(
                    "File %s not found in storage (permanent failure), will remove from database: %s",
                    file_name,
                    err,
                )
                storage_deleted = True
            else:
                # Transient failure (network, timeout, permissions) - keep in DB for retry
                await logger.awarning(
                    "Failed to delete file %s from storage (transient error, keeping in database for retry): %s",
                    file_name,
                    err,
                )
                # Don't delete from DB - user can retry
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete file from storage. Please try again. Error: {err}",
                ) from err

        # Only delete from database if storage deletion succeeded OR it was a permanent failure
        if storage_deleted:
            try:
                await session.delete(file_to_delete)
                await session.commit()
            except Exception as db_error:
                await logger.aerror(
                    "Failed to delete file %s from database: %s",
                    file_to_delete.name,
                    db_error,
                )
                raise HTTPException(
                    status_code=500, detail=f"Error deleting file from database: {db_error}"
                ) from db_error

            return {"detail": f"File {file_to_delete.name} deleted successfully", "files_not_deleted": []}
    except HTTPException:
        # Re-raise HTTPException to avoid being caught by the generic exception handler
        raise
    except Exception as e:
        # Log and return a generic server error
        await logger.aerror("Error deleting file %s: %s", file_id, e)
        raise HTTPException(status_code=500, detail=f"Error deleting file: {e}") from e


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

        # Fetch all flows for the current user to check for file usage
        flows_stmt = select(Flow).where(Flow.user_id == current_user.id)
        flows = (await session.exec(flows_stmt)).all()

        files_not_deleted = []
        files_to_process = []

        for file in files:
            # Check if file is used in any flow
            file_is_used = False
            for flow in flows:
                if is_file_used(flow.data, file.name):
                    file_is_used = True
                    break

            if file_is_used:
                files_not_deleted.append(file.name)
            else:
                files_to_process.append(file)

        files = files_to_process

        storage_failures = []
        db_failures = []

        # Delete all files from the storage service
        for file in files:
            # Extract just the filename from the path (strip user_id prefix)
            file_name = file.path.split("/")[-1]
            storage_deleted = False

            try:
                await storage_service.delete_file(flow_id=str(current_user.id), file_name=file_name)
                storage_deleted = True
            except OSError as err:
                # Check if this is a "permanent" failure where file/storage is gone
                # These are safe to delete from DB even if storage deletion failed
                if is_permanent_storage_failure(err):
                    # File/storage is permanently gone - safe to delete from DB
                    await logger.awarning(
                        "File %s not found in storage, also removing from database: %s",
                        file_name,
                        err,
                    )
                    storage_deleted = True
                else:
                    # Transient failure (network, timeout, permissions) - keep in DB for retry
                    storage_failures.append(f"{file_name}: {err}")
                    await logger.awarning(
                        "Failed to delete file %s from storage (transient error, keeping in database for retry): %s",
                        file_name,
                        err,
                    )

            # Only delete from database if storage deletion succeeded OR it was a permanent failure
            if storage_deleted:
                try:
                    await session.delete(file)
                except OSError as db_error:
                    # Log database deletion failure but continue processing remaining files
                    db_failures.append(f"{file_name}: {db_error}")
                    await logger.aerror(
                        "Failed to delete file %s from database: %s",
                        file_name,
                        db_error,
                    )

        if storage_failures:
            await logger.awarning(
                "Batch delete completed with %d storage failures: %s", len(storage_failures), storage_failures
            )

        if db_failures:
            await logger.aerror("Batch delete completed with %d database failures: %s", len(db_failures), db_failures)
            # If all database deletions failed, raise an error
            if len(db_failures) == len(files):
                raise HTTPException(status_code=500, detail=f"Failed to delete any files from database: {db_failures}")

        # Calculate how many files were actually deleted from database
        # Files successfully deleted = total - (kept due to transient storage failures) - (DB deletion failures)
        files_deleted = len(files) - len(storage_failures) - len(db_failures)
        files_kept = len(storage_failures) + len(db_failures)

        if files_deleted == len(files) and not files_not_deleted:
            message = f"All {files_deleted} files deleted successfully"
        else:
            message = f"{files_deleted} files deleted successfully"
            if files_kept > 0:
                message += f", {files_kept} files failed to delete. See logs for details."
            if files_not_deleted:
                message += f", {len(files_not_deleted)} files not deleted because they are in use"

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting all files: {e}") from e

    return {"message": message, "files_not_deleted": files_not_deleted}
