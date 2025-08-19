import re
from typing import Any

from langchain_core.messages import BaseMessage
from loguru import logger

from lfx.schema.data import Data
from lfx.services.cache.base import CacheService
from lfx.services.cache.utils import CacheMiss


def data_to_messages(data: list[Data]) -> list[BaseMessage]:
    """Convert a list of data to a list of messages.

    Args:
        data (List[Data]): The data to convert.

    Returns:
        List[Message]: The data as messages.
    """
    return [value.to_lc_message() for value in data]


def safe_cache_get(cache: CacheService, key, default=None):
    """Safely get a value from cache, handling CacheMiss objects."""
    try:
        value = cache.get(key)
        if isinstance(value, CacheMiss):
            return default
    except (AttributeError, KeyError, TypeError):
        return default
    else:
        return value


def safe_cache_set(cache: CacheService, key, value):
    """Safely set a value in cache, handling potential errors."""
    try:
        cache.set(key, value)
    except (AttributeError, TypeError) as e:
        logger.warning(f"Failed to set cache key '{key}': {e}")


def maybe_unflatten_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """If any key looks nested (contains a dot or "[index]"), rebuild the.

    full nested structure; otherwise return flat as is.
    """
    # Quick check: do we have any nested keys?
    if not any(re.search(r"\.|\[\d+\]", key) for key in flat):
        return flat

    # Otherwise, unflatten into dicts/lists
    nested: dict[str, Any] = {}
    array_re = re.compile(r"^(.+)\[(\d+)\]$")

    for key, val in flat.items():
        parts = key.split(".")
        cur = nested
        for i, part in enumerate(parts):
            m = array_re.match(part)
            # Array segment?
            if m:
                name, idx = m.group(1), int(m.group(2))
                lst = cur.setdefault(name, [])
                # Ensure list is big enough
                while len(lst) <= idx:
                    lst.append({})
                if i == len(parts) - 1:
                    lst[idx] = val
                else:
                    cur = lst[idx]
            # Normal object key
            elif i == len(parts) - 1:
                cur[part] = val
            else:
                cur = cur.setdefault(part, {})

    return nested
