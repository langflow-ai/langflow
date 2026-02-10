"""Helper utility functions for lfx package."""

from __future__ import annotations

import math
import mimetypes
from typing import TYPE_CHECKING

from lfx.utils.constants import EXTENSION_TO_CONTENT_TYPE

if TYPE_CHECKING:
    from pathlib import Path


def get_mime_type(file_path: str | Path) -> str:
    """Get the MIME type of a file based on its extension.

    Args:
        file_path: Path to the file

    Returns:
        MIME type string (e.g., 'image/jpeg', 'image/png')

    Raises:
        ValueError: If MIME type cannot be determined
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type is None:
        msg = f"Could not determine MIME type for: {file_path}"
        raise ValueError(msg)
    return mime_type


def build_content_type_from_extension(extension: str):
    return EXTENSION_TO_CONTENT_TYPE.get(extension.lower(), "application/octet-stream")


def sanitize_nan(value):
    """Replace float NaN / Infinity with ``None`` for JSON safety.

    NaN and Infinity are valid IEEE 754 values but are not representable in
    standard JSON (RFC 7159). PostgreSQL ``JSON`` / ``JSONB`` columns will
    reject them.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
