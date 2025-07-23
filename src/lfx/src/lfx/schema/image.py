import base64
from pathlib import Path

import aiofiles
from PIL import Image as PILImage
from platformdirs import user_cache_dir
from pydantic import BaseModel

from lfx.services.deps import get_storage_service

IMAGE_ENDPOINT = "/files/images/"


def is_image_file(file_path) -> bool:
    """Check if a file is a valid image."""
    try:
        with PILImage.open(file_path) as img:
            img.verify()  # Verify that it is, in fact, an image
    except (OSError, SyntaxError):
        return False
    return True


def get_file_paths(files: list[str | dict]):
    """Get file paths for a list of files."""
    storage_service = get_storage_service()
    if not storage_service:
        # Extract paths from dicts if present

        extracted_files = []
        cache_dir = Path(user_cache_dir("langflow"))

        for file in files:
            file_path = file["path"] if isinstance(file, dict) and "path" in file else file

            # If it's a relative path like "flow_id/filename", resolve it to cache dir
            path = Path(file_path)
            if not path.is_absolute() and not path.exists():
                # Check if it exists in the cache directory
                cache_path = cache_dir / file_path
                if cache_path.exists():
                    extracted_files.append(str(cache_path))
                else:
                    # Keep the original path if not found
                    extracted_files.append(file_path)
            else:
                extracted_files.append(file_path)
        return extracted_files

    file_paths = []
    for file in files:
        # Handle dict case
        if storage_service is None:
            continue
        if isinstance(file, dict) and "path" in file:
            file_path = Path(file["path"])
        elif hasattr(file, "path") and file.path:
            file_path = Path(file.path)
        else:
            file_path = Path(file)
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
        # For testing purposes, read files directly when no storage service
        file_objects: list[str | bytes] = []
        for file_path_str in file_paths:
            file_path = Path(file_path_str)
            if file_path.exists():
                # Use async read for compatibility

                async with aiofiles.open(file_path, "rb") as f:
                    file_content = await f.read()
                if convert_to_base64:
                    file_base64 = base64.b64encode(file_content).decode("utf-8")
                    file_objects.append(file_base64)
                else:
                    file_objects.append(file_content)
            else:
                msg = f"File not found: {file_path}"
                raise FileNotFoundError(msg)
        return file_objects

    file_objects: list[str | bytes] = []
    for file in file_paths:
        file_path = Path(file)
        flow_id, file_name = str(file_path.parent), file_path.name
        if not storage_service:
            continue
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
