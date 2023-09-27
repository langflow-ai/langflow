import base64
import contextlib
import functools
import hashlib
import os
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict
from appdirs import user_cache_dir
from fastapi import UploadFile
from langflow.api.v1.schemas import BuildStatus
from langflow.services.database.models.base import orjson_dumps

if TYPE_CHECKING:
    pass

CACHE: Dict[str, Any] = {}

CACHE_DIR = user_cache_dir("langflow", "langflow")


def create_cache_folder(func):
    def wrapper(*args, **kwargs):
        # Get the destination folder
        cache_path = Path(CACHE_DIR) / PREFIX

        # Create the destination folder if it doesn't exist
        os.makedirs(cache_path, exist_ok=True)

        return func(*args, **kwargs)

    return wrapper


def memoize_dict(maxsize=128):
    cache = OrderedDict()
    hash_to_key = {}  # Mapping from hash to cache key

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            hashed = compute_dict_hash(args[0])
            key = (func.__name__, hashed, frozenset(kwargs.items()))
            if key not in cache:
                result = func(*args, **kwargs)
                cache[key] = result
                hash_to_key[hashed] = key  # Store the mapping
                if len(cache) > maxsize:
                    oldest_key = next(iter(cache))
                    oldest_hash = oldest_key[1]
                    del cache[oldest_key]
                    del hash_to_key[oldest_hash]
            else:
                result = cache[key]

            wrapper.session_id = hashed  # Store hash in the wrapper
            return result

        def clear_cache():
            cache.clear()
            hash_to_key.clear()

        def get_result_by_session_id(session_id):
            key = hash_to_key.get(session_id)
            return cache.get(key) if key is not None else None

        wrapper.clear_cache = clear_cache  # type: ignore
        wrapper.get_result_by_session_id = get_result_by_session_id  # type: ignore
        wrapper.hash = None
        wrapper.cache = cache  # type: ignore
        return wrapper

    return decorator


PREFIX = "langflow_cache"


@create_cache_folder
def clear_old_cache_files(max_cache_size: int = 3):
    cache_dir = Path(tempfile.gettempdir()) / PREFIX
    cache_files = list(cache_dir.glob("*.dill"))

    if len(cache_files) > max_cache_size:
        cache_files_sorted_by_mtime = sorted(
            cache_files, key=lambda x: x.stat().st_mtime, reverse=True
        )

        for cache_file in cache_files_sorted_by_mtime[max_cache_size:]:
            with contextlib.suppress(OSError):
                os.remove(cache_file)


def compute_dict_hash(graph_data):
    graph_data = filter_json(graph_data)

    cleaned_graph_json = orjson_dumps(graph_data, sort_keys=True)

    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()


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


def update_build_status(cache_service, flow_id: str, status: BuildStatus):
    cached_flow = cache_service[flow_id]
    if cached_flow is None:
        raise ValueError(f"Flow {flow_id} not found in cache")
    cached_flow["status"] = status
    cache_service[flow_id] = cached_flow
