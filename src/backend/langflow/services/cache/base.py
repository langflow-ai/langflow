import abc
import asyncio
import threading
from typing import Optional

from langflow.services.base import Service


class CacheService(Service):
    """
    Abstract base class for a cache.
    """

    name = "cache_service"

    @abc.abstractmethod
    def get(self, key, lock: Optional[threading.Lock] = None):
        """
        Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.

        Returns:
            The value associated with the key, or None if the key is not found.
        """

    @abc.abstractmethod
    def set(self, key, value, lock: Optional[threading.Lock] = None):
        """
        Add an item to the cache.

        Args:
            key: The key of the item.
            value: The value to cache.
        """

    @abc.abstractmethod
    def upsert(self, key, value, lock: Optional[threading.Lock] = None):
        """
        Add an item to the cache if it doesn't exist, or update it if it does.

        Args:
            key: The key of the item.
            value: The value to cache.
        """

    @abc.abstractmethod
    def delete(self, key, lock: Optional[threading.Lock] = None):
        """
        Remove an item from the cache.

        Args:
            key: The key of the item to remove.
        """

    @abc.abstractmethod
    def clear(self, lock: Optional[threading.Lock] = None):
        """
        Clear all items from the cache.
        """

    @abc.abstractmethod
    def __contains__(self, key):
        """
        Check if the key is in the cache.

        Args:
            key: The key of the item to check.

        Returns:
            True if the key is in the cache, False otherwise.
        """

    @abc.abstractmethod
    def __getitem__(self, key):
        """
        Retrieve an item from the cache using the square bracket notation.

        Args:
            key: The key of the item to retrieve.
        """

    @abc.abstractmethod
    def __setitem__(self, key, value):
        """
        Add an item to the cache using the square bracket notation.

        Args:
            key: The key of the item.
            value: The value to cache.
        """

    @abc.abstractmethod
    def __delitem__(self, key):
        """
        Remove an item from the cache using the square bracket notation.

        Args:
            key: The key of the item to remove.
        """


class AsyncBaseCacheService(Service):
    """
    Abstract base class for a async cache.
    """

    name = "cache_service"

    @abc.abstractmethod
    async def get(self, key, lock: Optional[asyncio.Lock] = None):
        """
        Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.

        Returns:
            The value associated with the key, or None if the key is not found.
        """

    @abc.abstractmethod
    async def set(self, key, value, lock: Optional[asyncio.Lock] = None):
        """
        Add an item to the cache.

        Args:
            key: The key of the item.
            value: The value to cache.
        """

    @abc.abstractmethod
    async def upsert(self, key, value, lock: Optional[asyncio.Lock] = None):
        """
        Add an item to the cache if it doesn't exist, or update it if it does.

        Args:
            key: The key of the item.
            value: The value to cache.
        """

    @abc.abstractmethod
    async def delete(self, key, lock: Optional[asyncio.Lock] = None):
        """
        Remove an item from the cache.

        Args:
            key: The key of the item to remove.
        """

    @abc.abstractmethod
    async def clear(self, lock: Optional[asyncio.Lock] = None):
        """
        Clear all items from the cache.
        """

    @abc.abstractmethod
    def __contains__(self, key):
        """
        Check if the key is in the cache.

        Args:
            key: The key of the item to check.

        Returns:
            True if the key is in the cache, False otherwise.
        """
