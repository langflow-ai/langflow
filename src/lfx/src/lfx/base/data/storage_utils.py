"""Storage-aware file utilities for components.

This module provides utilities that work with both local files and remote files
stored in the storage service.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lfx.services.deps import get_settings_service, get_storage_service
from lfx.utils.async_helpers import run_until_complete

if TYPE_CHECKING:
    from lfx.services.storage.service import StorageService


def parse_storage_path(path: str) -> tuple[str, str] | None:
    """Parse a storage service path into flow_id and filename.

    Storage service paths follow the format: flow_id/filename
    This should only be called when storage_type == "s3".

    Args:
        path: The storage service path in format "flow_id/filename"

    Returns:
        tuple[str, str] | None: (flow_id, filename) or None if invalid format
    """
    if not path or "/" not in path:
        return None

    parts = path.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None

    return parts[0], parts[1]


async def read_file_bytes(file_path: str, storage_service: StorageService | None = None) -> bytes:
    """Read file bytes from either storage service or local filesystem.

    Args:
        file_path: Path to the file (S3 key format "flow_id/filename" or absolute local path)
        storage_service: Optional storage service instance (will get from deps if not provided)

    Returns:
        bytes: The file content

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    settings = get_settings_service().settings

    if settings.storage_type == "s3":
        parsed = parse_storage_path(file_path)
        if not parsed:
            msg = f"Invalid S3 path format: {file_path}. Expected 'flow_id/filename'"
            raise ValueError(msg)

        if storage_service is None:
            storage_service = get_storage_service()

        flow_id, filename = parsed
        return await storage_service.get_file(flow_id, filename)

    path_obj = Path(file_path)
    if not path_obj.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)

    return path_obj.read_bytes()


async def read_file_text(file_path: str, encoding: str = "utf-8", storage_service: StorageService | None = None) -> str:
    """Read file text from either storage service or local filesystem.

    Args:
        file_path: Path to the file (storage service path or absolute local path)
        encoding: Text encoding to use
        storage_service: Optional storage service instance

    Returns:
        str: The file content as text

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    content = await read_file_bytes(file_path, storage_service)
    return content.decode(encoding)


def get_file_size(file_path: str, storage_service: StorageService | None = None) -> int:
    """Get file size from either storage service or local filesystem.

    Note: This is a sync wrapper - for async code, use the storage service directly.

    Args:
        file_path: Path to the file (S3 key format "flow_id/filename" or absolute local path)
        storage_service: Optional storage service instance

    Returns:
        int: File size in bytes

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    settings = get_settings_service().settings

    if settings.storage_type == "s3":
        parsed = parse_storage_path(file_path)
        if not parsed:
            msg = f"Invalid S3 path format: {file_path}. Expected 'flow_id/filename'"
            raise ValueError(msg)

        if storage_service is None:
            storage_service = get_storage_service()

        flow_id, filename = parsed
        return run_until_complete(storage_service.get_file_size(flow_id, filename))

    # Local file system
    path_obj = Path(file_path)
    if not path_obj.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)

    return path_obj.stat().st_size


def file_exists(file_path: str, storage_service: StorageService | None = None) -> bool:
    """Check if a file exists in either storage service or local filesystem.

    Args:
        file_path: Path to the file (S3 key format "flow_id/filename" or absolute local path)
        storage_service: Optional storage service instance

    Returns:
        bool: True if the file exists
    """
    try:
        get_file_size(file_path, storage_service)
        return True
    except (FileNotFoundError, ValueError):
        return False
