"""Shared S3 utility functions for working with S3 URIs and file operations.

This module provides S3-specific utilities and delegates to the unified storage_file_io
module for actual file operations. This ensures consistent behavior across storage backends.
"""

from lfx.services.deps import get_storage_service


def parse_s3_uri(s3_uri: str) -> tuple[str, str] | None:
    """Parse S3 URI into (flow_id, file_name).

    Expected format: s3://bucket/prefix/flow_id/file_name

    Args:
        s3_uri: The S3 URI to parse

    Returns:
        tuple[str, str] | None: (flow_id, file_name) if valid S3 URI, None otherwise

    Examples:
        >>> parse_s3_uri("s3://my-bucket/prefix/flow123/document.pdf")
        ('flow123', 'document.pdf')
        >>> parse_s3_uri("/local/file/path.txt")
        None
    """
    storage_service = get_storage_service()
    if storage_service:
        # Use storage service's parse_path method for consistency
        return storage_service.parse_path(s3_uri)

    # Fallback to manual parsing if storage service not available
    if not s3_uri.startswith("s3://"):
        return None

    # Remove s3:// prefix and split into parts
    path_parts = s3_uri[5:].split("/")

    # We need at least: bucket/prefix/flow_id/file_name (4 parts minimum)
    if len(path_parts) < 4:
        return None

    # Extract flow_id (second to last) and file_name (last)
    flow_id = path_parts[-2]
    file_name = path_parts[-1]

    return (flow_id, file_name)


async def fetch_s3_file_async(flow_id: str, file_name: str) -> bytes:
    """Fetch file content from S3 asynchronously.

    NOTE: This function is deprecated. Use storage_file_io.read_file_async() instead
    for storage-agnostic file reading.

    Args:
        flow_id: The flow ID where the file is stored
        file_name: The name of the file to fetch

    Returns:
        bytes: The file content as bytes

    Raises:
        RuntimeError: If storage service is not available
        ValueError: If file cannot be retrieved
    """
    from lfx.utils.storage_file_io import read_file_async

    storage_service = get_storage_service()
    if not storage_service:
        msg = "Storage service not available"
        raise RuntimeError(msg)

    # Build S3 URI and use unified read function
    s3_uri = storage_service.build_full_path(flow_id, file_name)
    return await read_file_async(s3_uri)


def fetch_s3_file_sync(s3_uri: str) -> bytes:
    """Fetch file content from S3 synchronously (for use in sync contexts).

    NOTE: This function is deprecated. Use storage_file_io.read_file_sync() instead
    for storage-agnostic file reading with proper async handling.

    Args:
        s3_uri: The S3 URI (e.g., s3://bucket/prefix/flow_id/file_name)

    Returns:
        bytes: The file content as bytes

    Raises:
        ValueError: If S3 URI is invalid
        RuntimeError: If storage service is not available

    Examples:
        >>> content = fetch_s3_file_sync("s3://bucket/prefix/flow123/doc.pdf")
        >>> len(content) > 0
        True
    """
    from lfx.utils.storage_file_io import read_file_sync

    # Validate S3 URI format
    if not is_s3_uri(s3_uri):
        msg = f"Invalid S3 URI format: {s3_uri}"
        raise ValueError(msg)

    # Use unified read function which handles async properly
    return read_file_sync(s3_uri)


def is_s3_uri(path: str) -> bool:
    """Check if a path is an S3 URI.

    Args:
        path: The path to check

    Returns:
        bool: True if path is an S3 URI, False otherwise

    Examples:
        >>> is_s3_uri("s3://bucket/prefix/flow/file.txt")
        True
        >>> is_s3_uri("/local/path/file.txt")
        False
    """
    storage_service = get_storage_service()
    if storage_service:
        # Use storage service's is_remote_path method for consistency
        return storage_service.is_remote_path(path)

    # Fallback to simple check if storage service not available
    return isinstance(path, str) and path.startswith("s3://")
