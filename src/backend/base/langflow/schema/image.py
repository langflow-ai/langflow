import base64

from PIL import Image as PILImage
from pydantic import BaseModel

from langflow.services.deps import get_storage_service

IMAGE_ENDPOINT = "/files/images/"


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
        flow_id, file_name = file.split("/")
        file_paths.append(storage_service.build_full_path(flow_id=flow_id, file_name=file_name))
    return file_paths


async def get_files(
    file_paths: list[str],
    *,
    convert_to_base64: bool = False,
):
    storage_service = get_storage_service()
    file_objects: list[str | bytes] = []
    for file_path in file_paths:
        flow_id, file_name = file_path.split("/")
        file_object = await storage_service.get_file(flow_id=flow_id, file_name=file_name)
        if convert_to_base64:
            file_base64 = base64.b64encode(file_object).decode("utf-8")
            file_objects.append(file_base64)
        else:
            file_objects.append(file_object)
    return file_objects


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
