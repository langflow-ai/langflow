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


_MARKER_PATH_HOLDER: list[str] = []


def _deser_side_effect(path: str) -> str:
    """Module-level callable used as a pickle reduce gadget in the test below."""
    _MARKER_PATH_HOLDER.append(path)
    return path


class _Gadget:
    """A picklable object whose deserialization would run _deser_side_effect."""

    def __init__(self, path: str) -> None:
        self.path = path

    def __reduce__(self):
        return (_deser_side_effect, (self.path,))


@pytest.mark.asyncio
class TestRedisCacheDeserializationIntegrity:
    """Regression (insecure dill.loads of untrusted Redis bytes)."""

    async def test_get_rejects_payload_without_valid_hmac(self):
        """A payload lacking a valid HMAC tag must not be deserialized (no gadget run)."""
        import dill
        from lfx.services.cache.utils import CACHE_MISS

        _MARKER_PATH_HOLDER.clear()
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32  # inject a fixed key (no settings dependency)

            # Attacker-written value: a reduce gadget, prefixed with a WRONG 32-byte tag.
            forged = b"\x00" * cache._HMAC_DIGEST_SIZE + dill.dumps(_Gadget("gadget-ran"))
            mock_client.get.return_value = forged

            result = await cache.get("k")

            assert result is CACHE_MISS  # rejected before dill.loads
            assert _MARKER_PATH_HOLDER == []  # gadget never executed

    async def test_get_rejects_payload_shorter_than_tag(self):
        """A value too short to even hold a tag is a miss (cheapest attacker write)."""
        from lfx.services.cache.utils import CACHE_MISS

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32

            # Fewer bytes than the HMAC tag length: rejected before any slicing/HMAC.
            mock_client.get.return_value = b"short"

            assert await cache.get("k") is CACHE_MISS

    async def test_set_get_roundtrip_with_signature(self):
        """Values written by set() carry a valid tag and round-trip through get()."""
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32

            store: dict[str, bytes] = {}

            async def fake_setex(key, _ttl, value):
                store[key] = value
                return True

            async def fake_get(key):
                return store.get(key)

            mock_client.setex.side_effect = fake_setex
            mock_client.get.side_effect = fake_get

            await cache.set("k", {"a": 1, "b": [2, 3]})
            assert await cache.get("k") == {"a": 1, "b": [2, 3]}

    async def test_get_rejects_payload_replayed_under_different_key(self):
        """A validly-signed entry must not verify when relocated to another key.

        The integrity tag is bound to the namespaced Redis key, so copying a
        legitimately-signed payload from key ``a`` into the slot for key ``b``
        (cross-key substitution) is rejected as a miss instead of deserialized.
        """
        from lfx.services.cache.utils import CACHE_MISS

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32

            store: dict[str, bytes] = {}

            async def fake_setex(key, _ttl, value):
                store[key] = value
                return True

            async def fake_get(key):
                return store.get(key)

            mock_client.setex.side_effect = fake_setex
            mock_client.get.side_effect = fake_get

            # Write a real, validly-signed entry under key "a".
            await cache.set("a", {"secret": "for-a"})
            assert await cache.get("a") == {"secret": "for-a"}

            # Attacker relocates a's signed bytes into b's namespaced slot.
            store[cache._key("b")] = store[cache._key("a")]

            # The tag was bound to "a"'s key, so it fails verification under "b".
            assert await cache.get("b") is CACHE_MISS
