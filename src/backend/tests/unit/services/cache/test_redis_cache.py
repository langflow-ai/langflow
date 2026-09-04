"""Tests for RedisCache teardown functionality."""

import ssl
from unittest.mock import AsyncMock, patch

import fakeredis
import pytest
from langflow.services.cache.service import RedisCache
from lfx.services.cache.utils import CACHE_MISS


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


@pytest.mark.asyncio
class TestRedisCacheSerialization:
    """Test that RedisCache degrades gracefully on unpicklable values.

    Live objects built during a flow run (e.g. an LLM client holding an
    ``ssl.SSLContext``, httpx clients, thread locks) cannot be serialized. The
    cache write must not crash the flow build; the value should simply be
    skipped. See https://github.com/langflow-ai/langflow/issues/13764.
    """

    def _cache(self) -> RedisCache:
        with patch("redis.asyncio.StrictRedis"):
            cache = RedisCache(expiration_time=3600)
        cache._client = fakeredis.FakeAsyncRedis()
        return cache

    async def test_set_unpicklable_value_does_not_raise(self):
        """An unpicklable value (SSLContext) is skipped instead of raising.

        ``dill.dumps`` raises a bare ``TypeError`` for an ``SSLContext`` (not a
        ``pickle.PicklingError``), so the original narrow ``except`` let it
        escape and crash the build.
        """
        cache = self._cache()
        value = {"result": {"built_object": ssl.create_default_context()}, "type": dict}

        # Should not raise (previously raised TypeError: cannot pickle 'SSLContext').
        await cache.set("vertex-id", value)

        # The value was skipped, so a later read is a cache miss rather than stale data.
        assert await cache.get("vertex-id") is CACHE_MISS

    async def test_upsert_unpicklable_value_does_not_raise(self):
        """upsert() (used by the build cache path) also degrades gracefully."""
        cache = self._cache()
        value = {"built_object": ssl.create_default_context()}

        await cache.upsert("vertex-id", value)

        assert await cache.get("vertex-id") is CACHE_MISS

    async def test_picklable_value_still_round_trips(self):
        """Regression: ordinary picklable values continue to cache and load."""
        cache = self._cache()
        value = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}

        await cache.set("ok-key", value)

        assert await cache.get("ok-key") == value

    async def test_unpicklable_set_evicts_stale_value(self):
        """A skipped write must drop any previously cached value for that key.

        ``upsert`` is get -> merge -> set; if a later value is unserializable we
        skip the write, but a stale entry left in Redis would be served on the
        next get() instead of triggering recomputation.
        """
        cache = self._cache()
        await cache.set("vertex-id", {"built_object": "old-serializable"})
        assert await cache.get("vertex-id") == {"built_object": "old-serializable"}

        # New value for the same key is unserializable -> write skipped...
        await cache.upsert("vertex-id", {"built_object": ssl.create_default_context()})

        # ...and the stale entry is gone, so the next access recomputes.
        assert await cache.get("vertex-id") is CACHE_MISS
