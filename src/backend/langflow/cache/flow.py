import threading
import time
from collections import OrderedDict

from langflow.cache.base import BaseCache


class InMemoryCache(BaseCache):
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
        self._lock = threading.Lock()
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
            if key in self._cache:
                item = self._cache.pop(key)
                if (
                    self.expiration_time is None
                    or time.time() - item["time"] < self.expiration_time
                ):
                    # Move the key to the end to make it recently used
                    self._cache[key] = item
                    return item["value"]
                else:
                    self.delete(key)
            return None

    def set(self, key, value):
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
            self._cache[key] = {"value": value, "time": time.time()}

    def get_or_set(self, key, value):
        """
        Retrieve an item from the cache. If the item does not exist, set it with the provided value.

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
        # with self._lock:
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
