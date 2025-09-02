from functools import lru_cache
from typing import Any

import httpx

from langflow.logging.logger import logger


@lru_cache(maxsize=1)
def get_cached_evaluators(url: str) -> dict[str, Any]:
    return _fetch_evaluators(url)


def _fetch_evaluators(url: str) -> dict[str, Any]:
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("evaluators", {})
    except httpx.RequestError as e:
        logger.error(f"Error fetching evaluators: {e}")
        return {}
    except (httpx.HTTPStatusError, ValueError, KeyError) as e:
        logger.error(f"Unexpected error fetching evaluators: {e}")
        return {}


def get_fresh_evaluators(url: str) -> dict[str, Any]:
    get_cached_evaluators.cache_clear()
    fresh_data = _fetch_evaluators(url)
    get_cached_evaluators(url)  # Re-seed the cache
    return fresh_data
