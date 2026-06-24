import asyncio
import atexit
import hashlib
import hmac
import os
import pickle
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Generic, Union

import dill
from lfx.log.logger import logger
from lfx.services.cache.utils import CACHE_MISS
from typing_extensions import override

from langflow.services.cache.base import (
    AsyncBaseCacheService,
    AsyncLockType,
    CacheService,
    ExternalAsyncBaseCacheService,
    LockType,
)

_redis_cache_experimental_warning_lock = threading.Lock()
_redis_cache_experimental_warning_emitted = False


def _warn_redis_experimental_once() -> None:
    """Emit the RedisCache experimental warning only once per server run."""
    global _redis_cache_experimental_warning_emitted  # noqa: PLW0603

    with _redis_cache_experimental_warning_lock:
        if _redis_cache_experimental_warning_emitted:
            return
        _redis_cache_experimental_warning_emitted = True

    # Cross-process deduplication: all workers forked from the same master
    # share the same getppid() value, so they all target the same sentinel.
    sentinel = Path(tempfile.gettempdir()) / f"langflow_redis_cache_warned_{os.getppid()}.sentinel"
    try:
        fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        return  # Another worker already logged the warning

    # Best-effort cleanup so we don't leave a stale file in /tmp after every restart.
    atexit.register(sentinel.unlink, missing_ok=True)

    logger.warning(
        "RedisCache is an experimental feature and may not work as expected."
        " Please report any issues to our GitHub repository."
    )


