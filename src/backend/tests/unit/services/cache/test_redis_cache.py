"""Tests for RedisCache service."""

from unittest.mock import AsyncMock, patch

import pytest
from langflow.services.cache.service import RedisCache


@pytest.mark.asyncio
class TestRedisCacheTeardown:
    """Test teardown operations in RedisCache to prevent fork-safety issues."""

    async def test_teardown_closes_client(self):
        """Test that teardown properly closes the Redis client connection.

        This test verifies the fix for the fork-safety bug where RedisCache
        had no teardown() override, causing workers to fork with a shared
        Redis TCP socket. The teardown() method must close the connection
        before fork to prevent socket leaks.
        """
        # Mock the Redis client to avoid needing a real Redis instance
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client

            # Create RedisCache instance
            cache = RedisCache(
                host="localhost",
                port=6379,
                db=0,
                expiration_time=3600,
            )

            # Verify client was created
            assert cache._client is not None

            # Call teardown
            await cache.teardown()

            # Verify close() was called on the client
            mock_client.close.assert_awaited_once()

    async def test_teardown_handles_close_error(self):
        """Test that teardown handles errors gracefully during close.

        If the Redis client fails to close (e.g., already closed, network issue),
        the teardown should log a warning but not raise an exception.
        """
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            # Make close() raise an exception
            mock_client.close.side_effect = Exception("Connection already closed")
            mock_redis_class.return_value = mock_client

            cache = RedisCache(
                host="localhost",
                port=6379,
                db=0,
                expiration_time=3600,
            )

            # Teardown should not raise despite close() error
            try:
                await cache.teardown()
            except Exception as e:
                pytest.fail(f"teardown() raised an exception: {e}")

            # Verify close() was attempted
            mock_client.close.assert_awaited_once()

    async def test_teardown_with_url_connection(self):
        """Test teardown works with URL-based connection."""
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client

            # Create cache with URL instead of host/port
            cache = RedisCache(
                url="redis://localhost:6379/0",
                expiration_time=3600,
            )

            # Call teardown
            await cache.teardown()

            # Verify close() was called
            mock_client.close.assert_awaited_once()
