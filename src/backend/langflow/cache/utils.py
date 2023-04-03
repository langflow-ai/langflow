import contextlib
import hashlib
import json
import os
import tempfile
from pathlib import Path

import dill  # type: ignore

PREFIX = "langflow_cache"


def clear_old_cache_files(max_cache_size: int = 3):
    cache_dir = Path(tempfile.gettempdir())
    cache_files = list(cache_dir.glob(f"{PREFIX}_*.dill"))

    if len(cache_files) > max_cache_size:
        cache_files_sorted_by_mtime = sorted(
            cache_files, key=lambda x: x.stat().st_mtime, reverse=True
        )

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


def compute_hash(graph_data):
    graph_data = filter_json(graph_data)

    cleaned_graph_json = json.dumps(graph_data, sort_keys=True)
    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()


def save_cache(hash_val: str, chat_data, clean_old_cache_files: bool):
    cache_path = Path(tempfile.gettempdir()) / f"{PREFIX}_{hash_val}.dill"
    with cache_path.open("wb") as cache_file:
        dill.dump(chat_data, cache_file)

    if clean_old_cache_files:
        clear_old_cache_files()


def load_cache(hash_val):
    cache_path = Path(tempfile.gettempdir()) / f"{PREFIX}_{hash_val}.dill"
    if cache_path.exists():
        with cache_path.open("rb") as cache_file:
            return dill.load(cache_file)
    return None
