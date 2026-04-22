"""Tests for RedisCache teardown functionality."""

from unittest.mock import AsyncMock, patch

import pytest
from langflow.services.cache.service import RedisCache


@pytest.mark.asyncio
class TestRedisCacheTeardown:
    """Test RedisCache teardown functionality."""

    async def test_teardown_closes_redis_client(self):
        """Test that teardown() calls aclose() on the Redis client."""
        # Mock the Redis client
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client

            # Create RedisCache instance
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)

            # Verify the client was created
            assert cache._client is mock_client

            # Call teardown
            await cache.teardown()

            # Verify aclose was called
            mock_client.aclose.assert_called_once()

    async def test_teardown_with_url(self):
        """Test that teardown() works with Redis URL configuration."""
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client

            # Create RedisCache instance with URL
            cache = RedisCache(url="redis://localhost:6379/0", expiration_time=3600)

            # Verify the client was created with from_url
            mock_redis_class.from_url.assert_called_once_with("redis://localhost:6379/0")
            assert cache._client is mock_client

            # Call teardown
            await cache.teardown()

            # Verify aclose was called
            mock_client.aclose.assert_called_once()

    async def test_is_external_async_base_cache_service(self):
        """Test that RedisCache is an instance of ExternalAsyncBaseCacheService."""
        from langflow.services.cache.base import ExternalAsyncBaseCacheService

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client

            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)

            # Verify it's an instance of ExternalAsyncBaseCacheService
            assert isinstance(cache, ExternalAsyncBaseCacheService)

            # Verify teardown method exists and is callable
            assert hasattr(cache, "teardown")
            assert callable(cache.teardown)

            # Clean up
            await cache.teardown()

    async def test_preload_teardown_pattern(self):
        """Test the teardown pattern used in preload.py.

        ``teardown`` is now an abstract method on ``ExternalAsyncBaseCacheService``,
        so preload can call it directly without ``getattr`` fallbacks.
        """
        from langflow.services.cache.base import ExternalAsyncBaseCacheService

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client

            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)

            if isinstance(cache, ExternalAsyncBaseCacheService):
                await cache.teardown()

            mock_client.aclose.assert_called_once()
