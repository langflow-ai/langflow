"""Helper utility functions for lfx package."""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING

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
