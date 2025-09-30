import abc
import asyncio
import threading
from typing import Generic, TypeVar

from lfx.services.interfaces import CacheServiceProtocol

LockType = TypeVar("LockType", bound=threading.Lock)
AsyncLockType = TypeVar("AsyncLockType", bound=asyncio.Lock)


class CacheService(CacheServiceProtocol, Generic[LockType]):
    """Abstract base class for a cache."""

    name = "cache_service"

    @abc.abstractmethod
    def get(self, key, lock: LockType | None = None):
        """Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.
            lock: A lock to use for the operation.

        Returns:
            The value associated with the key, or CACHE_MISS if the key is not found.
        """

    @abc.abstractmethod
    def set(self, key, value, lock: LockType | None = None):
        """Add an item to the cache.

        Args:
            key: The key of the item.
            value: The value to cache.
            lock: A lock to use for the operation.
        """

    @abc.abstractmethod
    def upsert(self, key, value, lock: LockType | None = None):
        """Add an item to the cache if it doesn't exist, or update it if it does.

        Args:
            key: The key of the item.
            value: The value to cache.
            lock: A lock to use for the operation.
        """

    @abc.abstractmethod
    def delete(self, key, lock: LockType | None = None):
        """Remove an item from the cache.

        Args:
            key: The key of the item to remove.
            lock: A lock to use for the operation.
        """

    @abc.abstractmethod
    def clear(self, lock: LockType | None = None):
        """Clear all items from the cache."""

    @abc.abstractmethod
    def contains(self, key) -> bool:
        """Check if the key is in the cache.

        Args:
            key: The key of the item to check.

        Returns:
            True if the key is in the cache, False otherwise.
        """

    @abc.abstractmethod
    def __contains__(self, key) -> bool:
        """Check if the key is in the cache.

        Args:
            key: The key of the item to check.

        Returns:
            True if the key is in the cache, False otherwise.
        """

    @abc.abstractmethod
    def __getitem__(self, key):
        """Retrieve an item from the cache using the square bracket notation.

        Args:
            key: The key of the item to retrieve.
        """

    @abc.abstractmethod
    def __setitem__(self, key, value) -> None:
        """Add an item to the cache using the square bracket notation.

        Args:
            key: The key of the item.
            value: The value to cache.
        """

    @abc.abstractmethod
    def __delitem__(self, key) -> None:
        """Remove an item from the cache using the square bracket notation.

        Args:
            key: The key of the item to remove.
        """


class AsyncBaseCacheService(CacheServiceProtocol, Generic[AsyncLockType]):
    """Abstract base class for a async cache."""

    name = "cache_service"

    @abc.abstractmethod
    async def get(self, key, lock: AsyncLockType | None = None):
        """Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.
            lock: A lock to use for the operation.

        Returns:
            The value associated with the key, or CACHE_MISS if the key is not found.
        """

    @abc.abstractmethod
    async def set(self, key, value, lock: AsyncLockType | None = None):
        """Add an item to the cache.

        Args:
            key: The key of the item.
            value: The value to cache.
            lock: A lock to use for the operation.
        """

    @abc.abstractmethod
    async def upsert(self, key, value, lock: AsyncLockType | None = None):
        """Add an item to the cache if it doesn't exist, or update it if it does.

        Args:
            key: The key of the item.
            value: The value to cache.
            lock: A lock to use for the operation.
        """

    @abc.abstractmethod
    async def delete(self, key, lock: AsyncLockType | None = None):
        """Remove an item from the cache.

        Args:
            key: The key of the item to remove.
            lock: A lock to use for the operation.
        """

    @abc.abstractmethod
    async def clear(self, lock: AsyncLockType | None = None):
        """Clear all items from the cache."""

    @abc.abstractmethod
    async def contains(self, key) -> bool:
        """Check if the key is in the cache.

        Args:
            key: The key of the item to check.

        Returns:
            True if the key is in the cache, False otherwise.
        """


class ExternalAsyncBaseCacheService(AsyncBaseCacheService):
    """Abstract base class for an external async cache."""

    name = "cache_service"

    @abc.abstractmethod
    async def is_connected(self) -> bool:
        """Check if the cache is connected.

        Returns:
            True if the cache is connected, False otherwise.
        """
