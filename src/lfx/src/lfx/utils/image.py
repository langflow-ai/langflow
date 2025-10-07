"""Image utility functions for lfx package."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from lfx.utils.helpers import get_mime_type


def convert_image_to_base64(image_path: str | Path) -> str:
    """Convert an image file to a base64 encoded string.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded string of the image

    Raises:
        FileNotFoundError: If the image file doesn't exist
    """
    image_path = Path(image_path)
    if not image_path.exists():
        msg = f"Image file not found: {image_path}"
        raise FileNotFoundError(msg)

    with image_path.open("rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def create_data_url(image_path: str | Path, mime_type: str | None = None) -> str:
    """Create a data URL from an image file.

    Args:
        image_path: Path to the image file
        mime_type: MIME type of the image. If None, will be auto-detected

    Returns:
        Data URL string in format: data:mime/type;base64,{base64_data}

    Raises:
        FileNotFoundError: If the image file doesn't exist
    """
    image_path = Path(image_path)
    if not image_path.exists():
        msg = f"Image file not found: {image_path}"
        raise FileNotFoundError(msg)

    if mime_type is None:
        mime_type = get_mime_type(image_path)

    base64_data = convert_image_to_base64(image_path)
    return f"data:{mime_type};base64,{base64_data}"


@lru_cache(maxsize=50)
def create_image_content_dict(
    image_path: str | Path, mime_type: str | None = None, model_name: str | None = None
) -> dict:
    """Create a content dictionary for multimodal inputs from an image file.

    Args:
        image_path: Path to the image file
        mime_type: MIME type of the image. If None, will be auto-detected
        model_name: Optional model parameter to determine content dict structure

    Returns:
        Content dictionary with type and image_url fields

    Raises:
        FileNotFoundError: If the image file doesn't exist
    """
    data_url = create_data_url(image_path, mime_type)

    if model_name == "OllamaModel":
        return {"type": "image_url", "source_type": "url", "image_url": data_url}
    return {"type": "image", "source_type": "url", "url": data_url}
