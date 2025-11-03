"""
Token-Centric Cache Service

This service provides in-memory caching for Keycloak token validation results.
Ported from genesis-bff's token-centric caching pattern to replicate BFF functionality.

Uses token as the primary cache key, allowing for:
- Fast token validation lookups
- Easy cache invalidation on logout (single key delete)
- TTL-based automatic expiration
"""

import time
from typing import Any

from loguru import logger


class CacheEntry:
    """Represents a single cache entry with value and expiration time."""

    def __init__(self, value: Any, ttl: int):
        """
        Initialize cache entry.

        Args:
            value: The value to cache
            ttl: Time-to-live in seconds
        """
        self.value = value
        self.expires_at = time.time() + ttl if ttl > 0 else float("inf")

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > self.expires_at


class TokenCache:
    """
    In-memory cache for token validation results.

    This replicates the token-centric caching pattern from genesis-bff's CacheService.
    All data is stored under a token key for simplified operations and logout.

    Cache TTL values match BFF's CacheTime configuration:
    - ACCESS_TOKEN: 604800 seconds (7 days)
    """

    # Default TTL values from BFF's CacheTime configuration
    DEFAULT_TTL = {
        "ACCESS_TOKEN": 604800,  # 7 days
        "REFRESH_TOKEN": 2419200,  # 28 days
        "USER_CLIENT_INFO": 604800,  # 7 days
        "RESOURCE_ACCESS": 2419200,  # 28 days
        "PERMISSION_DENIAL": 604800,  # 7 days
        "SHORT_TERM": 60,  # 1 minute
        "MEDIUM_TERM": 300,  # 5 minutes
        "LONG_TERM": 3600,  # 1 hour
    }

    def __init__(self):
        """Initialize the token cache with empty storage."""
        self._cache: dict[str, CacheEntry] = {}
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "evictions": 0}
        logger.info("TokenCache initialized (in-memory cache)")

    def _get_token_key(self, token: str) -> str:
        """
        Get cache key for a token.

        Uses last 8 characters of token for logging/debugging while using
        full token as the actual key (for security).

        Args:
            token: The access token

        Returns:
            Cache key string
        """
        # Remove 'Bearer ' prefix if present
        clean_token = token.replace("Bearer ", "").strip() if token.startswith("Bearer ") else token
        return f"token:{clean_token}"

    def _evict_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries evicted
        """
        before_count = len(self._cache)
        self._cache = {k: v for k, v in self._cache.items() if not v.is_expired()}
        evicted = before_count - len(self._cache)

        if evicted > 0:
            self._stats["evictions"] += evicted
            logger.debug(f"Evicted {evicted} expired cache entries")

        return evicted

    async def cache_token_validation(self, token: str, user_data: dict[str, Any], ttl: int | None = None) -> None:
        """
        Cache token validation result.

        Args:
            token: The access token
            user_data: The validated user data from Keycloak
            ttl: Time-to-live in seconds (defaults to ACCESS_TOKEN TTL: 7 days)
        """
        cache_key = self._get_token_key(token)
        ttl = ttl or self.DEFAULT_TTL["ACCESS_TOKEN"]

        # Store validation result with metadata
        cache_value = {
            "isValid": True,
            "userData": user_data,
            "cachedAt": time.time(),
        }

        self._cache[cache_key] = CacheEntry(cache_value, ttl)
        self._stats["sets"] += 1

        # Periodically evict expired entries (every 100 sets)
        if self._stats["sets"] % 100 == 0:
            self._evict_expired()

        token_preview = token[-8:] if len(token) > 8 else "****"
        logger.info(
            f"[CACHE]: Token validation cached under token:***{token_preview} " f"(TTL: {ttl}s, Total entries: {len(self._cache)})"
        )

    async def get_token_validation(self, token: str) -> dict[str, Any] | None:
        """
        Get cached token validation result.

        Args:
            token: The access token

        Returns:
            Cached validation result or None if not found/expired
        """
        cache_key = self._get_token_key(token)
        entry = self._cache.get(cache_key)

        token_preview = token[-8:] if len(token) > 8 else "****"

        # Cache miss or expired
        if entry is None or entry.is_expired():
            self._stats["misses"] += 1

            # Clean up if expired
            if entry is not None and entry.is_expired():
                del self._cache[cache_key]
                self._stats["evictions"] += 1
                logger.debug(f"[CACHE]: Token validation cache expired for token:***{token_preview}")
            else:
                logger.debug(f"[CACHE]: Token validation cache miss for token:***{token_preview}")

            return None

        # Cache hit
        self._stats["hits"] += 1
        logger.info(f"[CACHE]: Token validation cache hit for token:***{token_preview}")

        return entry.value

    async def invalidate_token(self, token: str) -> None:
        """
        Invalidate all cached data for a token (used on logout).

        Args:
            token: The access token to invalidate
        """
        cache_key = self._get_token_key(token)

        if cache_key in self._cache:
            del self._cache[cache_key]
            self._stats["deletes"] += 1

            token_preview = token[-8:] if len(token) > 8 else "****"
            logger.info(f"[CACHE]: Invalidated token:***{token_preview}")
        else:
            logger.debug(f"[CACHE]: No cache entry found to invalidate for token")

    async def clear_all(self) -> None:
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"[CACHE]: Cleared all cache entries (removed {count} entries)")

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            "entries": len(self._cache),
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
            "evictions": self._stats["evictions"],
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
        }

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on cache.

        Returns:
            Health status dictionary
        """
        try:
            # Clean up expired entries
            evicted = self._evict_expired()

            return {
                "status": "healthy",
                "type": "in-memory",
                "entries": len(self._cache),
                "stats": self.get_stats(),
                "evicted_on_check": evicted,
            }
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {"status": "unhealthy", "type": "in-memory", "error": str(e)}


# Singleton instance
_token_cache_instance: TokenCache | None = None


def get_token_cache() -> TokenCache:
    """
    Get or create the singleton TokenCache instance.

    Returns:
        The global TokenCache instance
    """
    global _token_cache_instance
    if _token_cache_instance is None:
        _token_cache_instance = TokenCache()
    return _token_cache_instance
