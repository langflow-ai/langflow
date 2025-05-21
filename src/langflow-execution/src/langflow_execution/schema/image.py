import base64
import mimetypes
from pathlib import Path

from PIL import Image as PILImage
from pydantic import BaseModel

from langflow.services.deps import get_storage_service

IMAGE_ENDPOINT = "/files/images/"

class Image(BaseModel):
    path: str | None = None
    url: str | None = None

    def to_base64(self):
        if self.path:
            files = get_files([self.path], convert_to_base64=True)
            return files[0]
        msg = "Image path is not set."
        raise ValueError(msg)

    def to_content_dict(self):
        return {
            "type": "image_url",
            "image_url": self.to_base64(),
        }

    def get_url(self) -> str:
        return f"{IMAGE_ENDPOINT}{self.path}"


def is_image_file(file_path) -> bool:
    try:
        with PILImage.open(file_path) as img:
            img.verify()  # Verify that it is, in fact, an image
    except (OSError, SyntaxError):
        return False
    return True


def get_file_paths(files: list[str]):
    storage_service = get_storage_service()
    file_paths = []
    for file in files:
        file_path = Path(file)
        flow_id, file_name = str(file_path.parent), file_path.name
        file_paths.append(storage_service.build_full_path(flow_id=flow_id, file_name=file_name))
    return file_paths


async def get_files(
    file_paths: list[str],
    *,
    convert_to_base64: bool = False,
):
    storage_service = get_storage_service()
    file_objects: list[str | bytes] = []
    for file in file_paths:
        file_path = Path(file)
        flow_id, file_name = str(file_path.parent), file_path.name
        file_object = await storage_service.get_file(flow_id=flow_id, file_name=file_name)
        if convert_to_base64:
            file_base64 = base64.b64encode(file_object).decode("utf-8")
            file_objects.append(file_base64)
        else:
            file_objects.append(file_object)
    return file_objects


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
