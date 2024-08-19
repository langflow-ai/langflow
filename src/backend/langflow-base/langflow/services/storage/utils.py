from langflow.services.storage.constants import EXTENSION_TO_CONTENT_TYPE


def build_content_type_from_extension(extension: str):
    return EXTENSION_TO_CONTENT_TYPE.get(extension.lower(), "application/octet-stream")
