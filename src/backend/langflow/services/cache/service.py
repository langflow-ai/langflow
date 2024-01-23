import pickle
import threading
import time
from collections import OrderedDict

from loguru import logger

from langflow.services.base import Service
from langflow.services.cache.base import BaseCacheService


class InMemoryCache(BaseCacheService, Service):

    """
    A simple in-memory cache using an OrderedDict.

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

    def __init__(self, max_size=None, expiration_time=60 * 60):
        """
        Initialize a new InMemoryCache instance.

        Args:
            max_size (int, optional): Maximum number of items to store in the cache.
            expiration_time (int, optional): Time in seconds after which a cached item expires. Default is 1 hour.
        """
        self._cache = OrderedDict()
        self._lock = threading.RLock()
        self.max_size = max_size
        self.expiration_time = expiration_time

    def get(self, key):
        """
        Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.

        Returns:
            The value associated with the key, or None if the key is not found or the item has expired.
        """
        with self._lock:
            return self._get_without_lock(key)

    def _get_without_lock(self, key):
        """
        Retrieve an item from the cache without acquiring the lock.
        """
        if item := self._cache.get(key):
            if self.expiration_time is None or time.time() - item["time"] < self.expiration_time:
                # Move the key to the end to make it recently used
                self._cache.move_to_end(key)
                # Check if the value is pickled
                if isinstance(item["value"], bytes):
                    value = pickle.loads(item["value"])
                else:
                    value = item["value"]
                return value
            else:
                self.delete(key)
        return None

    def set(self, key, value, pickle=False):
        """
        Add an item to the cache.

        If the cache is full, the least recently used item is evicted.

        Args:
            key: The key of the item.
            value: The value to cache.
        """
        with self._lock:
            if key in self._cache:
                # Remove existing key before re-inserting to update order
                self.delete(key)
            elif self.max_size and len(self._cache) >= self.max_size:
                # Remove least recently used item
                self._cache.popitem(last=False)
            # pickle locally to mimic Redis
            if pickle:
                value = pickle.dumps(value)

            self._cache[key] = {"value": value, "time": time.time()}

    def upsert(self, key, value):
        """
        Inserts or updates a value in the cache.
        If the existing value and the new value are both dictionaries, they are merged.

        Args:
            key: The key of the item.
            value: The value to insert or update.
        """
        with self._lock:
            existing_value = self._get_without_lock(key)
            if existing_value is not None and isinstance(existing_value, dict) and isinstance(value, dict):
                existing_value.update(value)
                value = existing_value

            self.set(key, value)

    def get_or_set(self, key, value):
        """
        Retrieve an item from the cache. If the item does not exist,
        set it with the provided value.

        Args:
            key: The key of the item.
            value: The value to cache if the item doesn't exist.

        Returns:
            The cached value associated with the key.
        """
        with self._lock:
            if key in self._cache:
                return self.get(key)
            self.set(key, value)
            return value

    def delete(self, key):
        """
        Remove an item from the cache.

        Args:
            key: The key of the item to remove.
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        """
        Clear all items from the cache.
        """
        with self._lock:
            self._cache.clear()

    def __contains__(self, key):
        """Check if the key is in the cache."""
        return key in self._cache

    def __getitem__(self, key):
        """Retrieve an item from the cache using the square bracket notation."""
        return self.get(key)

    def __setitem__(self, key, value):
        """Add an item to the cache using the square bracket notation."""
        self.set(key, value)

    def __delitem__(self, key):
        """Remove an item from the cache using the square bracket notation."""
        self.delete(key)

    def __len__(self):
        """Return the number of items in the cache."""
        return len(self._cache)

    def __repr__(self):
        """Return a string representation of the InMemoryCache instance."""
        return f"InMemoryCache(max_size={self.max_size}, expiration_time={self.expiration_time})"


class RedisCache(BaseCacheService, Service):
    """
    A Redis-based cache implementation.

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

    def __init__(self, host="localhost", port=6379, db=0, url=None, expiration_time=60 * 60):
        """
        Initialize a new RedisCache instance.

        Args:
            host (str, optional): Redis host.
            port (int, optional): Redis port.
            db (int, optional): Redis DB.
            expiration_time (int, optional): Time in seconds after which a
            ached item expires. Default is 1 hour.
        """
        try:
            import redis
        except ImportError as exc:
            raise ImportError(
                "RedisCache requires the redis-py package."
                " Please install Langflow with the deploy extra: pip install langflow[deploy]"
            ) from exc
        logger.warning(
            "RedisCache is an experimental feature and may not work as expected."
            " Please report any issues to our GitHub repository."
        )
        if url:
            self._client = redis.StrictRedis.from_url(url)
        else:
            self._client = redis.StrictRedis(host=host, port=port, db=db)
        self.expiration_time = expiration_time

    # check connection
    def is_connected(self):
        """
        Check if the Redis client is connected.
        """
        import redis

        try:
            self._client.ping()
            return True
        except redis.exceptions.ConnectionError:
            return False

    def get(self, key):
        """
        Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.

        Returns:
            The value associated with the key, or None if the key is not found.
        """
        value = self._client.get(key)
        return pickle.loads(value) if value else None

    def set(self, key, value):
        """
        Add an item to the cache.

        Args:
            key: The key of the item.
            value: The value to cache.
        """
        try:
            if pickled := pickle.dumps(value):
                result = self._client.setex(key, self.expiration_time, pickled)
                if not result:
                    raise ValueError("RedisCache could not set the value.")
        except TypeError as exc:
            raise TypeError("RedisCache only accepts values that can be pickled. ") from exc

    def upsert(self, key, value):
        """
        Inserts or updates a value in the cache.
        If the existing value and the new value are both dictionaries, they are merged.

        Args:
            key: The key of the item.
            value: The value to insert or update.
        """
        existing_value = self.get(key)
        if existing_value is not None and isinstance(existing_value, dict) and isinstance(value, dict):
            existing_value.update(value)
            value = existing_value

        self.set(key, value)

    def delete(self, key):
        """
        Remove an item from the cache.

        Args:
            key: The key of the item to remove.
        """
        self._client.delete(key)

    def clear(self):
        """
        Clear all items from the cache.
        """
        self._client.flushdb()

    def __contains__(self, key):
        """Check if the key is in the cache."""
        return False if key is None else self._client.exists(key)

    def __getitem__(self, key):
        """Retrieve an item from the cache using the square bracket notation."""
        return self.get(key)

    def __setitem__(self, key, value):
        """Add an item to the cache using the square bracket notation."""
        self.set(key, value)

    def __delitem__(self, key):
        """Remove an item from the cache using the square bracket notation."""
        self.delete(key)

    def __repr__(self):
        """Return a string representation of the RedisCache instance."""
        return f"RedisCache(expiration_time={self.expiration_time})"
