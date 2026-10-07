"""Shared validation for vector-store collection names."""

from __future__ import annotations

import ipaddress
import re

MIN_COLLECTION_NAME_LENGTH = 3
MAX_COLLECTION_NAME_LENGTH = 512
MAX_LOCAL_COLLECTION_NAME_LENGTH = 255

_COLLECTION_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,510}[a-zA-Z0-9]$")


def _is_valid_name_segment(name: str) -> bool:
    if _COLLECTION_NAME_PATTERN.fullmatch(name) is None or ".." in name:
        return False
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return True
    return False


def is_valid_collection_name(name: str) -> bool:
    """Return whether ``name`` satisfies the Chroma collection-name contract."""
    if not isinstance(name, str):
        return False
    if "+" not in name:
        return _is_valid_name_segment(name)
    if len(name) > MAX_COLLECTION_NAME_LENGTH or name.count("+") != 1:
        return False
    topology, collection_name = name.split("+", 1)
    return _is_valid_name_segment(topology) and _is_valid_name_segment(collection_name)


def validate_collection_name(name: str, *, resource: str = "Collection", local: bool = False) -> None:
    """Raise an actionable error when ``name`` cannot be used by Chroma."""
    if not is_valid_collection_name(name):
        msg = (
            f"{resource} name must follow Chroma naming rules: each name must be 3-512 characters, "
            "contain only ASCII letters, numbers, periods, underscores, or hyphens, start and end "
            "with a letter or number, contain no consecutive periods, and not be an IP address. "
            "A single '+' may join a valid topology and collection name"
        )
        raise ValueError(msg)
    if local and len(name) > MAX_LOCAL_COLLECTION_NAME_LENGTH:
        msg = f"{resource} name must be at most {MAX_LOCAL_COLLECTION_NAME_LENGTH} characters for local Chroma storage"
        raise ValueError(msg)
