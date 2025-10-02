"""Unified file I/O that works with both local and remote storage.

This module provides a storage-agnostic interface for reading and writing files.
It automatically detects the storage backend (local or S3) and uses the appropriate
service from the dependency injection system.
"""

import asyncio
from pathlib import Path

from lfx.log.logger import logger
from lfx.services.deps import get_storage_service


async def read_file_async(file_path: str) -> bytes:
    """Read file from any storage backend (local or S3).

    Automatically detects storage type and uses appropriate service.

    Args:
        file_path: The path to read from (can be local path or S3 URI)

    Returns:
        bytes: The file content

    Raises:
        FileNotFoundError: If the file does not exist
        RuntimeError: If storage service is not available
        ValueError: If the path format is invalid

    Examples:
        >>> # Read from local file
        >>> content = await read_file_async("/path/to/file.txt")
        >>> # Read from S3
        >>> content = await read_file_async("s3://bucket/prefix/flow/file.txt")
    """
    storage = get_storage_service()

    if not storage:
        # Fallback to direct file read for backward compatibility
        logger.warning("Storage service not available, falling back to direct file read")
        try:
            return Path(file_path).read_bytes()
        except FileNotFoundError as e:
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg) from e

    # Use storage service for unified read
    try:
        return await storage.read_file(file_path)
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise


def read_file_sync(file_path: str) -> bytes:
    """Synchronous wrapper for read_file_async.

    Args:
        file_path: The path to read from (can be local path or S3 URI)

    Returns:
        bytes: The file content

    Raises:
        FileNotFoundError: If the file does not exist
        RuntimeError: If storage service is not available
        ValueError: If the path format is invalid

    Examples:
        >>> # Read from local file
        >>> content = read_file_sync("/path/to/file.txt")
        >>> # Read from S3
        >>> content = read_file_sync("s3://bucket/prefix/flow/file.txt")
    """
    return asyncio.run(read_file_async(file_path))


async def write_file_async(file_path: str, data: bytes, *, flow_id: str | None = None) -> str:
    """Write file to storage backend, return final path.

    Args:
        file_path: The desired path or file name
        data: The file content to write
        flow_id: Optional flow ID for organizing files

    Returns:
        str: The final storage path where file was written

    Raises:
        RuntimeError: If storage service is not available
        ValueError: If the path format is invalid

    Examples:
        >>> # Write to local storage
        >>> path = await write_file_async("/path/to/file.txt", b"content")
        >>> # Write to S3
        >>> path = await write_file_async("s3://bucket/prefix/flow/file.txt", b"content")
        >>> # Write with explicit flow_id
        >>> path = await write_file_async("file.txt", b"content", flow_id="my-flow")
    """
    storage = get_storage_service()

    if not storage:
        # Fallback to direct file write for backward compatibility
        logger.warning("Storage service not available, falling back to direct file write")
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    # Use storage service for unified write
    try:
        return await storage.write_file(file_path, data, flow_id=flow_id)
    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        raise


def write_file_sync(file_path: str, data: bytes, *, flow_id: str | None = None) -> str:
    """Synchronous wrapper for write_file_async.

    Args:
        file_path: The desired path or file name
        data: The file content to write
        flow_id: Optional flow ID for organizing files

    Returns:
        str: The final storage path where file was written

    Raises:
        RuntimeError: If storage service is not available
        ValueError: If the path format is invalid

    Examples:
        >>> # Write to local storage
        >>> path = write_file_sync("/path/to/file.txt", b"content")
        >>> # Write to S3
        >>> path = write_file_sync("s3://bucket/prefix/flow/file.txt", b"content")
        >>> # Write with explicit flow_id
        >>> path = write_file_sync("file.txt", b"content", flow_id="my-flow")
    """
    return asyncio.run(write_file_async(file_path, data, flow_id=flow_id))


async def path_exists_async(file_path: str) -> bool:
    """Check if a file exists in any storage backend.

    Args:
        file_path: The path to check (can be local path or S3 URI)

    Returns:
        bool: True if file exists, False otherwise

    Examples:
        >>> # Check local file
        >>> exists = await path_exists_async("/path/to/file.txt")
        >>> # Check S3 file
        >>> exists = await path_exists_async("s3://bucket/prefix/flow/file.txt")
    """
    storage = get_storage_service()

    if not storage:
        # Fallback to direct path check
        logger.warning("Storage service not available, falling back to direct path check")
        return Path(file_path).exists()

    # Parse path and check existence
    try:
        parsed = storage.parse_path(file_path)
        if not parsed:
            return False

        flow_id, file_name = parsed
        return await storage.path_exists(flow_id, file_name)
    except Exception as e:
        logger.error(f"Error checking if path exists {file_path}: {e}")
        return False


def path_exists_sync(file_path: str) -> bool:
    """Synchronous wrapper for path_exists_async.

    Args:
        file_path: The path to check (can be local path or S3 URI)

    Returns:
        bool: True if file exists, False otherwise

    Examples:
        >>> # Check local file
        >>> exists = path_exists_sync("/path/to/file.txt")
        >>> # Check S3 file
        >>> exists = path_exists_sync("s3://bucket/prefix/flow/file.txt")
    """
    return asyncio.run(path_exists_async(file_path))


def is_remote_path(file_path: str) -> bool:
    """Check if a path is a remote storage path.

    Args:
        file_path: The path to check

    Returns:
        bool: True if path is remote (e.g., S3 URI), False otherwise

    Examples:
        >>> is_remote_path("s3://bucket/prefix/flow/file.txt")
        True
        >>> is_remote_path("/local/path/file.txt")
        False
    """
    storage = get_storage_service()

    if not storage:
        # If no storage service, assume all paths are local
        return False

    return storage.is_remote_path(file_path)
