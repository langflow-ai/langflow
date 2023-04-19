import base64
import contextlib
import functools
import hashlib

import json
import os
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any
from PIL import Image
import dill
import pandas as pd  # type: ignore

CACHE = {}


def create_cache_folder(func):
    def wrapper(*args, **kwargs):
        # Get the destination folder
        cache_path = Path(tempfile.gettempdir()) / PREFIX

        # Create the destination folder if it doesn't exist
        os.makedirs(cache_path, exist_ok=True)

        return func(*args, **kwargs)

    return wrapper


def memoize_dict(maxsize=128):
    cache = OrderedDict()

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            hashed = compute_dict_hash(args[0])
            key = (func.__name__, hashed, frozenset(kwargs.items()))
            if key not in cache:
                result = func(*args, **kwargs)
                cache[key] = result
                if len(cache) > maxsize:
                    cache.popitem(last=False)
            else:
                result = cache[key]
            return result

        def clear_cache():
            cache.clear()

        wrapper.clear_cache = clear_cache
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

    cleaned_graph_json = json.dumps(graph_data, sort_keys=True)
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
    cache_path = Path(tempfile.gettempdir()) / PREFIX

    data = content.split(",")[1]
    decoded_bytes = base64.b64decode(data)

    # Create the full file path
    file_path = os.path.join(cache_path, file_name)

    # Save the binary content to the file
    with open(file_path, "wb") as file:
        file.write(decoded_bytes)

    return file_path


@create_cache_folder
def save_cache(hash_val: str, chat_data, clean_old_cache_files: bool):
    cache_path = Path(tempfile.gettempdir()) / PREFIX / f"{hash_val}.dill"
    with cache_path.open("wb") as cache_file:
        dill.dump(chat_data, cache_file)

    if clean_old_cache_files:
        clear_old_cache_files()


@create_cache_folder
def load_cache(hash_val):
    cache_path = Path(tempfile.gettempdir()) / PREFIX / f"{hash_val}.dill"
    if cache_path.exists():
        with cache_path.open("rb") as cache_file:
            return dill.load(cache_file)
    return None


def add_pandas(name: str, obj: Any):
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        CACHE[name] = {"obj": obj, "type": "pandas"}
    else:
        raise ValueError("Object is not a pandas DataFrame or Series")


def add_image(name: str, obj: Any):
    if isinstance(obj, Image.Image):
        CACHE[name] = {"obj": obj, "type": "image"}
    else:
        raise ValueError("Object is not a PIL Image")


def get(name: str):
    return CACHE.get(name, {}).get("obj", None)


# get last added item
def get_last():
    obj_dict = list(CACHE.values())[-1]
    if obj_dict["type"] == "pandas":
        # return a csv string
        return obj_dict["obj"].to_csv()
    elif obj_dict["type"] == "image":
        # return a base64 encoded string
        return base64.b64encode(obj_dict["obj"].tobytes()).decode("utf-8")
    return obj_dict["obj"]
