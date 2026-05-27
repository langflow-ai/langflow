from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator


class CacheSettings(BaseModel):
    """In-memory and Redis cache settings."""

    cache_type: Literal["async", "redis", "memory"] = "async"
    """The cache backend: 'async' (default in-memory), 'memory' (sync in-memory), or 'redis'."""
    cache_expire: int = 3600
    """The cache expire in seconds."""
    cache_dir: str | None = None
    """Directory used by FlowEventsService for cross-worker event storage. Defaults to a temp dir if not set."""
    langchain_cache: str = "InMemoryCache"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None
    redis_cache_expire: int = 3600

    @field_validator("cache_dir", mode="before")
    @classmethod
    def validate_cache_dir(cls, value):
        """Validate and normalize cache_dir path."""
        if not value:
            return None

        if isinstance(value, str):
            value = Path(value)
        value = value.resolve()
        if not value.exists():
            value.mkdir(parents=True, exist_ok=True)

        return str(value)
