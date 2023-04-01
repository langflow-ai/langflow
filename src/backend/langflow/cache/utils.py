import contextlib
import hashlib
import json
import os
import tempfile
from pathlib import Path

import dill

PREFIX = "langflow_cache"


def clear_old_cache_files(max_cache_size: int = 10):
    cache_dir = Path(tempfile.gettempdir())
    cache_files = list(cache_dir.glob(f"{PREFIX}_*.dill"))

    if len(cache_files) > max_cache_size:
        cache_files_sorted_by_mtime = sorted(
            cache_files, key=lambda x: x.stat().st_mtime, reverse=True
        )

        for cache_file in cache_files_sorted_by_mtime[max_cache_size:]:
            with contextlib.suppress(OSError):
                os.remove(cache_file)


def remove_position_info(node):
    node.pop("position", None)


def compute_hash(graph_data):
    for node in graph_data["nodes"]:
        remove_position_info(node)

    cleaned_graph_json = json.dumps(graph_data, sort_keys=True)
    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()


def save_cache(hash_val, chat_data):
    cache_path = Path(tempfile.gettempdir()) / f"{PREFIX}_{hash_val}.dill"
    with cache_path.open("wb") as cache_file:
        dill.dump(chat_data, cache_file)


def load_cache(hash_val):
    cache_path = Path(tempfile.gettempdir()) / f"{PREFIX}_{hash_val}.dill"
    if cache_path.exists():
        with cache_path.open("rb") as cache_file:
            return dill.load(cache_file)
    return None
