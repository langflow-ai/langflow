import base64
import mimetypes
from pathlib import Path


def convert_image_to_base64(image_path: str | Path) -> str:
    """Convert an image file to a base64 encoded string.

    Args:
        image_path (str | Path): Path to the image file.

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

    image_path = Path(image_path)

    if not image_path.exists() and not image_path.is_absolute():
        try:
            from langflow.services.deps import get_storage_service
            storage_service = get_storage_service()
            base_dir = Path(str(storage_service.data_dir))
            resolved_path = base_dir / image_path
            if resolved_path.exists():
                image_path = resolved_path
        except Exception:
            pass

    if not image_path.exists():
        msg = f"Image file not found: {image_path}"
        raise FileNotFoundError(msg)

    if not image_path.is_file():
        msg = f"Path is not a file: {image_path}"
        raise ValueError(msg)

    try:
        with image_path.open("rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except OSError as e:
        msg = f"Error reading image file: {e}"
        raise OSError(msg) from e


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
