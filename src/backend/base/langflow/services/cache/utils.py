import base64
import contextlib
import hashlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import UploadFile
from platformdirs import user_cache_dir

if TYPE_CHECKING:
    from langflow.api.v1.schemas import BuildStatus

CACHE: dict[str, Any] = {}

CACHE_DIR = user_cache_dir("langflow", "langflow")

PREFIX = "langflow_cache"


class CacheMiss:
    def __repr__(self) -> str:
        return "<CACHE_MISS>"

    def __bool__(self) -> bool:
        return False


def create_cache_folder(func):
    def wrapper(*args, **kwargs):
        # Get the destination folder
        cache_path = Path(CACHE_DIR) / PREFIX

        # Create the destination folder if it doesn't exist
        cache_path.mkdir(parents=True, exist_ok=True)

        return func(*args, **kwargs)

    return wrapper


@create_cache_folder
def clear_old_cache_files(max_cache_size: int = 3) -> None:
    cache_dir = Path(tempfile.gettempdir()) / PREFIX
    cache_files = list(cache_dir.glob("*.dill"))

    if len(cache_files) > max_cache_size:
        cache_files_sorted_by_mtime = sorted(cache_files, key=lambda x: x.stat().st_mtime, reverse=True)

        for cache_file in cache_files_sorted_by_mtime[max_cache_size:]:
            with contextlib.suppress(OSError):
                cache_file.unlink()


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
    """Save a binary file to the specified folder.

    Args:
        content: The content of the file as a bytes object.
        file_name: The name of the file, including its extension.
        accepted_types: A list of accepted file types.

    Returns:
        The path to the saved file.
    """
    if not any(file_name.endswith(suffix) for suffix in accepted_types):
        msg = f"File {file_name} is not accepted"
        raise ValueError(msg)

    # Get the destination folder
    cache_path = Path(CACHE_DIR) / PREFIX
    if not content:
        msg = "Please, reload the file in the loader."
        raise ValueError(msg)
    data = content.split(",")[1]
    decoded_bytes = base64.b64decode(data)

    # Create the full file path
    file_path = cache_path / file_name

    # Save the binary content to the file
    file_path.write_bytes(decoded_bytes)

    return str(file_path)


@create_cache_folder
def save_uploaded_file(file: UploadFile, folder_name):
    """Save an uploaded file to the specified folder with a hash of its content as the file name.

    Args:
        file: The uploaded file object.
        folder_name: The name of the folder to save the file in.

    Returns:
        The path to the saved file.
    """
    cache_path = Path(CACHE_DIR)
    folder_path = cache_path / folder_name
    filename = file.filename
    file_extension = Path(filename).suffix if isinstance(filename, str | Path) else ""
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

    with file_path.open("wb") as new_file:
        while chunk := file_object.read(8192):
            new_file.write(chunk)

    return file_path


def update_build_status(cache_service, flow_id: str, status: "BuildStatus") -> None:
    cached_flow = cache_service[flow_id]
    if cached_flow is None:
        msg = f"Flow {flow_id} not found in cache"
        raise ValueError(msg)
    cached_flow["status"] = status
    cache_service[flow_id] = cached_flow
    cached_flow["status"] = status
    cache_service[flow_id] = cached_flow


CACHE_MISS = CacheMiss()
