import asyncio
import base64
import mimetypes
from functools import lru_cache
from pathlib import Path


def convert_image_to_base64(image_path: str | Path) -> str:
    """Convert an image file to a base64 encoded string.
    
    Supports both local absolute paths and storage service paths (flow_id/filename format).

    Args:
        image_path (str | Path): Path to the image file (local absolute path or storage service path).

    Returns:
        str: Base64 encoded string representation of the image.

    Raises:
        FileNotFoundError: If the image file does not exist.
        IOError: If there's an error reading the image file.
        ValueError: If the image path is empty or invalid.
    """
    if not image_path:
        msg = "Image path cannot be empty"
        raise ValueError(msg)

    image_path_obj = Path(image_path)

    # Check if this is an absolute local path
    if image_path_obj.is_absolute():
        # Local file path
        if not image_path_obj.exists():
            msg = f"Image file not found: {image_path}"
            raise FileNotFoundError(msg)

        if not image_path_obj.is_file():
            msg = f"Path is not a file: {image_path}"
            raise ValueError(msg)

        try:
            with image_path_obj.open("rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except OSError as e:
            msg = f"Error reading image file: {e}"
            raise OSError(msg) from e
    
    # Storage service path (format: flow_id/filename or just filename)
    from langflow.services.deps import get_settings_service, get_storage_service
    
    settings = get_settings_service().settings
    storage_service = get_storage_service()
    
    if not storage_service:
        msg = f"Storage service not available for path: {image_path}"
        raise ValueError(msg)
    
    # For local storage, resolve to absolute path
    if settings.storage_type == "local":
        full_path = storage_service.build_full_path(
            flow_id=str(image_path_obj.parent) if image_path_obj.parent != Path() else "",
            file_name=image_path_obj.name
        )
        full_path_obj = Path(full_path)
        
        if not full_path_obj.exists():
            msg = f"Image file not found: {image_path}"
            raise FileNotFoundError(msg)
        
        try:
            with full_path_obj.open("rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except OSError as e:
            msg = f"Error reading image file: {e}"
            raise OSError(msg) from e
    
    # For S3 storage, use async get_file
    try:
        # Parse the path
        if image_path_obj.parent == Path():
            flow_id, file_name = "", image_path_obj.name
        else:
            flow_id, file_name = str(image_path_obj.parent), image_path_obj.name
        
        # Get file from storage service (async operation)
        file_bytes = asyncio.run(storage_service.get_file(flow_id=flow_id, file_name=file_name))
        return base64.b64encode(file_bytes).decode("utf-8")
    except Exception as e:
        msg = f"Error reading image file from storage: {e}"
        raise FileNotFoundError(msg) from e


def create_data_url(image_path: str | Path, mime_type: str | None = None) -> str:
    """Create a data URL from an image file.

    Args:
        image_path (str | Path): Path to the image file.
        mime_type (Optional[str], optional): MIME type of the image.
            If None, it will be guessed from the file extension.

    Returns:
        str: Data URL containing the base64 encoded image.

    Raises:
        FileNotFoundError: If the image file does not exist.
        IOError: If there's an error reading the image file.
        ValueError: If the image path is empty or invalid.
    """
    if not mime_type:
        mime_type = mimetypes.guess_type(str(image_path))[0]
        if not mime_type:
            msg = f"Could not determine MIME type for: {image_path}"
            raise ValueError(msg)

    try:
        base64_data = convert_image_to_base64(image_path)
    except (OSError, FileNotFoundError, ValueError) as e:
        msg = f"Failed to create data URL: {e}"
        raise type(e)(msg) from e
    return f"data:{mime_type};base64,{base64_data}"


@lru_cache(maxsize=50)
def create_image_content_dict(image_path: str | Path, mime_type: str | None = None) -> dict:
    """Create a content dictionary for multimodal inputs from an image file.

    Args:
        image_path (str | Path): Path to the image file.
        mime_type (Optional[str], optional): MIME type of the image.
            If None, it will be guessed from the file extension.

    Returns:
        dict: Content dictionary with type, source_type, data, and mime_type fields.

    Raises:
        FileNotFoundError: If the image file does not exist.
        IOError: If there's an error reading the image file.
        ValueError: If the image path is empty or invalid.
    """
    if not mime_type:
        mime_type = mimetypes.guess_type(str(image_path))[0]
        if not mime_type:
            msg = f"Could not determine MIME type for: {image_path}"
            raise ValueError(msg)

    try:
        base64_data = convert_image_to_base64(image_path)
    except (OSError, FileNotFoundError, ValueError) as e:
        msg = f"Failed to create image content dict: {e}"
        raise type(e)(msg) from e

    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}}
