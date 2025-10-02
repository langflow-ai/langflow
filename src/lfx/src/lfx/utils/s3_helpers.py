"""Shared S3 utility functions for working with S3 URIs and file operations."""

import asyncio

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

    Args:
        flow_id: The flow ID where the file is stored
        file_name: The name of the file to fetch

    Returns:
        bytes: The file content as bytes

    Raises:
        RuntimeError: If storage service is not available
        ValueError: If file cannot be retrieved
    """
    storage_service = get_storage_service()
    if not storage_service:
        msg = "Storage service not available"
        raise RuntimeError(msg)

    return await storage_service.get_file(flow_id, file_name)


def fetch_s3_file_sync(s3_uri: str) -> bytes:
    """Fetch file content from S3 synchronously (for use in sync contexts).

    This function handles the async event loop setup automatically.

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
    s3_info = parse_s3_uri(s3_uri)
    if not s3_info:
        msg = f"Invalid S3 URI format: {s3_uri}"
        raise ValueError(msg)

    flow_id, file_name = s3_info

    # Get or create event loop for async operation
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(fetch_s3_file_async(flow_id, file_name))


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
    return isinstance(path, str) and path.startswith("s3://")
