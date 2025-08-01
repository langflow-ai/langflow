from functools import lru_cache
from typing import Any

import httpx
from loguru import logger


@lru_cache(maxsize=1)
def get_cached_evaluators(url: str) -> dict[str, Any]:
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("evaluators", {})
    except httpx.RequestError as e:
        logger.error(f"Error fetching evaluators: {e}")
        return {}
