from typing import Literal

from pydantic import BaseModel


class CacheSettings(BaseModel):
    """In-memory, disk, and Redis cache settings."""

    cache_type: Literal["async", "redis", "memory", "disk"] = "async"
    """The cache type can be 'async' or 'redis'."""
    cache_expire: int = 3600
    """The cache expire in seconds."""
    langchain_cache: str = "InMemoryCache"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None
    redis_cache_expire: int = 3600
