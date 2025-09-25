import asyncio
import pickle
import threading
import time
import warnings
from collections import OrderedDict
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

        logger.warning(
            "RedisCache is an experimental feature and may not work as expected."
            " Please report any issues to our GitHub repository."
        )
        if url:
            self._client = StrictRedis.from_url(url)
        else:
            self._client = StrictRedis(host=host, port=port, db=db)
        self.expiration_time = expiration_time

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

    # -- Internal helpers -------------------------------------------------
    def _sanitize_for_pickle(self, obj):
        """Sanitize objects known to cause dill recursion issues.

        Specifically targets dynamically created Pydantic models like
        lfx.io.schema.InputSchema (both class objects and instances).
        Falls back to identity for everything else.
        """
        try:
            from pydantic import BaseModel  # type: ignore
        except Exception:  # noqa: BLE001
            BaseModel = None  # type: ignore

        visited: set[int] = set()

        def _walk(value):
            vid = id(value)
            if vid in visited:
                return value
            visited.add(vid)

            # Replace InputSchema classes with a placeholder reference
            if isinstance(value, type):
                mod = getattr(value, "__module__", "")
                name = getattr(value, "__name__", "")
                # Avoid importing pydantic just to check subclassing; use module+name
                if mod.startswith("lfx.io.schema") and name == "InputSchema":
                    return {"__lfx_skipped_class__": f"{mod}.{name}"}
                # For any class, store a lightweight path to avoid pickling class objects
                return {"__class_path__": f"{mod}.{name}"}

            # Replace InputSchema instances with plain data
            if BaseModel is not None and isinstance(value, BaseModel):  # type: ignore[arg-type]
                cls = value.__class__
                mod = getattr(cls, "__module__", "")
                name = getattr(cls, "__name__", "")
                if mod.startswith("lfx.io.schema") and name == "InputSchema":
                    try:
                        return value.model_dump()
                    except Exception:  # noqa: BLE001
                        return dict(value.__dict__)

            # Replace callables (functions, methods, lambdas) with path-like hint or repr
            try:
                import inspect

                if inspect.isfunction(value) or inspect.ismethod(value) or inspect.isbuiltin(value):
                    mod = getattr(value, "__module__", "")
                    name = getattr(value, "__qualname__", getattr(value, "__name__", ""))
                    return {"__callable_path__": f"{mod}.{name}"}
            except Exception:
                pass

            # Replace instances of dynamically created or custom component classes
            # that commonly resist pickling.
            cls = (
                value.__class__
                if not isinstance(value, (dict, list, tuple, set, bytes, bytearray, str, int, float, bool, type(None)))
                else None
            )
            if cls is not None:
                mod = getattr(cls, "__module__", "")
                qual = getattr(cls, "__qualname__", getattr(cls, "__name__", ""))
                if mod.startswith("lfx.custom") or "<locals>" in qual or mod == "__main__" or mod == "builtins":
                    # Best-effort shallow representation
                    try:
                        return {"__repr__": repr(value)}
                    except Exception:
                        return {"__class__": f"{mod}.{qual}"}

            # Containers
            if isinstance(value, dict):
                return {k: _walk(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                seq = [_walk(v) for v in value]
                if isinstance(value, tuple):
                    return tuple(seq)
                if isinstance(value, set):
                    return set(seq)
                return seq

            return value

        return _walk(obj)

    @override
    async def get(self, key, lock=None):
        if key is None:
            return CACHE_MISS
        value = await self._client.get(str(key))
        return dill.loads(value) if value else CACHE_MISS

    @override
    async def set(self, key, value, lock=None) -> None:
        try:
            # First attempt: try to pickle as-is, suppressing noisy PicklingWarnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                # Try ignoring dill's own PicklingWarning if available
                try:
                    from dill._dill import PicklingWarning as _DillPicklingWarning  # type: ignore

                    warnings.simplefilter("ignore", category=_DillPicklingWarning)
                except Exception:
                    pass
                pickled = dill.dumps(value, recurse=False, byref=True)
        except Exception:
            # Fallback: sanitize value to strip problematic dynamic schemas
            sanitized = self._sanitize_for_pickle(value)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                try:
                    from dill._dill import PicklingWarning as _DillPicklingWarning  # type: ignore

                    warnings.simplefilter("ignore", category=_DillPicklingWarning)
                except Exception:
                    pass
                pickled = dill.dumps(sanitized, recurse=False, byref=True)

        if pickled:
            result = await self._client.setex(str(key), self.expiration_time, pickled)
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
        await self._client.delete(key)

    @override
    async def clear(self, lock=None) -> None:
        """Clear all items from the cache."""
        await self._client.flushdb()

    async def contains(self, key) -> bool:
        """Check if the key is in the cache."""
        if key is None:
            return False
        return bool(await self._client.exists(str(key)))

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
