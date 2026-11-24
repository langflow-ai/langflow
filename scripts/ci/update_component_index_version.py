"""Stamp a component index with an LFX version and recompute its integrity hash."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import orjson


def update_component_index_version(index_path: str | Path, version: str) -> None:
    """Update an index version without changing its component payload."""
    filepath = Path(index_path)
    index = orjson.loads(filepath.read_bytes())
    index["version"] = version
    index.pop("sha256", None)
    payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
    index["sha256"] = hashlib.sha256(payload).hexdigest()
    json_bytes = orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
    filepath.write_bytes(json_bytes + b"\n")


def main() -> None:
    expected_args = 3
    if len(sys.argv) != expected_args:
        print("Usage: update_component_index_version.py <index_path> <version>")
        raise SystemExit(1)
    update_component_index_version(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
