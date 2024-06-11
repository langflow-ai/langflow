import base64
import contextlib
import hashlib
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from fastapi import UploadFile
from platformdirs import user_cache_dir

if TYPE_CHECKING:
    from langflow.api.v1.schemas import BuildStatus

CACHE: Dict[str, Any] = {}

CACHE_DIR = user_cache_dir("langflow", "langflow")

PREFIX = "langflow_cache"


class CacheMiss:
    def __repr__(self):
        return "<CACHE_MISS>"

    def __bool__(self):
        return False


def create_cache_folder(func):
    def wrapper(*args, **kwargs):
        # Get the destination folder
        cache_path = Path(CACHE_DIR) / PREFIX

        # Create the destination folder if it doesn't exist
        os.makedirs(cache_path, exist_ok=True)

        return func(*args, **kwargs)

    return wrapper


@create_cache_folder
def clear_old_cache_files(max_cache_size: int = 3):
    cache_dir = Path(tempfile.gettempdir()) / PREFIX
    cache_files = list(cache_dir.glob("*.dill"))

    if len(cache_files) > max_cache_size:
        cache_files_sorted_by_mtime = sorted(cache_files, key=lambda x: x.stat().st_mtime, reverse=True)

        for cache_file in cache_files_sorted_by_mtime[max_cache_size:]:
            with contextlib.suppress(OSError):
                os.remove(cache_file)


def filter_json(json_data):
    filtered_data = json_data.copy()

    # Remove 'viewport' and 'chatHistory' keys
    if "viewport" in filtered_data:
        del filtered_data["viewport"]
    if "chatHistory" in filtered_data:
        del filtered_data["chatHistory"]

    # Filter nodes
    if "nodes" in filtered_data:
        for node in filtered_data["nodes"]:
            if "position" in node:
                del node["position"]
            if "positionAbsolute" in node:
                del node["positionAbsolute"]
            if "selected" in node:
                del node["selected"]
            if "dragging" in node:
                del node["dragging"]

    return filtered_data


@create_cache_folder
def save_binary_file(content: str, file_name: str, accepted_types: list[str]) -> str:
    """
    Save a binary file to the specified folder.

    Args:
        content: The content of the file as a bytes object.
        file_name: The name of the file, including its extension.

    Returns:
        The path to the saved file.
    """
    if not any(file_name.endswith(suffix) for suffix in accepted_types):
        raise ValueError(f"File {file_name} is not accepted")

    # Get the destination folder
    cache_path = Path(CACHE_DIR) / PREFIX
    if not content:
        raise ValueError("Please, reload the file in the loader.")
    data = content.split(",")[1]
    decoded_bytes = base64.b64decode(data)

    # Create the full file path
    file_path = os.path.join(cache_path, file_name)

    # Save the binary content to the file
    with open(file_path, "wb") as file:
        file.write(decoded_bytes)

    return file_path


@create_cache_folder
def save_uploaded_file(file: UploadFile, folder_name):
    """
    Save an uploaded file to the specified folder with a hash of its content as the file name.

    Args:
        file: The uploaded file object.
        folder_name: The name of the folder to save the file in.

    Returns:
        The path to the saved file.
    """
    cache_path = Path(CACHE_DIR)
    folder_path = cache_path / folder_name
    filename = file.filename
    if isinstance(filename, str) or isinstance(filename, Path):
        file_extension = Path(filename).suffix
    else:
        file_extension = ""
    file_object = file.file

    # Create the folder if it doesn't exist
    if not folder_path.exists():
        folder_path.mkdir()

    # Create a hash of the file content
    sha256_hash = hashlib.sha256()
    # Reset the file cursor to the beginning of the file
    file_object.seek(0)
    # Iterate over the uploaded file in small chunks to conserve memory
    while chunk := file_object.read(8192):  # Read 8KB at a time (adjust as needed)
        sha256_hash.update(chunk)

    # Use the hex digest of the hash as the file name
    hex_dig = sha256_hash.hexdigest()
    file_name = f"{hex_dig}{file_extension}"

    # Reset the file cursor to the beginning of the file
    file_object.seek(0)

    # Save the file with the hash as its name
    file_path = folder_path / file_name
    with open(file_path, "wb") as new_file:
        while chunk := file_object.read(8192):
            new_file.write(chunk)

    return file_path


def update_build_status(cache_service, flow_id: str, status: "BuildStatus"):
    cached_flow = cache_service[flow_id]
    if cached_flow is None:
        raise ValueError(f"Flow {flow_id} not found in cache")
    cached_flow["status"] = status
    cache_service[flow_id] = cached_flow
    cached_flow["status"] = status
    cache_service[flow_id] = cached_flow
