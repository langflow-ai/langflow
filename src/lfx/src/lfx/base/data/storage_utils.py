"""Storage-aware file utilities for components.

This module provides utilities that work with both local files and remote files
stored in the storage service.

TODO: Can abstract these into the storage service interface and update
implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lfx.utils.async_helpers import run_until_complete

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.services.storage.service import StorageService

# Constants for path parsing
EXPECTED_PATH_PARTS = 2  # Path format: "flow_id/filename"

# Magic bytes signatures for common image formats
MIN_IMAGE_HEADER_SIZE = 12  # Minimum bytes needed to detect image type

IMAGE_SIGNATURES: dict[str, list[tuple[bytes, int]]] = {
    "jpeg": [(b"\xff\xd8\xff", 0)],
    "jpg": [(b"\xff\xd8\xff", 0)],
    "png": [(b"\x89PNG\r\n\x1a\n", 0)],
    "gif": [(b"GIF87a", 0), (b"GIF89a", 0)],
    "webp": [(b"RIFF", 0)],  # WebP starts with RIFF, then has WEBP at offset 8
    "bmp": [(b"BM", 0)],
    "tiff": [(b"II*\x00", 0), (b"MM\x00*", 0)],  # Little-endian and big-endian TIFF
}


def detect_image_type_from_bytes(content: bytes) -> str | None:
    """Detect the actual image type from file content using magic bytes.

    Args:
        content: The file content bytes (at least first 12 bytes needed)

    Returns:
        str | None: The detected image type (e.g., "jpeg", "png") or None if not recognized
    """
    if len(content) < MIN_IMAGE_HEADER_SIZE:
        return None

    # Check WebP specifically (needs to check both RIFF and WEBP)
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"

    # Check other image signatures
    for image_type, signatures in IMAGE_SIGNATURES.items():
        if image_type == "webp":
            continue  # Already handled above
        for signature, offset in signatures:
            if content[offset : offset + len(signature)] == signature:
                return image_type

    return None


def validate_image_content_type(
    file_path: str,
    content: bytes | None = None,
    storage_service: StorageService | None = None,
    resolve_path: Callable[[str], str] | None = None,
) -> tuple[bool, str | None]:
    """Validate that an image file's content matches its declared extension.

    This prevents errors like "Image does not match the provided media type image/png"
    when a JPEG file is saved with a .png extension.

    Only rejects files when we can definitively detect a mismatch. Files with
    unrecognized content are allowed through (they may fail later, but that's
    better than false positives blocking valid files).

    Args:
        file_path: Path to the image file
        content: Optional pre-read file content bytes. If not provided, will read from file.
        storage_service: Optional storage service instance for S3 files
        resolve_path: Optional function to resolve relative paths

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)
            - (True, None) if the content matches the extension, is unrecognized, or file is not an image
            - (False, error_message) if there's a definite mismatch
    """
    # Get the file extension
    path_obj = Path(file_path)
    extension = path_obj.suffix[1:].lower() if path_obj.suffix else ""

    # Only validate image files
    image_extensions = {"jpeg", "jpg", "png", "gif", "webp", "bmp", "tiff"}
    if extension not in image_extensions:
        return True, None

    # Read content if not provided
    if content is None:
        try:
            from lfx.services.deps import get_storage_service

            if storage_service is None:
                storage_service = get_storage_service()

            # Use storage service helper to read file bytes
            content = run_until_complete(storage_service.read_file_bytes_from_path(file_path, resolve_path))
        except (FileNotFoundError, ValueError):
            # Can't read file - let it pass, will fail later with better error
            return True, None

    # Detect actual image type
    detected_type = detect_image_type_from_bytes(content)

    # If we can't detect the type, the file is not a valid image
    if detected_type is None:
        return False, (
            f"File '{path_obj.name}' has extension '.{extension}' but its content "
            f"is not a valid image format. The file may be corrupted, empty, or not a real image."
        )

    # Normalize extensions for comparison (jpg == jpeg, tif == tiff)
    extension_normalized = "jpeg" if extension == "jpg" else extension
    detected_normalized = "jpeg" if detected_type == "jpg" else detected_type

    if extension_normalized != detected_normalized:
        return False, (
            f"File '{path_obj.name}' has extension '.{extension}' but contains "
            f"'{detected_type.upper()}' image data. This mismatch will cause API errors. "
            f"Please rename the file with the correct extension '.{detected_type}' or "
            f"re-save it in the correct format."
        )

    return True, None
