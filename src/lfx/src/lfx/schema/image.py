import base64
from pathlib import Path

from PIL import Image as PILImage
from pydantic import BaseModel

try:
    from lfx.services.deps import get_storage_service
except ImportError:
    # Fallback for when langflow services are not available
    def get_storage_service():
        """Fallback storage service when langflow is not available."""
        return


IMAGE_ENDPOINT = "/files/images/"


def is_image_file(file_path) -> bool:
    """Check if a file is a valid image."""
    try:
        with PILImage.open(file_path) as img:
            img.verify()  # Verify that it is, in fact, an image
    except (OSError, SyntaxError):
        return False
    return True


def get_file_paths(files: list[str]):
    """Get file paths for a list of files."""
    storage_service = get_storage_service()
    if not storage_service:
        # Return files as-is if no storage service
        return files

    file_paths = []
    for file in files:
        file_path = Path(file.path) if hasattr(file, "path") and file.path else Path(file)
        flow_id, file_name = str(file_path.parent), file_path.name
        file_paths.append(storage_service.build_full_path(flow_id=flow_id, file_name=file_name))
    return file_paths


async def get_files(
    file_paths: list[str],
    *,
    convert_to_base64: bool = False,
):
    """Get files from storage service."""
    storage_service = get_storage_service()
    if not storage_service:
        msg = "Storage service not available"
        raise ValueError(msg)

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


class Image(BaseModel):
    """Image model for lfx package."""

    path: str | None = None
    url: str | None = None

    def to_base64(self):
        """Convert image to base64 string."""
        if self.path:
            files = get_files([self.path], convert_to_base64=True)
            return files[0]
        msg = "Image path is not set."
        raise ValueError(msg)

    def to_content_dict(self):
        """Convert image to content dictionary."""
        return {
            "type": "image_url",
            "image_url": self.to_base64(),
        }

    def get_url(self) -> str:
        """Get the URL for the image."""
        return f"{IMAGE_ENDPOINT}{self.path}"