class ThreadingInMemoryCache(CacheService, Generic[LockType]):
    """A simple in-memory cache using an OrderedDict.

    This cache supports setting a maximum size and expiration time for cached items.
    When the cache is full, it uses a Least Recently Used (LRU) eviction policy.
    Thread-safe using a threading Lock.

    Attributes:
        max_size (int, optional): Maximum number of items to store in the cache.
        expiration_time (int, optional): Time in seconds after which a cached item expires. Default is 1 hour.

    Example:
        cache = InMemoryCache(max_size=3, expiration_time=5)

        # setting cache values
        cache.set("a", 1)
        cache.set("b", 2)
        cache["c"] = 3

        # getting cache values
        a = cache.get("a")
        b = cache["b"]
    """

    def __init__(self, max_size=None, expiration_time=60 * 60) -> None:
        """Initialize a new InMemoryCache instance.

        Args:
            max_size (int, optional): Maximum number of items to store in the cache.
            expiration_time (int, optional): Time in seconds after which a cached item expires. Default is 1 hour.
        """
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self.max_size = max_size
        self.expiration_time = expiration_time

    def get(self, key, lock: Union[threading.Lock, None] = None):  # noqa: UP007
        """Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.
            lock: A lock to use for the operation.

        Returns:
            The value associated with the key, or CACHE_MISS if the key is not found or the item has expired.
        """
        with lock or self._lock:
            return self._get_without_lock(key)

    def _get_without_lock(self, key):
        """Retrieve an item from the cache without acquiring the lock."""
        if item := self._cache.get(key):
            if self.expiration_time is None or time.time() - item["time"] < self.expiration_time:
                # Move the key to the end to make it recently used
                self._cache.move_to_end(key)
                # Check if the value is pickled
                return pickle.loads(item["value"]) if isinstance(item["value"], bytes) else item["value"]
            self.delete(key)
        return CACHE_MISS

    def set(self, key, value, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        """Add an item to the cache.

        If the cache is full, the least recently used item is evicted.

        Args:
            key: The key of the item.
            value: The value to cache.
            lock: A lock to use for the operation.
        """
        with lock or self._lock:
            if key in self._cache:
                # Remove existing key before re-inserting to update order
                self.delete(key)
            elif self.max_size and len(self._cache) >= self.max_size:
                # Remove least recently used item
                self._cache.popitem(last=False)
            # pickle locally to mimic Redis

            self._cache[key] = {"value": value, "time": time.time()}

    def upsert(self, key, value, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        """Inserts or updates a value in the cache.

        If the existing value and the new value are both dictionaries, they are merged.

        Args:
            key: The key of the item.
            value: The value to insert or update.
            lock: A lock to use for the operation.
        """
        with lock or self._lock:
            existing_value = self._get_without_lock(key)
            if existing_value is not CACHE_MISS and isinstance(existing_value, dict) and isinstance(value, dict):
                existing_value.update(value)
                value = existing_value

            self.set(key, value)

    def get_or_set(self, key, value, lock: Union[threading.Lock, None] = None):  # noqa: UP007
        """Retrieve an item from the cache.

        If the item does not exist, set it with the provided value.

        Args:
            key: The key of the item.
            value: The value to cache if the item doesn't exist.
            lock: A lock to use for the operation.

        Returns:
            The cached value associated with the key.
        """
        with lock or self._lock:
            if key in self._cache:
                return self.get(key)
            self.set(key, value)
            return value

    def delete(self, key, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        with lock or self._lock:
            self._cache.pop(key, None)

    def clear(self, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        """Clear all items from the cache."""
        with lock or self._lock:
            self._cache.clear()

    def contains(self, key) -> bool:
        """Check if the key is in the cache."""
        return key in self._cache

    def __contains__(self, key) -> bool:
        """Check if the key is in the cache."""
        return self.contains(key)

    def __getitem__(self, key):
        """Retrieve an item from the cache using the square bracket notation."""
        return self.get(key)

    def __setitem__(self, key, value) -> None:
        """Add an item to the cache using the square bracket notation."""
        self.set(key, value)

    def __delitem__(self, key) -> None:
        """Remove an item from the cache using the square bracket notation."""
        self.delete(key)

    def __len__(self) -> int:
        """Return the number of items in the cache."""
        return len(self._cache)

    def __repr__(self) -> str:
        """Return a string representation of the InMemoryCache instance."""
        return f"InMemoryCache(max_size={self.max_size}, expiration_time={self.expiration_time})"


class RedisCache(ExternalAsyncBaseCacheService, Generic[LockType]):
    """A Redis-based cache implementation.

    This cache supports setting an expiration time for cached items.

    Attributes:
        expiration_time (int, optional): Time in seconds after which a cached item expires. Default is 1 hour.

    Example:
        cache = RedisCache(expiration_time=5)

        # setting cache values
        cache.set("a", 1)
        cache.set("b", 2)
        cache["c"] = 3

        # getting cache values
        a = cache.get("a")
        b = cache["b"]
    """

    KEY_PREFIX = "langflow:cache:"

    # Size of the HMAC-SHA256 tag prepended to every stored payload.
    _HMAC_DIGEST_SIZE = hashlib.sha256().digest_size

    def __init__(self, host="localhost", port=6379, db=0, url=None, expiration_time=60 * 60) -> None:
        """Initialize a new RedisCache instance.

        Args:
            host (str, optional): Redis host.
            port (int, optional): Redis port.
            db (int, optional): Redis DB.
            url (str, optional): Redis URL.
            expiration_time (int, optional): Time in seconds after which a
                cached item expires. Default is 1 hour.
        """
        # Redis is a main dependency, no need to import check
        from redis.asyncio import StrictRedis

        _warn_redis_experimental_once()
        if url:
            self._client = StrictRedis.from_url(url)
        else:
            self._client = StrictRedis(host=host, port=port, db=db)
        self.expiration_time = expiration_time
        self._signing_key: bytes | None = None

    def _key(self, key) -> str:
        """Return the namespaced Redis key."""
        return f"{self.KEY_PREFIX}{key}"

    def _get_signing_key(self) -> bytes:
        """Derive the HMAC key for cache payload integrity from the server secret.

        Bound to the same ``SECRET_KEY`` used elsewhere, so no extra config is
        required. Cached after first use (the secret does not change at runtime).
        """
        if self._signing_key is None:
            from langflow.services.deps import get_settings_service

            secret = get_settings_service().auth_settings.SECRET_KEY.get_secret_value()
            self._signing_key = hashlib.sha256(b"langflow-redis-cache-hmac:" + secret.encode()).digest()
        return self._signing_key

    def _integrity_tag(self, namespaced_key: str, payload: bytes) -> bytes:
        """Compute the HMAC-SHA256 tag binding ``payload`` to ``namespaced_key``.

        The Redis key is mixed in as associated authenticated data so a tag is
        only valid for the exact key the payload was written under. Without this
        binding, a payload signed for one key verifies under any other key,
        letting anyone with write access to the ``langflow:cache:`` namespace
        relocate/replay a validly-signed entry across keys (cross-key
        substitution → type confusion / stale-value injection) without ever
        knowing the secret. The key is length-prefixed so the (key, payload)
        framing is unambiguous and bytes cannot be shifted across the boundary
        while keeping a valid tag.
        """
        mac = hmac.new(self._get_signing_key(), digestmod=hashlib.sha256)
        key_bytes = namespaced_key.encode("utf-8")
        mac.update(len(key_bytes).to_bytes(8, "big"))
        mac.update(key_bytes)
        mac.update(payload)
        return mac.digest()

    async def is_connected(self) -> bool:
        """Check if the Redis client is connected."""
        import redis

        try:
            await self._client.ping()
        except redis.exceptions.ConnectionError:
            msg = "RedisCache could not connect to the Redis server"
            await logger.aexception(msg)
            return False
        return True

    @override
    async def get(self, key, lock=None):
        if key is None:
            return CACHE_MISS
        namespaced_key = self._key(key)
        value = await self._client.get(namespaced_key)
        if not value:
            return CACHE_MISS
        # Integrity check before deserializing. The Redis datastore is an
        # untrusted boundary (a co-tenant on a shared Redis, an exposed/un-ACL'd
        # port, or anyone able to write under the langflow:cache: namespace could
        # plant a payload). dill.loads() executes embedded reduce gadgets, so we
        # only deserialize bytes carrying a valid HMAC produced with the server
        # secret. Unsigned/tampered/legacy entries are treated as a miss and are
        # never passed to dill.loads (CWE-502).
        if len(value) < self._HMAC_DIGEST_SIZE:
            return CACHE_MISS
        tag, payload = value[: self._HMAC_DIGEST_SIZE], value[self._HMAC_DIGEST_SIZE :]
        expected = self._integrity_tag(namespaced_key, payload)
        if not hmac.compare_digest(tag, expected):
            await logger.awarning("RedisCache: discarding cache entry with an invalid integrity tag")
            return CACHE_MISS
        return dill.loads(payload)

    @override
    async def set(self, key, value, lock=None) -> None:
        # Serialize first, in isolation from the network write. Live objects built during
        # a flow run -- LLM clients holding an ``ssl.SSLContext``, httpx clients, thread
        # locks, dynamically-created pydantic models -- are inherently unpicklable, and
        # dill signals this with a variety of exception types (a bare ``TypeError`` for an
        # SSLContext, ``AttributeError`` for dynamic classes, ``RecursionError`` for deep
        # graphs, etc.) -- not only ``pickle.PicklingError``. Failing to serialize must not
        # crash the caller (e.g. the vertex build); skip the cache write instead, which
        # just means the value is recomputed on the next access. See issue #13764.
        try:
            pickled = dill.dumps(value, recurse=True)
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(
                f"RedisCache skipping cache for key '{key}': value is not serializable ({type(exc).__name__}: {exc})."
            )
            # Drop any previously-cached value for this key. ``upsert`` does
            # get -> merge -> set, so leaving an older entry in place would let a
            # later get() serve stale data instead of recomputing. (DEL of a
            # missing key is a harmless no-op.)
            await self._client.delete(self._key(key))
            return
        if pickled:
            # Prefix an HMAC tag so get() can reject tampered/forged payloads
            # before deserialization (see get()). The tag is bound to the
            # namespaced key so it cannot be replayed under a different key.
            namespaced_key = self._key(key)
            tag = self._integrity_tag(namespaced_key, pickled)
            result = await self._client.setex(namespaced_key, self.expiration_time, tag + pickled)
            if not result:
                msg = "RedisCache could not set the value."
                raise ValueError(msg)

    @override
    async def upsert(self, key, value, lock=None) -> None:
        """Inserts or updates a value in the cache.

        If the existing value and the new value are both dictionaries, they are merged.

        Args:
            key: The key of the item.
            value: The value to insert or update.
            lock: A lock to use for the operation.
        """
        if key is None:
            return
        existing_value = await self.get(key)
        if existing_value is not None and isinstance(existing_value, dict) and isinstance(value, dict):
            existing_value.update(value)
            value = existing_value

        await self.set(key, value)

    @override
    async def delete(self, key, lock=None) -> None:
        await self._client.delete(self._key(key))

    @override
    async def clear(self, lock=None) -> None:
        """Clear all items from the cache using a key-prefix scan to avoid nuking unrelated data."""
        cursor = 0
        pattern = f"{self.KEY_PREFIX}*"
        while True:
            cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
            if keys:
                await self._client.delete(*keys)
            if cursor == 0:
                break

    async def contains(self, key) -> bool:
        """Check if the key is in the cache."""
        if key is None:
            return False
        return bool(await self._client.exists(self._key(key)))

    @override
    async def teardown(self) -> None:
        """Close the Redis client connection to prevent socket leaks across fork."""
        await self._client.aclose()

    def __repr__(self) -> str:
        """Return a string representation of the RedisCache instance."""
        return f"RedisCache(expiration_time={self.expiration_time})"


class AsyncInMemoryCache(AsyncBaseCacheService, Generic[AsyncLockType]):
    def __init__(self, max_size=None, expiration_time=3600) -> None:
        self.cache: OrderedDict = OrderedDict()

        self.lock = asyncio.Lock()
        self.max_size = max_size
        self.expiration_time = expiration_time

    async def get(self, key, lock: asyncio.Lock | None = None):
        async with lock or self.lock:
            return await self._get(key)

    async def _get(self, key):
        item = self.cache.get(key, None)
        if item:
            if time.time() - item["time"] < self.expiration_time:
                self.cache.move_to_end(key)
                return pickle.loads(item["value"]) if isinstance(item["value"], bytes) else item["value"]
            await logger.ainfo(f"Cache item for key '{key}' has expired and will be deleted.")
            await self._delete(key)  # Log before deleting the expired item
        return CACHE_MISS

    async def set(self, key, value, lock: asyncio.Lock | None = None) -> None:
        async with lock or self.lock:
            await self._set(
                key,
                value,
            )

    async def _set(self, key, value) -> None:
        if self.max_size and len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = {"value": value, "time": time.time()}
        self.cache.move_to_end(key)

    async def delete(self, key, lock: asyncio.Lock | None = None) -> None:
        async with lock or self.lock:
            await self._delete(key)

    async def _delete(self, key) -> None:
        if key in self.cache:
            del self.cache[key]

    async def clear(self, lock: asyncio.Lock | None = None) -> None:
        async with lock or self.lock:
            await self._clear()

    async def _clear(self) -> None:
        self.cache.clear()

    async def upsert(self, key, value, lock: asyncio.Lock | None = None) -> None:
        await self._upsert(key, value, lock)

    async def _upsert(self, key, value, lock: asyncio.Lock | None = None) -> None:
        existing_value = await self.get(key, lock)
        if existing_value is not None and isinstance(existing_value, dict) and isinstance(value, dict):
            existing_value.update(value)
            value = existing_value
        await self.set(key, value, lock)

    async def contains(self, key) -> bool:
        return key in self.cache
